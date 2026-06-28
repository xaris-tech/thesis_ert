"""Live reconstruction for the Phase 3A unified v2 ERT firmware."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Iterable

import numpy as np
import serial

import phase3a_reconstruct as base


DEFAULT_PORT = "COM3"
DEFAULT_BAUD = 115200
DEFAULT_LOG_DIR = Path("phase3a_logs")
MIN_VALID_CURRENT_UA = 0.5
DEFAULT_WARMUP_FRAMES = 10
DEFAULT_BASELINE_FRAMES = 10
DEFAULT_SETTLE_MS = 30
MAX_BASELINE_RELATIVE_RMS_PERCENT = 2.0
MAX_BASELINE_ABSOLUTE_RMS_KOHM = 0.002
MIN_BASELINE_CORRELATION = 0.995


@dataclass(frozen=True)
class MeasurementRecord:
    polarity: str
    i_pair: tuple[int, int]
    v_pair: tuple[int, int]
    voltage_mv: float
    current_ua: float
    quality: str


@dataclass(frozen=True)
class UnifiedFrame:
    frame_id: int
    pattern: str
    dac_code: int
    settle_ms: int
    sample_count: int
    records: list[MeasurementRecord]


@dataclass(frozen=True)
class BaselineStability:
    stable: bool
    max_relative_rms_percent: float
    max_absolute_rms_kohm: float
    min_correlation: float


@dataclass(frozen=True)
class ControlFrameMetric:
    frame: int
    rms_kohm: float
    relative_rms_percent: float
    correlation: float


@dataclass(frozen=True)
class ControlPairMetric:
    index: int
    i_pair: tuple[int, int]
    v_pair: tuple[int, int]
    rms_kohm: float
    max_abs_kohm: float


@dataclass(frozen=True)
class ControlElectrodeMetric:
    electrode: int
    mean_pair_rms_kohm: float


@dataclass(frozen=True)
class ControlDriftReport:
    frames: list[ControlFrameMetric]
    pairs: list[ControlPairMetric]
    electrodes: list[ControlElectrodeMetric]


def parse_header(line: str) -> tuple[int, str, int, int, int]:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 10 or parts[0] != "FRAME" or parts[1] != "2":
        raise ValueError(f"Unsupported frame header: {line}")
    if parts[4] != "DAC" or parts[6] != "SETTLE" or parts[8] != "SAMPLES":
        raise ValueError(f"Malformed frame header: {line}")
    pattern = parts[3].lower()
    if pattern not in {"adjacent", "opposite"}:
        raise ValueError(f"Unsupported drive pattern: {parts[3]}")
    return int(parts[2]), pattern, int(parts[5]), int(parts[7]), int(parts[9])


def parse_measurement(line: str) -> MeasurementRecord:
    parts = [part.strip() for part in line.split(",")]
    expected_labels = {
        0: "M", 1: "P", 3: "I+", 5: "I-", 7: "V+", 9: "V-",
        11: "V", 13: "I", 15: "Q",
    }
    if len(parts) != 17 or any(parts[index] != label for index, label in expected_labels.items()):
        raise ValueError(f"Malformed measurement record: {line}")
    polarity = parts[2].upper()
    if polarity not in {"FWD", "REV"}:
        raise ValueError(f"Unsupported polarity: {polarity}")
    return MeasurementRecord(
        polarity=polarity,
        i_pair=(base.electrode_to_index(parts[4]), base.electrode_to_index(parts[6])),
        v_pair=(base.electrode_to_index(parts[8]), base.electrode_to_index(parts[10])),
        voltage_mv=float(parts[12]),
        current_ua=float(parts[14]),
        quality=parts[16],
    )


def parse_v2_frame(lines: Iterable[str]) -> UnifiedFrame:
    cleaned = [line.strip() for line in lines if line.strip()]
    if len(cleaned) < 2:
        raise ValueError("Incomplete v2 frame")
    frame_id, pattern, dac_code, settle_ms, sample_count = parse_header(cleaned[0])
    if cleaned[-1] != f"END,{frame_id}":
        raise ValueError("Frame END marker does not match frame ID")
    records = [parse_measurement(line) for line in cleaned[1:-1]]
    if not records:
        raise ValueError("Frame contains no measurements")
    return UnifiedFrame(frame_id, pattern, dac_code, settle_ms, sample_count, records)


def validate_record(record: MeasurementRecord) -> None:
    if record.quality != "OK":
        raise ValueError(f"Measurement quality is {record.quality}")
    if abs(record.current_ua) < MIN_VALID_CURRENT_UA:
        raise ValueError("Measured current is too close to zero")


def paired_transfer_resistance(
    frame: UnifiedFrame,
) -> dict[tuple[tuple[int, int], tuple[int, int]], float]:
    forward: dict[tuple[tuple[int, int], tuple[int, int]], MeasurementRecord] = {}
    reverse: dict[tuple[tuple[int, int], tuple[int, int]], MeasurementRecord] = {}

    for record in frame.records:
        validate_record(record)
        if record.polarity == "FWD":
            key = (record.i_pair, record.v_pair)
            forward[key] = record
        else:
            canonical_i_pair = (record.i_pair[1], record.i_pair[0])
            key = (canonical_i_pair, record.v_pair)
            reverse[key] = record

    if forward.keys() != reverse.keys():
        missing_reverse = sorted(forward.keys() - reverse.keys())
        missing_forward = sorted(reverse.keys() - forward.keys())
        raise ValueError(
            f"Forward/reverse mismatch; missing reverse={missing_reverse[:3]} "
            f"missing forward={missing_forward[:3]}"
        )

    result: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}
    for key, fwd in forward.items():
        rev = reverse[key]
        fwd_resistance = fwd.voltage_mv / abs(fwd.current_ua)
        rev_resistance = rev.voltage_mv / abs(rev.current_ua)
        # mV/uA is numerically kOhm. Reverse voltage has opposite physical sign.
        result[key] = 0.5 * (fwd_resistance - rev_resistance)
    return result


def protocol_and_command(pattern: str):
    normalized = pattern.lower()
    if normalized == "adjacent":
        return base.build_adjacent_protocol(), b"ma\n"
    if normalized == "opposite":
        return base.build_opposite_protocol(), b"mo\n"
    raise ValueError(f"Unsupported pattern: {pattern}")


def frame_to_vector(frame: UnifiedFrame, protocol) -> np.ndarray:
    values_by_key = paired_transfer_resistance(frame)
    values: list[float] = []
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        i_pair = (int(ex_pair[0]), int(ex_pair[1]))
        for meas_pair in protocol.meas_mat[ex_index]:
            v_pair = (int(meas_pair[1]), int(meas_pair[0]))
            try:
                values.append(values_by_key[(i_pair, v_pair)])
            except KeyError as exc:
                raise ValueError(
                    f"Missing normalized measurement I={i_pair} V={v_pair}; "
                    f"frame pattern is {frame.pattern}"
                ) from exc
    return np.asarray(values, dtype=float)


def average_vectors(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise ValueError("At least one vector is required")
    expected_shape = vectors[0].shape
    if any(vector.shape != expected_shape for vector in vectors):
        raise ValueError("All vectors must have the same shape")
    return np.mean(np.stack(vectors), axis=0)


def protocol_vector_keys(protocol) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    keys: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        i_pair = (int(ex_pair[0]), int(ex_pair[1]))
        for meas_pair in protocol.meas_mat[ex_index]:
            keys.append((i_pair, (int(meas_pair[1]), int(meas_pair[0]))))
    return keys


def _vector_correlation(left: np.ndarray, right: np.ndarray) -> float:
    if np.std(left) == 0.0 or np.std(right) == 0.0:
        return 1.0 if np.allclose(left, right) else 0.0
    return float(np.corrcoef(left, right)[0, 1])


def analyze_control_drift(
    baseline: np.ndarray,
    controls: list[np.ndarray],
    protocol,
) -> ControlDriftReport:
    if not controls:
        raise ValueError("At least one control frame is required")
    if any(vector.shape != baseline.shape for vector in controls):
        raise ValueError("Control vectors must match the baseline shape")

    keys = protocol_vector_keys(protocol)
    if len(keys) != len(baseline):
        raise ValueError("Protocol measurement count does not match vector length")

    baseline_rms = max(float(np.sqrt(np.mean(baseline ** 2))), np.finfo(float).eps)
    deltas = np.stack([vector - baseline for vector in controls])
    frames = [
        ControlFrameMetric(
            frame=index + 1,
            rms_kohm=float(np.sqrt(np.mean(delta ** 2))),
            relative_rms_percent=(
                100.0 * float(np.sqrt(np.mean(delta ** 2))) / baseline_rms
            ),
            correlation=_vector_correlation(controls[index], baseline),
        )
        for index, delta in enumerate(deltas)
    ]

    pair_rms = np.sqrt(np.mean(deltas ** 2, axis=0))
    pair_max = np.max(np.abs(deltas), axis=0)
    pairs = [
        ControlPairMetric(index, key[0], key[1], float(pair_rms[index]), float(pair_max[index]))
        for index, key in enumerate(keys)
    ]
    pairs.sort(key=lambda item: item.rms_kohm, reverse=True)

    electrode_values: dict[int, list[float]] = {
        electrode: [] for electrode in range(base.N_ELECTRODES)
    }
    for pair in pairs:
        for electrode in set(pair.i_pair + pair.v_pair):
            electrode_values[electrode].append(pair.rms_kohm)
    electrodes = [
        ControlElectrodeMetric(electrode, float(np.mean(values)))
        for electrode, values in electrode_values.items()
    ]
    electrodes.sort(key=lambda item: item.mean_pair_rms_kohm, reverse=True)
    return ControlDriftReport(frames, pairs, electrodes)


def write_control_report(path: Path, report: ControlDriftReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "record_type", "rank", "frame", "i_plus", "i_minus", "v_plus",
        "v_minus", "electrode", "rms_kohm", "relative_rms_percent",
        "correlation", "max_abs_kohm",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for metric in report.frames:
            writer.writerow([
                "frame", "", metric.frame, "", "", "", "", "",
                f"{metric.rms_kohm:.9f}", f"{metric.relative_rms_percent:.6f}",
                f"{metric.correlation:.9f}", "",
            ])
        for rank, metric in enumerate(report.pairs, start=1):
            writer.writerow([
                "pair", rank, "", base.index_to_electrode(metric.i_pair[0]),
                base.index_to_electrode(metric.i_pair[1]),
                base.index_to_electrode(metric.v_pair[0]),
                base.index_to_electrode(metric.v_pair[1]), "",
                f"{metric.rms_kohm:.9f}", "", "", f"{metric.max_abs_kohm:.9f}",
            ])
        for rank, metric in enumerate(report.electrodes, start=1):
            writer.writerow([
                "electrode", rank, "", "", "", "", "",
                base.index_to_electrode(metric.electrode),
                f"{metric.mean_pair_rms_kohm:.9f}", "", "", "",
            ])


def wait_for_target(auto_continue: bool, input_fn=input) -> None:
    if not auto_continue:
        input_fn("[Target] Place the target without moving electrodes, then press Enter...")


def reconstruction_image_paths(csv_path: Path) -> tuple[Path, Path]:
    stem = csv_path.stem
    return (
        csv_path.with_name(f"{stem}-reconstructions.png"),
        csv_path.with_name(f"{stem}-average.png"),
    )


def control_report_path(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}-stability.csv")


def reconstruction_title(base_title: str, diameter_cm: float | None = None) -> str:
    if diameter_cm is None:
        return base_title
    return f"{base_title} (diameter={diameter_cm:g} cm)"


def _draw_reconstruction(ax, eit_mesh, values: np.ndarray, title: str, limit: float):
    image = ax.tripcolor(
        eit_mesh.node[:, 0],
        eit_mesh.node[:, 1],
        eit_mesh.element,
        values,
        shading="flat",
        cmap="coolwarm",
        vmin=-limit,
        vmax=limit,
    )
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9)
    ax.set_axis_off()
    for index in range(base.N_ELECTRODES):
        angle = 2.0 * np.pi * index / base.N_ELECTRODES
        ax.text(
            1.12 * np.cos(angle),
            1.12 * np.sin(angle),
            f"E{index + 1}",
            ha="center",
            va="center",
            fontsize=6,
            fontweight="bold",
        )
    return image


def save_reconstruction_images(
    eit_mesh,
    reconstructions: list[np.ndarray],
    contact_path: Path,
    average_path: Path,
    pattern_label: str,
    diameter_cm: float | None = None,
) -> None:
    if not reconstructions:
        raise ValueError("No reconstructions are available to save")
    contact_path.parent.mkdir(parents=True, exist_ok=True)
    limit = max(float(np.max(np.abs(values))) for values in reconstructions)
    limit = max(limit, np.finfo(float).eps)

    fig, axes = base.plt.subplots(4, 5, figsize=(16, 12), constrained_layout=True)
    image = None
    flat_axes = list(axes.flat)
    for index, ax in enumerate(flat_axes):
        if index < len(reconstructions):
            image = _draw_reconstruction(
                ax,
                eit_mesh,
                reconstructions[index],
                f"Frame {index + 1}",
                limit,
            )
        else:
            ax.set_axis_off()
    fig.suptitle(
        reconstruction_title(f"Phase 3A {pattern_label} Reconstructions", diameter_cm),
        fontsize=16,
    )
    if image is not None:
        colorbar = fig.colorbar(image, ax=flat_axes, shrink=0.75)
        colorbar.set_label("Relative conductivity change")
    fig.savefig(contact_path, dpi=180)
    base.plt.close(fig)

    average_values = np.mean(np.stack(reconstructions), axis=0)
    average_limit = max(float(np.max(np.abs(average_values))), np.finfo(float).eps)
    avg_fig, avg_ax = base.plt.subplots(figsize=(8, 7), constrained_layout=True)
    avg_image = _draw_reconstruction(
        avg_ax,
        eit_mesh,
        average_values,
        f"Average of {len(reconstructions)} Frames",
        average_limit,
    )
    avg_colorbar = avg_fig.colorbar(avg_image, ax=avg_ax, shrink=0.8)
    avg_colorbar.set_label("Relative conductivity change")
    avg_fig.suptitle(
        reconstruction_title(
            f"Phase 3A {pattern_label} Average Reconstruction",
            diameter_cm,
        ),
        fontsize=15,
    )
    avg_fig.savefig(average_path, dpi=200)
    base.plt.close(avg_fig)


def read_one_v2_frame(ser: serial.Serial) -> UnifiedFrame:
    lines: list[str] = []
    in_frame = False
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        if line.startswith("FRAME,2,"):
            lines = [line]
            in_frame = True
            continue
        if in_frame:
            lines.append(line)
            if line.startswith("END,"):
                return parse_v2_frame(lines)


class RawFrameLogger:
    HEADER = [
        "run_id", "capture", "frame_id", "pattern", "polarity",
        "i_plus", "i_minus", "v_plus", "v_minus", "voltage_mv",
        "current_ua", "quality", "dac_code", "settle_ms", "sample_count",
    ]

    def __init__(self, path: Path, max_frames: int) -> None:
        self.path = path
        self.max_frames = max_frames
        self.frames_written = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(self.HEADER)

    def write(self, run_id: str, capture: str, frame: UnifiedFrame) -> None:
        if self.frames_written >= self.max_frames:
            return
        for record in frame.records:
            self._writer.writerow([
                run_id, capture, frame.frame_id, frame.pattern, record.polarity,
                base.index_to_electrode(record.i_pair[0]),
                base.index_to_electrode(record.i_pair[1]),
                base.index_to_electrode(record.v_pair[0]),
                base.index_to_electrode(record.v_pair[1]),
                f"{record.voltage_mv:.6f}", f"{record.current_ua:.6f}",
                record.quality, frame.dac_code, frame.settle_ms, frame.sample_count,
            ])
        self._handle.flush()
        self.frames_written += 1

    def close(self) -> None:
        self._handle.close()


def request_frame(ser: serial.Serial) -> UnifiedFrame:
    ser.write(b"s\n")
    return read_one_v2_frame(ser)


def assess_baseline_stability(vectors: list[np.ndarray]) -> BaselineStability:
    baseline = average_vectors(vectors)
    baseline_rms = float(np.sqrt(np.mean(baseline ** 2)))
    if baseline_rms == 0.0:
        return BaselineStability(False, float("inf"), float("inf"), 0.0)

    absolute_rms = [
        float(np.sqrt(np.mean((vector - baseline) ** 2)))
        for vector in vectors
    ]
    relative_rms = [100.0 * value / baseline_rms for value in absolute_rms]
    correlations: list[float] = []
    for vector in vectors:
        if np.std(vector) == 0.0 or np.std(baseline) == 0.0:
            correlations.append(1.0 if np.allclose(vector, baseline) else 0.0)
        else:
            correlations.append(float(np.corrcoef(vector, baseline)[0, 1]))

    max_relative_rms = max(relative_rms)
    max_absolute_rms = max(absolute_rms)
    min_correlation = min(correlations)
    stable_by_relative_shape = (
        max_relative_rms <= MAX_BASELINE_RELATIVE_RMS_PERCENT
        and min_correlation >= MIN_BASELINE_CORRELATION
    )
    stable_by_absolute_drift = max_absolute_rms <= MAX_BASELINE_ABSOLUTE_RMS_KOHM
    stable = stable_by_relative_shape or stable_by_absolute_drift
    return BaselineStability(
        stable,
        max_relative_rms,
        max_absolute_rms,
        min_correlation,
    )


def require_stable_baseline(vectors: list[np.ndarray]) -> BaselineStability:
    result = assess_baseline_stability(vectors)
    if not result.stable:
        raise ValueError(
            "Baseline is unstable: "
            f"max relative RMS={result.max_relative_rms_percent:.2f}% "
            f"(limit {MAX_BASELINE_RELATIVE_RMS_PERCENT:.2f}%), "
            f"max absolute RMS={result.max_absolute_rms_kohm:.6f} kOhm "
            f"(limit {MAX_BASELINE_ABSOLUTE_RMS_KOHM:.6f} kOhm), "
            f"minimum correlation={result.min_correlation:.5f} "
            f"(limit {MIN_BASELINE_CORRELATION:.5f}). "
            "Check electrode contact and rerun after the trunk has settled."
        )
    return result


def capture_vectors(
    ser: serial.Serial,
    protocol,
    count: int,
    expected_pattern: str,
    logger: RawFrameLogger | None,
    run_id: str,
    capture: str,
) -> list[np.ndarray]:
    vectors: list[np.ndarray] = []
    for index in range(1, count + 1):
        frame = request_frame(ser)
        if frame.pattern != expected_pattern:
            raise ValueError(
                f"Firmware returned {frame.pattern}, expected {expected_pattern}"
            )
        if logger is not None:
            logger.write(run_id, capture, frame)
        vector = frame_to_vector(frame, protocol)
        vectors.append(vector)
        currents = np.asarray([abs(record.current_ua) for record in frame.records])
        print(
            f"[{capture} {index}/{count}] frame={frame.frame_id} "
            f"measurements={len(vector)} current_median={np.median(currents):.2f}uA"
        )
    return vectors


def capture_average(
    ser: serial.Serial,
    protocol,
    count: int,
    expected_pattern: str,
    logger: RawFrameLogger | None,
    run_id: str,
    capture: str,
) -> np.ndarray:
    vectors = capture_vectors(
        ser, protocol, count, expected_pattern, logger, run_id, capture
    )
    return average_vectors(vectors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 3A unified forward/reverse current-normalized reconstruction"
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--pattern", choices=("adjacent", "opposite"), default="adjacent")
    parser.add_argument("--dac", type=int, default=100)
    parser.add_argument("--settle-ms", type=int, default=DEFAULT_SETTLE_MS)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--warmup-frames", type=int, default=DEFAULT_WARMUP_FRAMES)
    parser.add_argument("--baseline-frames", type=int, default=DEFAULT_BASELINE_FRAMES)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument(
        "--diameter-cm",
        type=float,
        default=None,
        help="Real trunk or phantom diameter in centimeters; used for plot/run labeling",
    )
    parser.add_argument("--startup-wait", type=float, default=1.5)
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--max-log-frames", type=int, default=30)
    parser.add_argument(
        "--control",
        action="store_true",
        help="Measure same-condition drift and save a stability report; do not reconstruct",
    )
    parser.add_argument(
        "--auto-continue",
        action="store_true",
        help="Do not pause between baseline and comparison capture",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dac < 0 or args.dac > 620:
        raise ValueError("--dac must be between 0 and 620")
    if min(args.baseline_frames, args.frames, args.samples, args.settle_ms) <= 0:
        raise ValueError("Frame, sample, and settling values must be positive")
    if args.warmup_frames < 0:
        raise ValueError("--warmup-frames cannot be negative")
    if args.diameter_cm is not None and args.diameter_cm <= 0:
        raise ValueError("--diameter-cm must be positive when provided")

    protocol, mode_command = protocol_and_command(args.pattern)
    eit_mesh, solver = base.create_solver(protocol)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    logger = None
    run_csv_path = Path(args.log_dir) / f"phase3a-v2-{args.pattern}-{run_id}.csv"
    if args.log:
        logger = RawFrameLogger(run_csv_path, args.max_log_frames)

    print(f"[Serial] Connecting to {args.port} at {args.baud} baud")
    ser = serial.Serial(args.port, args.baud, timeout=1.0)
    time.sleep(args.startup_wait)
    ser.reset_input_buffer()
    fig = None
    reconstructions: list[np.ndarray] = []

    try:
        ser.write(mode_command)
        ser.write(f"p{args.dac}\n".encode())
        ser.write(f"t{args.settle_ms}\n".encode())
        ser.write(f"n{args.samples}\n".encode())

        if args.warmup_frames:
            print(f"[Warmup] Discarding {args.warmup_frames} settling frames")
            capture_vectors(
                ser, protocol, args.warmup_frames, args.pattern,
                None, run_id, "warmup",
            )

        print(f"[Baseline] Capturing {args.baseline_frames} averaged frames")
        baseline_vectors = capture_vectors(
            ser, protocol, args.baseline_frames, args.pattern,
            logger, run_id, "baseline",
        )
        stability = require_stable_baseline(baseline_vectors)
        baseline = average_vectors(baseline_vectors)
        print(
            "[Baseline] Stable: "
            f"max_relative_rms={stability.max_relative_rms_percent:.2f}% "
            f"max_absolute_rms={stability.max_absolute_rms_kohm:.6f}kOhm "
            f"min_correlation={stability.min_correlation:.5f}"
        )

        if args.control:
            print(
                f"[Control] Capturing {args.frames} untouched frames; "
                "do not touch the trunk, electrodes, or wiring"
            )
            controls = capture_vectors(
                ser, protocol, args.frames, args.pattern,
                logger, run_id, "control",
            )
            report = analyze_control_drift(baseline, controls, protocol)
            report_path = control_report_path(run_csv_path)
            write_control_report(report_path, report)
            worst_frame = max(report.frames, key=lambda item: item.rms_kohm)
            print(
                f"[Control] Worst frame={worst_frame.frame} "
                f"relative_rms={worst_frame.relative_rms_percent:.2f}% "
                f"correlation={worst_frame.correlation:.5f}"
            )
            print("[Control] Most unstable electrodes:")
            for metric in report.electrodes[:5]:
                print(
                    f"  {base.index_to_electrode(metric.electrode)} "
                    f"mean_pair_rms={metric.mean_pair_rms_kohm:.6f} kOhm"
                )
            print("[Control] Most unstable measurement pairs:")
            for metric in report.pairs[:5]:
                print(
                    f"  I={base.index_to_electrode(metric.i_pair[0])}-"
                    f"{base.index_to_electrode(metric.i_pair[1])} "
                    f"V={base.index_to_electrode(metric.v_pair[0])}-"
                    f"{base.index_to_electrode(metric.v_pair[1])} "
                    f"rms={metric.rms_kohm:.6f} kOhm"
                )
            print(f"[Control] Stability report saved to {report_path}")
        else:
            wait_for_target(args.auto_continue)

            fig, ax = base.create_reconstruction_plot()
            print(f"[Run] Capturing {args.frames} comparison frames")
            for frame_index in range(1, args.frames + 1):
                current = capture_average(
                    ser, protocol, 1, args.pattern,
                    logger, run_id, f"comparison-{frame_index}",
                )
                ds = base.reconstruct_difference(baseline, current, solver)
                reconstructions.append(ds)
                delta_rms = float(np.sqrt(np.mean((current - baseline) ** 2)))
                print(
                    f"[Frame {frame_index}/{args.frames}] "
                    f"transfer_delta_rms={delta_rms:.6f} kOhm"
                )
                base.update_reconstruction_plot(
                    fig,
                    ax,
                    eit_mesh,
                    ds,
                    reconstruction_title(
                        f"Phase 3A {args.pattern.title()} V2 Reconstruction",
                        args.diameter_cm,
                    ),
                )
            print("[Complete] Close the plot window to exit")
    except KeyboardInterrupt:
        print("\n[Stopped]")
    finally:
        ser.write(b"x\n")
        ser.close()
        if logger is not None:
            logger.close()
            print(f"[Log] saved {logger.frames_written} frames to {logger.path}")

    if reconstructions:
        contact_path, average_path = reconstruction_image_paths(run_csv_path)
        save_reconstruction_images(
            eit_mesh,
            reconstructions,
            contact_path,
            average_path,
            args.pattern.title(),
            args.diameter_cm,
        )
        print(f"[Images] saved contact sheet to {contact_path}")
        print(f"[Images] saved average reconstruction to {average_path}")

    if fig is not None:
        base.plt.ioff()
        base.plt.show()


if __name__ == "__main__":
    main()
