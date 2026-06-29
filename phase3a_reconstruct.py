"""
Phase 3A ERT reconstruction tool.

Reads full FRAME records from the Phase 3A ESP32-S3 firmware and attempts
PyEIT difference reconstruction with a 12-electrode adjacent-adjacent protocol.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import serial

import pyeit.eit.protocol as protocol_module
import pyeit.mesh as mesh
from pyeit.eit.jac import JAC


N_ELECTRODES = 12
DEFAULT_PORT = "COM3"
DEFAULT_BAUD = 115200
DEFAULT_LOG_DIR = Path("phase3a_logs")
DEFAULT_MAX_LOG_FRAMES = 100
DEFAULT_CAPTURE_FRAMES = 20


@dataclass(frozen=True)
class FrameRecord:
    i_pair: tuple[int, int]
    v_pair: tuple[int, int]
    voltage_mv: float


class FrameLogger:
    def __init__(self, path: Path, max_frames: int) -> None:
        self.path = path
        self.max_frames = max_frames
        self.frames_written = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(["run_id", "frame_index", "i_plus", "i_minus", "v_plus", "v_minus", "voltage_mv"])

    def write_frame(self, run_id: str, frame_index: int, records: list[FrameRecord]) -> None:
        if self.frames_written >= self.max_frames:
            return
        for record in records:
            self._writer.writerow(build_frame_log_row(run_id, frame_index, record))
        self._handle.flush()
        self.frames_written += 1

    def close(self) -> None:
        self._handle.close()


def index_to_electrode(index: int) -> str:
    return f"E{index + 1}"


def build_frame_log_row(run_id: str, frame_index: int, record: FrameRecord) -> list[str]:
    return [
        run_id,
        str(frame_index),
        index_to_electrode(record.i_pair[0]),
        index_to_electrode(record.i_pair[1]),
        index_to_electrode(record.v_pair[0]),
        index_to_electrode(record.v_pair[1]),
        f"{record.voltage_mv:.6f}",
    ]


def default_log_path(log_dir: Path, mode: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return log_dir / f"phase3a-{mode}-{stamp}.csv"


def create_frame_logger(args: argparse.Namespace, mode: str) -> FrameLogger | None:
    if not args.log:
        return None
    log_path = Path(args.log_file) if args.log_file else default_log_path(Path(args.log_dir), mode)
    return FrameLogger(log_path, args.max_log_frames)


def electrode_to_index(label: str) -> int:
    normalized = label.strip().upper()
    if not normalized.startswith("E"):
        raise ValueError(f"Invalid electrode label: {label}")
    index = int(normalized[1:]) - 1
    if index < 0 or index >= N_ELECTRODES:
        raise ValueError(f"Electrode out of range: {label}")
    return index


def next_electrode(index: int, n_el: int = N_ELECTRODES) -> int:
    return (index + 1) % n_el


def pair_overlaps(vp: int, vn: int, i_src: int, i_ret: int) -> bool:
    return vp == vn or vp in (i_src, i_ret) or vn in (i_src, i_ret)


def build_adjacent_protocol(n_el: int = N_ELECTRODES) -> protocol_module.PyEITProtocol:
    return build_protocol(n_el=n_el, injection_distance=1)


def build_skip_one_protocol(n_el: int = N_ELECTRODES) -> protocol_module.PyEITProtocol:
    return build_protocol(n_el=n_el, injection_distance=2)


def build_skip_two_protocol(n_el: int = N_ELECTRODES) -> protocol_module.PyEITProtocol:
    return build_protocol(n_el=n_el, injection_distance=3)


def build_opposite_protocol(n_el: int = N_ELECTRODES) -> protocol_module.PyEITProtocol:
    if n_el % 2 != 0:
        raise ValueError("Opposite protocol requires an even electrode count")
    return build_protocol(n_el=n_el, injection_distance=n_el // 2)


def build_protocol(
    n_el: int = N_ELECTRODES,
    injection_distance: int = 1,
) -> protocol_module.PyEITProtocol:
    ex_rows: list[list[int]] = []
    meas_rows: list[list[list[int]]] = []

    for i_src in range(n_el):
        i_ret = (i_src + injection_distance) % n_el
        ex_rows.append([i_src, i_ret])

        per_excitation: list[list[int]] = []
        for vp in range(n_el):
            vn = next_electrode(vp, n_el)
            if pair_overlaps(vp, vn, i_src, i_ret):
                continue
            # PyEIT expects [N, M] because subtract_row computes V_N - V_M.
            per_excitation.append([vn, vp])
        meas_rows.append(per_excitation)

    ex_mat = np.asarray(ex_rows, dtype=int)
    meas_mat = np.asarray(meas_rows, dtype=int)
    keep_ba = np.ones(ex_mat.shape[0] * meas_mat.shape[1], dtype=bool)
    return protocol_module.PyEITProtocol(ex_mat, meas_mat, keep_ba)


def parse_frame_records(lines: Iterable[str]) -> list[FrameRecord]:
    records: list[FrameRecord] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) != 10:
            continue
        if parts[0] != "I+" or parts[2] != "I-" or parts[4] != "V+" or parts[6] != "V-" or parts[8] != "V":
            continue
        records.append(
            FrameRecord(
                i_pair=(electrode_to_index(parts[1]), electrode_to_index(parts[3])),
                v_pair=(electrode_to_index(parts[5]), electrode_to_index(parts[7])),
                voltage_mv=float(parts[9]),
            )
        )
    return records


def identify_drive_pattern(records: list[FrameRecord], n_el: int = N_ELECTRODES) -> str:
    if not records:
        return "empty frame"
    distances = {(record.i_pair[1] - record.i_pair[0]) % n_el for record in records}
    if distances == {1}:
        return "adjacent-drive"
    if distances == {2}:
        return "skip-1-drive"
    if distances == {3}:
        return "skip-2-drive"
    if n_el % 2 == 0 and distances == {n_el // 2}:
        return "opposite-drive"
    return f"unknown drive spacing {sorted(distances)}"


def capture_frame_numbers(count: int) -> range:
    if count <= 0:
        raise ValueError("Capture frame count must be positive")
    return range(1, count + 1)


def print_stability_summary(delta_rms_values: list[float]) -> None:
    if not delta_rms_values:
        return
    values = np.asarray(delta_rms_values)
    print(
        "[Summary] "
        f"frames={len(values)} "
        f"RMS min={values.min():.3f}mV "
        f"median={np.median(values):.3f}mV "
        f"max={values.max():.3f}mV "
        f"first={values[0]:.3f}mV "
        f"last={values[-1]:.3f}mV"
    )


def records_to_vector(
    records: list[FrameRecord],
    protocol: protocol_module.PyEITProtocol,
) -> np.ndarray:
    by_key = {
        (record.i_pair, record.v_pair): record.voltage_mv
        for record in records
    }

    values: list[float] = []
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        i_pair = (int(ex_pair[0]), int(ex_pair[1]))
        for meas_pair in protocol.meas_mat[ex_index]:
            # Firmware prints V+ then V-, while PyEIT stores [N, M].
            v_pair = (int(meas_pair[1]), int(meas_pair[0]))
            try:
                values.append(by_key[(i_pair, v_pair)])
            except KeyError as exc:
                detected_pattern = identify_drive_pattern(records)
                raise ValueError(
                    f"Missing measurement I={i_pair} V={v_pair}; frame/protocol mismatch. "
                    f"Received {detected_pattern} data."
                ) from exc

    return np.asarray(values, dtype=float)


def read_one_frame(ser: serial.Serial) -> list[FrameRecord]:
    buffer: list[str] = []
    in_frame = False

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        if line == "FRAME:":
            in_frame = True
            buffer = []
            continue
        if line == "END" and in_frame:
            return parse_frame_records(buffer)
        if in_frame:
            buffer.append(line)


def create_solver(protocol: protocol_module.PyEITProtocol) -> tuple[mesh.PyEITMesh, JAC]:
    eit_mesh = mesh.create(n_el=N_ELECTRODES, h0=0.12)
    solver = JAC(eit_mesh, protocol)
    solver.setup(p=0.45, lamb=0.01, method="kotre", jac_normalized=False)
    return eit_mesh, solver


def reconstruct_difference(
    baseline: np.ndarray,
    current: np.ndarray,
    solver: JAC,
) -> np.ndarray:
    return np.real(solver.solve_gs(current, baseline))


def create_reconstruction_plot() -> tuple[plt.Figure, plt.Axes]:
    plt.ion()
    fig, ax = plt.subplots(figsize=(7, 6))
    return fig, ax


def update_reconstruction_plot(
    fig: plt.Figure,
    ax: plt.Axes,
    eit_mesh: mesh.PyEITMesh,
    ds: np.ndarray,
    title: str,
) -> None:
    ax.clear()
    image = ax.tripcolor(
        eit_mesh.node[:, 0],
        eit_mesh.node[:, 1],
        eit_mesh.element,
        ds,
        shading="flat",
        cmap="coolwarm",
    )
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_axis_off()
    for index in range(N_ELECTRODES):
        angle = 2.0 * np.pi * index / N_ELECTRODES
        x = 1.12 * np.cos(angle)
        y = 1.12 * np.sin(angle)
        ax.text(
            x,
            y,
            f"E{index + 1}",
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="black",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
        )
    if hasattr(ax, "_phase3a_colorbar"):
        ax._phase3a_colorbar.update_normal(image)
    else:
        ax._phase3a_colorbar = fig.colorbar(image, ax=ax)
        ax._phase3a_colorbar.set_label("Relative conductivity change")
    plt.tight_layout()
    plt.pause(0.05)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3A live ERT reconstruction")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--baseline-wait", type=float, default=1.0)
    parser.add_argument("--log", action="store_true", help="Write captured frames to bounded CSV log")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="Directory for generated frame logs")
    parser.add_argument("--log-file", default=None, help="Optional exact CSV log path")
    parser.add_argument("--max-log-frames", type=int, default=DEFAULT_MAX_LOG_FRAMES, help="Maximum frames to write")
    parser.add_argument(
        "--frames",
        type=int,
        default=DEFAULT_CAPTURE_FRAMES,
        help="Comparison frames to capture after the baseline",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame_numbers = capture_frame_numbers(args.frames)
    protocol = build_adjacent_protocol(N_ELECTRODES)
    eit_mesh, solver = create_solver(protocol)
    logger = create_frame_logger(args, "adjacent")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    fig = None
    delta_rms_values: list[float] = []

    print(f"[Serial] Connecting to {args.port} at {args.baud} baud...")
    ser = serial.Serial(args.port, args.baud, timeout=0.5)
    time.sleep(args.baseline_wait)
    ser.reset_input_buffer()

    try:
        print("[Capture] Requesting baseline frame...")
        ser.write(b"s\n")
        baseline_records = read_one_frame(ser)
        baseline = records_to_vector(baseline_records, protocol)
        if logger is not None:
            logger.write_frame(run_id, 0, baseline_records)
            print(f"[Log] writing up to {logger.max_frames} frames to {logger.path}")
            if logger.max_frames < args.frames + 1:
                print(
                    f"[Log warning] {args.frames + 1} frames include the baseline, "
                    f"but the log limit is {logger.max_frames}."
                )
        print(f"[Baseline] captured {len(baseline)} measurements")

        fig, ax = create_reconstruction_plot()
        print(f"[Run] Capturing {args.frames} comparison frames. Press Ctrl+C to stop early.")
        for frame_index in frame_numbers:
            ser.write(b"s\n")
            current_records = read_one_frame(ser)
            current = records_to_vector(current_records, protocol)
            if logger is not None:
                logger.write_frame(run_id, frame_index, current_records)
            ds = reconstruct_difference(baseline, current, solver)
            delta_rms = float(np.sqrt(np.mean((current - baseline) ** 2)))
            delta_rms_values.append(delta_rms)
            print(
                f"[Frame {frame_index}/{args.frames}] "
                f"min={current.min():+.3f}mV max={current.max():+.3f}mV "
                f"delta_rms={delta_rms:.3f}mV"
            )
            update_reconstruction_plot(
                fig,
                ax,
                eit_mesh,
                ds,
                "Phase 3A ERT Difference Reconstruction",
            )
        print_stability_summary(delta_rms_values)
        print("[Complete] Capture finished. Close the plot window to exit.")
    except KeyboardInterrupt:
        print("\nStopped.")
        print_stability_summary(delta_rms_values)
    finally:
        if logger is not None:
            logger.close()
            print(f"[Log] saved {logger.frames_written} frames to {logger.path}")
        ser.close()
    if fig is not None:
        plt.ioff()
        plt.show()


if __name__ == "__main__":
    main()
