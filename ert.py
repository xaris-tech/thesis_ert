"""
Live ERT acquisition helper for the current ESP32-based scanner.

This version focuses on live serial acquisition, baseline comparison,
real-time plotting, and PyEIT-friendly measurement export.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
import time
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import serial

try:
    import msvcrt
except ImportError:  # pragma: no cover - Windows-specific input helper
    msvcrt = None


DEFAULT_PORT = "COM3"
DEFAULT_BAUD = 115200
DEFAULT_EXPORT_DIR = Path("exports")


@dataclass(frozen=True)
class ParsedScan:
    channels: tuple[str, ...]
    values: np.ndarray
    raw_lines: tuple[str, ...]


@dataclass(frozen=True)
class MeasurementRecord:
    timestamp: str
    channels: tuple[str, ...]
    values: np.ndarray
    delta: np.ndarray


class AcquisitionSession:
    def __init__(self) -> None:
        self.baseline: np.ndarray | None = None
        self.channels: tuple[str, ...] | None = None
        self.records: list[MeasurementRecord] = []
        self.latest_record: MeasurementRecord | None = None
        self._baseline_record_count = 0

    def reset_baseline(self) -> None:
        self.baseline = None
        self.channels = None
        self._baseline_record_count = len(self.records)
        self.latest_record = None

    def apply_scan(self, scan: ParsedScan) -> MeasurementRecord:
        if self.channels is None:
            self.channels = scan.channels

        if self.baseline is None:
            self.baseline = scan.values.copy()

        delta = scan.values - self.baseline
        record = MeasurementRecord(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            channels=scan.channels,
            values=scan.values.copy(),
            delta=delta,
        )
        self.records.append(record)
        self.latest_record = record
        return record

    def records_since_baseline(self) -> list[MeasurementRecord]:
        return self.records[self._baseline_record_count :]


def parse_scan_lines(lines: Iterable[str]) -> ParsedScan | None:
    channels: list[str] = []
    values: list[float] = []
    raw_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) != 3:
            continue
        try:
            value = float(parts[2])
        except ValueError:
            continue
        channels.append(parts[1] or f"CH{len(channels)}")
        values.append(value)
        raw_lines.append(stripped)

    if not values:
        return None

    return ParsedScan(
        channels=tuple(channels),
        values=np.asarray(values, dtype=float),
        raw_lines=tuple(raw_lines),
    )


def build_export_payload(
    scans: list[MeasurementRecord], baseline: np.ndarray | None
) -> dict[str, np.ndarray]:
    if scans:
        measurements = np.vstack([scan.values for scan in scans]).astype(float)
    else:
        measurements = np.empty((0, 0), dtype=float)

    if baseline is not None and measurements.size:
        delta = measurements - baseline
        baseline_matrix = np.tile(baseline, (measurements.shape[0], 1))
    else:
        delta = np.empty_like(measurements)
        baseline_width = measurements.shape[1] if measurements.ndim == 2 else 0
        baseline_matrix = np.empty((0, baseline_width), dtype=float)

    timestamps = np.asarray([scan.timestamp for scan in scans], dtype="U32")
    channels = np.asarray(scans[0].channels if scans else (), dtype="U16")

    return {
        "measurements": measurements,
        "delta": delta,
        "baseline": baseline_matrix,
        "channels": channels,
        "timestamps": timestamps,
    }


def build_recent_delta_matrix(records: list[MeasurementRecord], limit: int = 20) -> np.ndarray:
    if not records:
        return np.empty((0, 0), dtype=float)
    recent = records[-limit:]
    return np.vstack([record.delta for record in recent]).astype(float)


def export_measurements(
    session: AcquisitionSession, export_dir: Path
) -> tuple[Path, Path] | None:
    records = session.records_since_baseline()
    if not records or session.baseline is None:
        return None

    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = export_dir / f"ert-scan-{stamp}.csv"
    npz_path = export_dir / f"ert-scan-{stamp}.npz"

    payload = build_export_payload(records, session.baseline)
    channels = list(records[0].channels)

    header = ["timestamp", *[f"{name}_mv" for name in channels], *[f"{name}_delta_mv" for name in channels]]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(header) + "\n")
        for record in records:
            values = [f"{value:.6f}" for value in record.values]
            deltas = [f"{value:.6f}" for value in record.delta]
            handle.write(",".join([record.timestamp, *values, *deltas]) + "\n")

    np.savez(npz_path, **payload)
    return csv_path, npz_path


def serial_reader(ser: serial.Serial, session: AcquisitionSession, lock: threading.Lock) -> None:
    buffer: list[str] = []
    in_scan = False

    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
        except serial.SerialException:
            return
        except Exception:
            continue

        if not line:
            continue

        if line.startswith("SCAN:"):
            in_scan = True
            buffer = []
            continue

        if line == "END" and in_scan:
            in_scan = False
            parsed = parse_scan_lines(buffer)
            if parsed is not None:
                with lock:
                    session.apply_scan(parsed)
            continue

        if in_scan:
            buffer.append(line)


def create_figure() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes, plt.Axes]]:
    plt.ion()
    fig = plt.figure(figsize=(14, 8))
    grid = fig.add_gridspec(2, 2, height_ratios=(2, 1.2))
    ax_delta = fig.add_subplot(grid[0, 0])
    ax_absolute = fig.add_subplot(grid[0, 1])
    ax_history = fig.add_subplot(grid[1, :])
    return fig, (ax_delta, ax_absolute, ax_history)


def update_plot(
    ax_delta: plt.Axes,
    ax_absolute: plt.Axes,
    ax_history: plt.Axes,
    session: AcquisitionSession,
) -> None:
    record = session.latest_record
    baseline = session.baseline
    if record is None or baseline is None:
        return

    channels = list(record.channels)

    ax_delta.clear()
    ax_delta.set_title("Voltage Change", fontweight="bold")
    colors = ["red" if value > 0 else "blue" for value in record.delta]
    ax_delta.bar(channels, record.delta, color=colors, alpha=0.75)
    ax_delta.axhline(y=0, color="black", linestyle="--", linewidth=1)
    ax_delta.set_ylabel("Change (mV)")
    ax_delta.grid(True, alpha=0.3)

    ax_absolute.clear()
    ax_absolute.set_title("Voltages", fontweight="bold")
    x = np.arange(len(channels))
    width = 0.35
    ax_absolute.bar(x - width / 2, baseline, width, label="Baseline", alpha=0.7)
    ax_absolute.bar(x + width / 2, record.values, width, label="Current", alpha=0.7)
    ax_absolute.set_ylabel("Voltage (mV)")
    ax_absolute.set_xticks(x)
    ax_absolute.set_xticklabels(channels)
    ax_absolute.legend()
    ax_absolute.grid(True, alpha=0.3)

    history = build_recent_delta_matrix(session.records_since_baseline(), limit=20)
    ax_history.clear()
    ax_history.set_title("Recent Delta History", fontweight="bold")
    if history.size:
        max_abs = float(np.max(np.abs(history)))
        color_limit = max(max_abs, 1.0)
        image = ax_history.imshow(
            history,
            aspect="auto",
            cmap="coolwarm",
            vmin=-color_limit,
            vmax=color_limit,
            interpolation="nearest",
        )
        ax_history.set_yticks(np.arange(history.shape[0]))
        ax_history.set_yticklabels([f"-{history.shape[0] - 1 - idx}" for idx in range(history.shape[0])])
        ax_history.set_xticks(np.arange(len(channels)))
        ax_history.set_xticklabels(channels)
        ax_history.set_ylabel("Scans Ago")
        ax_history.set_xlabel("Electrode")
        if not hasattr(ax_history, "_ert_colorbar"):
            ax_history._ert_colorbar = ax_history.figure.colorbar(image, ax=ax_history, pad=0.02)
            ax_history._ert_colorbar.set_label("Delta (mV)")
        else:
            ax_history._ert_colorbar.update_normal(image)
    else:
        ax_history.text(0.5, 0.5, "Waiting for scans...", ha="center", va="center")
        ax_history.set_axis_off()


def print_record(record: MeasurementRecord, baseline: np.ndarray) -> None:
    for index, channel in enumerate(record.channels):
        print(
            f"{channel}: {record.values[index]:.1f}mV "
            f"(was {baseline[index]:.1f}mV, d{record.delta[index]:+.1f}mV)"
        )


def print_baseline(session: AcquisitionSession) -> None:
    if session.baseline is None or session.channels is None:
        return
    summary = " | ".join(
        f"{channel}: {value:.2f} mV" for channel, value in zip(session.channels, session.baseline)
    )
    print(f"\n[BASELINE] Captured {len(session.channels)} measurements")
    print(summary)


def poll_command() -> str | None:
    if msvcrt is None:
        return None
    if not msvcrt.kbhit():
        return None
    key = msvcrt.getwch()
    if key in ("\r", "\n"):
        return None
    return key.lower()


def handle_command(
    cmd: str, ser: serial.Serial, session: AcquisitionSession, export_dir: Path
) -> bool:
    if cmd == "q":
        return False
    if cmd == "s":
        ser.write(b"s\n")
    elif cmd == "g":
        ser.write(b"g\n")
    elif cmd == "x":
        ser.write(b"x\n")
    elif cmd == "b":
        session.reset_baseline()
        print("[Baseline reset]")
    elif cmd == "w":
        exported = export_measurements(session, export_dir)
        if exported is None:
            print("[Export skipped] Need a baseline and at least one post-baseline scan.")
        else:
            csv_path, npz_path = exported
            print(f"[Exported] CSV: {csv_path}")
            print(f"[Exported] NPZ: {npz_path}")
    return True


def fallback_input_loop(ser: serial.Serial, session: AcquisitionSession, export_dir: Path) -> None:
    print("\nCommands: s=scan  g=continuous  x=stop  b=reset baseline  w=write export  q=quit\n")
    while True:
        cmd = input("> ").strip().lower()
        if not handle_command(cmd, ser, session, export_dir):
            break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live ERT acquisition helper with PyEIT-friendly exports."
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port for the ESP32")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Serial baud rate")
    parser.add_argument(
        "--export-dir",
        default=str(DEFAULT_EXPORT_DIR),
        help="Directory for CSV and NPZ exports",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_dir = Path(args.export_dir)

    print(f"\n[Serial] Connecting to {args.port} at {args.baud} baud...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.2)
    except Exception:
        print(f"ERROR: Cannot open {args.port}")
        return

    time.sleep(1.5)
    ser.reset_input_buffer()

    session = AcquisitionSession()
    lock = threading.Lock()

    print("[Serial] Starting reader thread...")
    reader_thread = threading.Thread(target=serial_reader, args=(ser, session, lock), daemon=True)
    reader_thread.start()

    print("\n" + "=" * 70)
    print("  PHASE 2 ERT TEST - Live Multi-Electrode Acquisition")
    print("=" * 70)

    if msvcrt is None:
        fallback_input_loop(ser, session, export_dir)
        ser.close()
        return

    print("\nPress keys directly: s=scan  g=continuous  x=stop  b=baseline reset  w=write export  q=quit\n")
    _, axes = create_figure()

    last_seen_timestamp: str | None = None
    running = True
    try:
        while running:
            cmd = poll_command()
            if cmd is not None:
                running = handle_command(cmd, ser, session, export_dir)

            with lock:
                baseline = session.baseline.copy() if session.baseline is not None else None
                latest = session.latest_record
                should_print = latest is not None and latest.timestamp != last_seen_timestamp

            if should_print and baseline is not None and latest is not None:
                if len(session.records_since_baseline()) == 1 and np.allclose(latest.delta, 0.0):
                    print_baseline(session)
                else:
                    print_record(latest, baseline)
                last_seen_timestamp = latest.timestamp

            with lock:
                update_plot(axes[0], axes[1], axes[2], session)
            plt.tight_layout()
            plt.pause(0.05)
            time.sleep(0.05)
    finally:
        ser.close()
        plt.close("all")
        print("Done.")


if __name__ == "__main__":
    main()
