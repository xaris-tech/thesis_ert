"""Live reconstruction for the Phase 3A unified v2 ERT firmware."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Iterable
import warnings

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
MAX_RECON_BASELINE_PAIR_RMS_KOHM = 0.03
MAX_RECON_PAIR_DELTA_KOHM = 0.05
MIN_RECON_KEPT_PAIR_RATIO = 0.75
RECIPROCITY_THRESHOLD_PERCENT = 10.0

# Mirrors MIN_CURRENT_UA in the unified firmware. A measurement below this is
# flagged I_LOW by the firmware, and a single I_LOW aborts a strict capture, so
# the minimum current across a frame is what predicts whether a long run
# survives.
FIRMWARE_MIN_CURRENT_UA = 1.0
# Ratio of first to last current within one injection pair. Above this the
# current is decaying across a fixed drive pair, which indicates electrode
# polarisation rather than a real impedance change.
MAX_POLARIZATION_DECAY_RATIO = 1.5
# Polarisation is a monotonic slide, so a large first-to-last ratio only counts
# when most steps actually decrease. Without this a noisy non-monotonic pair got
# reported as polarisation (validity-audit X-04).
MIN_POLARIZATION_DECREASING_FRACTION = 0.6
# Ratio of common-mode to differential voltage across a forward/reverse pair.
# Above this the static electrode half-cell potential is larger than the
# injected signal, and the forward/reverse difference cancels to near zero.
MAX_OFFSET_COMMON_RATIO = 1.0


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


@dataclass(frozen=True)
class PairHealthScore:
    index: int
    i_pair: tuple[int, int]
    v_pair: tuple[int, int]
    baseline_rms_kohm: float
    max_abs_kohm: float


@dataclass(frozen=True)
class FrameHealthScore:
    kept_pairs: int
    dropped_pairs: int
    kept_ratio: float
    current_median_ua: float
    current_spread_ua: float
    quality_label: str


@dataclass(frozen=True)
class FilteredVectorResult:
    filtered_vector: np.ndarray
    dropped_indexes: list[int]
    kept_indexes: list[int]
    frame_health: FrameHealthScore


def parse_header(line: str) -> tuple[int, str, int, int, int]:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 10 or parts[0] != "FRAME" or parts[1] != "2":
        raise ValueError(f"Unsupported frame header: {line}")
    if parts[4] != "DAC" or parts[6] != "SETTLE" or parts[8] != "SAMPLES":
        raise ValueError(f"Malformed frame header: {line}")
    pattern = parts[3].lower()
    if pattern not in {"adjacent", "opposite", "skip-1", "skip-2"}:
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


def record_is_valid(record: MeasurementRecord) -> bool:
    return record.quality == "OK" and abs(record.current_ua) >= MIN_VALID_CURRENT_UA


def validate_record(record: MeasurementRecord) -> None:
    if record.quality != "OK":
        raise ValueError(f"Measurement quality is {record.quality}")
    if abs(record.current_ua) < MIN_VALID_CURRENT_UA:
        raise ValueError("Measured current is too close to zero")


def canonical_measurement_key(
    record: MeasurementRecord,
) -> tuple[tuple[int, int], tuple[int, int]]:
    if record.polarity == "FWD":
        return (record.i_pair, record.v_pair)
    return ((record.i_pair[1], record.i_pair[0]), record.v_pair)


def paired_transfer_resistance(
    frame: UnifiedFrame,
    strict: bool = True,
) -> dict[tuple[tuple[int, int], tuple[int, int]], float]:
    """Forward/reverse averaged transfer resistance, keyed by canonical pair.

    In strict mode any non-OK record raises, which is the behaviour the CLI
    capture path depends on. In lenient mode bad records are skipped and only
    pairs that still have both polarities are returned, so one weak measurement
    costs a single pair instead of the whole capture.
    """
    forward: dict[tuple[tuple[int, int], tuple[int, int]], MeasurementRecord] = {}
    reverse: dict[tuple[tuple[int, int], tuple[int, int]], MeasurementRecord] = {}

    for record in frame.records:
        if strict:
            validate_record(record)
        elif not record_is_valid(record):
            continue
        key = canonical_measurement_key(record)
        if record.polarity == "FWD":
            forward[key] = record
        else:
            reverse[key] = record

    if strict and forward.keys() != reverse.keys():
        missing_reverse = sorted(forward.keys() - reverse.keys())
        missing_forward = sorted(reverse.keys() - forward.keys())
        raise ValueError(
            f"Forward/reverse mismatch; missing reverse={missing_reverse[:3]} "
            f"missing forward={missing_forward[:3]}"
        )

    result: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}
    for key in forward.keys() & reverse.keys():
        fwd = forward[key]
        rev = reverse[key]
        fwd_resistance = fwd.voltage_mv / abs(fwd.current_ua)
        rev_resistance = rev.voltage_mv / abs(rev.current_ua)
        # mV/uA is numerically kOhm. Reverse voltage has opposite physical sign.
        #
        # The leading minus reconciles two conventions (validity-audit D-02):
        # the firmware measures ADS A0-A1, which is V_vp - V_vn, while
        # build_protocol stores rows as [vn, vp] and PyEIT's subtract_row
        # computes v[meas[:,0]] - v[meas[:,1]] = V_vn - V_vp. Without this the
        # whole vector reaches the solver negated and a more conductive target
        # renders blue.
        result[key] = -0.5 * (fwd_resistance - rev_resistance)
    return result


def reciprocity_errors(
    values: dict[tuple[tuple[int, int], tuple[int, int]], float],
) -> dict[tuple[tuple[int, int], tuple[int, int]], float]:
    """Percent error between each measurement and its reciprocal.

    Reciprocity: (I:A,B / V:C,D) should equal (I:C,D / V:A,B). Only pairs whose
    reciprocal was also captured in this frame are scored; each reciprocal
    pair is reported once, keyed by whichever orientation was seen first.
    """
    errors: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}
    seen: set[tuple[tuple, tuple]] = set()
    for key, value in values.items():
        i_pair, v_pair = key
        reciprocal_key = (v_pair, i_pair)
        if reciprocal_key not in values:
            continue
        canonical = tuple(sorted((key, reciprocal_key)))
        if canonical in seen:
            continue
        seen.add(canonical)
        other = values[reciprocal_key]
        denom = max((abs(value) + abs(other)) / 2.0, 1e-9)
        errors[key] = abs(value - other) / denom * 100.0
    return errors


def filter_by_reciprocity(
    values: dict[tuple[tuple[int, int], tuple[int, int]], float],
    threshold_percent: float = RECIPROCITY_THRESHOLD_PERCENT,
) -> tuple[dict[tuple[tuple[int, int], tuple[int, int]], float], list[tuple[tuple[int, int], tuple[int, int]]]]:
    """Drop both members of any reciprocal pair whose error exceeds threshold."""
    errors = reciprocity_errors(values)
    kept = dict(values)
    dropped: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for key, error in errors.items():
        if error > threshold_percent:
            i_pair, v_pair = key
            kept.pop(key, None)
            kept.pop((v_pair, i_pair), None)
            dropped.append(key)
    return kept, dropped


def protocol_and_command(pattern: str):
    normalized = pattern.lower()
    if normalized == "adjacent":
        return base.build_adjacent_protocol(), b"ma\n"
    if normalized == "opposite":
        return base.build_opposite_protocol(), b"mo\n"
    if normalized == "skip-1":
        return base.build_skip_one_protocol(), b"ms\n"
    if normalized == "skip-2":
        return base.build_skip_two_protocol(), b"mk\n"
    raise ValueError(f"Unsupported pattern: {pattern}")


def remap_electrode(
    index: int,
    offset: int = 0,
    reversed_ring: bool = False,
    n_el: int = base.N_ELECTRODES,
) -> int:
    """Map a wired electrode index onto the mesh's index order.

    The firmware reports electrodes as they are physically wired. If the ring
    was installed running the opposite way round, or starting at a different
    electrode, every reconstruction comes out mirrored or rotated by a fixed
    amount, with the image data itself perfectly good. Both defaults are the
    identity mapping.
    """
    if reversed_ring:
        return (offset - index) % n_el
    return (index + offset) % n_el


def remap_measurement_key(
    key: tuple[tuple[int, int], tuple[int, int]],
    offset: int = 0,
    reversed_ring: bool = False,
    n_el: int = base.N_ELECTRODES,
) -> tuple[tuple[int, int], tuple[int, int]]:
    i_pair, v_pair = key
    mapped = lambda index: remap_electrode(index, offset, reversed_ring, n_el)
    return (
        (mapped(i_pair[0]), mapped(i_pair[1])),
        (mapped(v_pair[0]), mapped(v_pair[1])),
    )


def frame_to_vector(
    frame: UnifiedFrame,
    protocol,
    strict: bool = True,
    electrode_offset: int = 0,
    electrode_reversed: bool = False,
) -> np.ndarray:
    """Vector of transfer resistances ordered to match the protocol.

    In lenient mode a measurement the firmware flagged bad becomes NaN rather
    than raising; use fill_missing_values() to substitute a reference before
    handing the vector to the solver.
    """
    values_by_key = paired_transfer_resistance(frame, strict=strict)
    if electrode_offset or electrode_reversed:
        values_by_key = {
            remap_measurement_key(key, electrode_offset, electrode_reversed): value
            for key, value in values_by_key.items()
        }
    values: list[float] = []
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        i_pair = (int(ex_pair[0]), int(ex_pair[1]))
        for meas_pair in protocol.meas_mat[ex_index]:
            v_pair = (int(meas_pair[1]), int(meas_pair[0]))
            try:
                values.append(values_by_key[(i_pair, v_pair)])
            except KeyError as exc:
                if not strict:
                    values.append(float("nan"))
                    continue
                raise ValueError(
                    f"Missing normalized measurement I={i_pair} V={v_pair}; "
                    f"frame pattern is {frame.pattern}"
                ) from exc
    return np.asarray(values, dtype=float)


def missing_value_indexes(vector: np.ndarray) -> list[int]:
    return [int(index) for index in np.flatnonzero(np.isnan(vector))]


def fill_missing_values(vector: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Replace NaN entries with the reference value at the same index."""
    if vector.shape != reference.shape:
        raise ValueError("Vector and reference must share the same shape")
    filled = np.array(vector, copy=True)
    missing = np.isnan(filled)
    filled[missing] = reference[missing]
    return filled


def average_vectors(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise ValueError("At least one vector is required")
    expected_shape = vectors[0].shape
    if any(vector.shape != expected_shape for vector in vectors):
        raise ValueError("All vectors must have the same shape")
    stacked = np.stack(vectors)
    if not np.isnan(stacked).any():
        return np.mean(stacked, axis=0)
    # Lenient captures leave NaN where a measurement was dropped; average over
    # whatever frames did measure that pair. A pair no frame measured stays NaN,
    # which the caller is expected to detect rather than silently accept.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(stacked, axis=0)


def protocol_vector_keys(protocol) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    keys: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        i_pair = (int(ex_pair[0]), int(ex_pair[1]))
        for meas_pair in protocol.meas_mat[ex_index]:
            keys.append((i_pair, (int(meas_pair[1]), int(meas_pair[0]))))
    return keys


def analyze_baseline_pair_health(
    baseline_vectors: list[np.ndarray],
    protocol,
) -> list[PairHealthScore]:
    baseline = average_vectors(baseline_vectors)
    deltas = np.stack([vector - baseline for vector in baseline_vectors])
    pair_rms = np.sqrt(np.mean(deltas ** 2, axis=0))
    pair_max = np.max(np.abs(deltas), axis=0)
    keys = protocol_vector_keys(protocol)
    scores = [
        PairHealthScore(
            index=index,
            i_pair=key[0],
            v_pair=key[1],
            baseline_rms_kohm=float(pair_rms[index]),
            max_abs_kohm=float(pair_max[index]),
        )
        for index, key in enumerate(keys)
    ]
    scores.sort(key=lambda item: item.baseline_rms_kohm, reverse=True)
    return scores


def filter_frame_vector_best_effort(
    baseline: np.ndarray,
    current: np.ndarray,
    pair_scores: list[PairHealthScore],
    current_median_ua: float,
    current_spread_ua: float = 0.0,
) -> FilteredVectorResult:
    if baseline.shape != current.shape:
        raise ValueError("Baseline and current vectors must share the same shape")

    filtered = np.array(current, copy=True)
    dropped_indexes: list[int] = []
    kept_indexes: list[int] = []

    for score in pair_scores:
        delta = abs(float(current[score.index] - baseline[score.index]))
        unstable_baseline = score.baseline_rms_kohm > MAX_RECON_BASELINE_PAIR_RMS_KOHM
        unstable_delta = delta > MAX_RECON_PAIR_DELTA_KOHM
        if unstable_baseline or unstable_delta:
            filtered[score.index] = baseline[score.index]
            dropped_indexes.append(score.index)
        else:
            kept_indexes.append(score.index)

    kept_pairs = len(kept_indexes)
    dropped_pairs = len(dropped_indexes)
    total_pairs = len(pair_scores)
    kept_ratio = kept_pairs / total_pairs if total_pairs else 0.0
    quality_label = "ok"
    if dropped_pairs:
        quality_label = "debug-best-effort"
    if kept_ratio < MIN_RECON_KEPT_PAIR_RATIO:
        quality_label = "debug-low-confidence"

    frame_health = FrameHealthScore(
        kept_pairs=kept_pairs,
        dropped_pairs=dropped_pairs,
        kept_ratio=kept_ratio,
        current_median_ua=float(current_median_ua),
        current_spread_ua=float(current_spread_ua),
        quality_label=quality_label,
    )
    return FilteredVectorResult(filtered, dropped_indexes, kept_indexes, frame_health)


def summarize_top_unstable_pairs(
    pair_scores: list[PairHealthScore],
    limit: int = 5,
) -> str:
    summary: list[str] = []
    for score in pair_scores[:limit]:
        summary.append(
            f"I={base.index_to_electrode(score.i_pair[0])}-{base.index_to_electrode(score.i_pair[1])} "
            f"V={base.index_to_electrode(score.v_pair[0])}-{base.index_to_electrode(score.v_pair[1])} "
            f"rms={score.baseline_rms_kohm:.6f}kOhm"
        )
    return "; ".join(summary)


@dataclass(frozen=True)
class FrameProbe:
    min_current_ua: float
    min_current_polarity: str
    min_current_i_pair: tuple[int, int]
    min_current_v_pair: tuple[int, int]
    median_current_ua: float
    margin_ratio: float
    quality_counts: dict[str, int]
    total_records: int

    @property
    def passes(self) -> bool:
        return self.margin_ratio >= 1.0 and set(self.quality_counts) <= {"OK"}


@dataclass(frozen=True)
class PolarizationMetric:
    i_pair: tuple[int, int]
    polarity: str
    first_current_ua: float
    last_current_ua: float
    decay_ratio: float
    decreasing_fraction: float
    sample_count: int


@dataclass(frozen=True)
class PolarizationReport:
    metrics: list[PolarizationMetric]
    worst_decay_ratio: float
    flagged_groups: int

    @property
    def flagged(self) -> bool:
        return self.flagged_groups > 0


@dataclass(frozen=True)
class OffsetPairMetric:
    i_pair: tuple[int, int]
    v_pair: tuple[int, int]
    forward_mv: float
    reverse_mv: float
    differential_mv: float
    common_mv: float
    common_ratio: float


@dataclass(frozen=True)
class OffsetReport:
    pairs: list[OffsetPairMetric]
    dominated_pairs: int
    total_pairs: int

    @property
    def dominated_fraction(self) -> float:
        return self.dominated_pairs / self.total_pairs if self.total_pairs else 0.0

    @property
    def flagged(self) -> bool:
        return self.dominated_pairs > 0


@dataclass(frozen=True)
class ElectrodeHealth:
    electrode: int
    drive_median_ua: float
    drive_count: int
    sense_median_abs_mv: float
    sense_count: int
    bad_quality_count: int


def probe_frame_health(frame: UnifiedFrame) -> FrameProbe:
    """Cheap single-frame screen: does the weakest measurement clear the floor?

    The minimum current across the frame, not the average, decides whether a
    long capture survives, because one measurement under the firmware's
    I_LOW threshold aborts a strict run.
    """
    if not frame.records:
        raise ValueError("Frame contains no measurements")

    currents = np.asarray([abs(record.current_ua) for record in frame.records])
    weakest_index = int(np.argmin(currents))
    weakest = frame.records[weakest_index]

    quality_counts: dict[str, int] = {}
    for record in frame.records:
        quality_counts[record.quality] = quality_counts.get(record.quality, 0) + 1

    min_current = float(currents[weakest_index])
    return FrameProbe(
        min_current_ua=min_current,
        min_current_polarity=weakest.polarity,
        min_current_i_pair=weakest.i_pair,
        min_current_v_pair=weakest.v_pair,
        median_current_ua=float(np.median(currents)),
        margin_ratio=min_current / FIRMWARE_MIN_CURRENT_UA,
        quality_counts=quality_counts,
        total_records=len(frame.records),
    )


def analyze_polarization(frame: UnifiedFrame) -> PolarizationReport:
    """Detect current decaying across a fixed injection pair.

    Current must not depend on which unrelated pair is being voltage-sensed, so
    a monotonic slide across successive measurements of one injection pair is
    time-dependent electrode polarisation, not a real impedance change.
    """
    groups: dict[tuple[tuple[int, int], str], list[float]] = {}
    for record in frame.records:
        key = (canonical_measurement_key(record)[0], record.polarity)
        groups.setdefault(key, []).append(abs(record.current_ua))

    metrics: list[PolarizationMetric] = []
    for (i_pair, polarity), currents in groups.items():
        if len(currents) < 2:
            continue
        first = currents[0]
        last = currents[-1]
        decay_ratio = first / last if last > 0.0 else float("inf")
        steps = np.diff(np.asarray(currents))
        decreasing_fraction = float(np.mean(steps < 0.0)) if steps.size else 0.0
        metrics.append(
            PolarizationMetric(
                i_pair=i_pair,
                polarity=polarity,
                first_current_ua=float(first),
                last_current_ua=float(last),
                decay_ratio=float(decay_ratio),
                decreasing_fraction=decreasing_fraction,
                sample_count=len(currents),
            )
        )

    metrics.sort(key=lambda item: item.decay_ratio, reverse=True)
    flagged = sum(
        1
        for metric in metrics
        if metric.decay_ratio > MAX_POLARIZATION_DECAY_RATIO
        and metric.decreasing_fraction >= MIN_POLARIZATION_DECREASING_FRACTION
    )
    worst = metrics[0].decay_ratio if metrics else 1.0
    return PolarizationReport(metrics, worst, flagged)


def analyze_offset_domination(frame: UnifiedFrame) -> OffsetReport:
    """Detect forward/reverse voltages that fail to invert.

    Reversing the injected current must invert an IR drop. When the common-mode
    part (V_fwd + V_rev) outweighs the differential part (V_fwd - V_rev), the
    reading is dominated by static electrode half-cell potential and
    paired_transfer_resistance() cancels toward zero.
    """
    forward: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}
    reverse: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}
    for record in frame.records:
        key = canonical_measurement_key(record)
        if record.polarity == "FWD":
            forward[key] = record.voltage_mv
        else:
            reverse[key] = record.voltage_mv

    pairs: list[OffsetPairMetric] = []
    for key in sorted(forward.keys() & reverse.keys()):
        fwd = forward[key]
        rev = reverse[key]
        differential = abs(fwd - rev)
        common = abs(fwd + rev)
        ratio = common / differential if differential > 0.0 else float("inf")
        pairs.append(
            OffsetPairMetric(
                i_pair=key[0],
                v_pair=key[1],
                forward_mv=fwd,
                reverse_mv=rev,
                differential_mv=differential,
                common_mv=common,
                common_ratio=ratio,
            )
        )

    pairs.sort(key=lambda item: item.common_ratio, reverse=True)
    dominated = sum(1 for pair in pairs if pair.common_ratio > MAX_OFFSET_COMMON_RATIO)
    return OffsetReport(pairs, dominated, len(pairs))


def analyze_electrode_health(
    frame: UnifiedFrame,
    n_el: int = base.N_ELECTRODES,
) -> list[ElectrodeHealth]:
    drive: dict[int, list[float]] = {index: [] for index in range(n_el)}
    sense: dict[int, list[float]] = {index: [] for index in range(n_el)}
    bad: dict[int, int] = {index: 0 for index in range(n_el)}

    for record in frame.records:
        for electrode in record.i_pair:
            if electrode in drive:
                drive[electrode].append(abs(record.current_ua))
        for electrode in record.v_pair:
            if electrode in sense:
                sense[electrode].append(abs(record.voltage_mv))
        if record.quality != "OK":
            for electrode in set(record.i_pair) | set(record.v_pair):
                if electrode in bad:
                    bad[electrode] += 1

    return [
        ElectrodeHealth(
            electrode=index,
            drive_median_ua=float(np.median(drive[index])) if drive[index] else 0.0,
            drive_count=len(drive[index]),
            sense_median_abs_mv=float(np.median(sense[index])) if sense[index] else 0.0,
            sense_count=len(sense[index]),
            bad_quality_count=bad[index],
        )
        for index in range(n_el)
    ]


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
        input_fn(
            "[Target] Place the target without moving electrodes. Let the tank "
            "settle 5-10 minutes (or pass --target-settle-s), then press Enter..."
        )


def reconstruction_image_paths(csv_path: Path) -> tuple[Path, Path]:
    stem = csv_path.stem
    return (
        csv_path.with_name(f"{stem}-reconstructions.png"),
        csv_path.with_name(f"{stem}-average.png"),
    )


def control_report_path(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}-stability.csv")


def reciprocity_report_path(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}-reciprocity.csv")


def average_measurement_values(
    frames: list[dict[tuple[tuple[int, int], tuple[int, int]], float]],
) -> dict[tuple[tuple[int, int], tuple[int, int]], float]:
    """Average per-key transfer resistance across frames that saw that key."""
    sums: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}
    counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
    for values in frames:
        for key, value in values.items():
            sums[key] = sums.get(key, 0.0) + value
            counts[key] = counts.get(key, 0) + 1
    return {key: sums[key] / counts[key] for key in sums}


def write_reciprocity_report(
    path: Path,
    errors: dict[tuple[tuple[int, int], tuple[int, int]], float],
    threshold_percent: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "i_plus", "i_minus", "v_plus", "v_minus",
            "percent_error", "threshold_percent", "status",
        ])
        for (i_pair, v_pair), error in sorted(
            errors.items(), key=lambda item: item[1], reverse=True
        ):
            writer.writerow([
                base.index_to_electrode(i_pair[0]), base.index_to_electrode(i_pair[1]),
                base.index_to_electrode(v_pair[0]), base.index_to_electrode(v_pair[1]),
                f"{error:.4f}", f"{threshold_percent:.4f}",
                "FAIL" if error > threshold_percent else "OK",
            ])


def consistency_report_path(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}-consistency.csv")


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
    for index, x, y in base.electrode_label_positions(eit_mesh):
        ax.text(
            x,
            y,
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
    fixed_limit: float | None = None,
) -> None:
    if not reconstructions:
        raise ValueError("No reconstructions are available to save")
    contact_path.parent.mkdir(parents=True, exist_ok=True)
    if fixed_limit is not None:
        limit = fixed_limit
    else:
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
    if fixed_limit is not None:
        average_limit = fixed_limit
    else:
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


def write_consistency_report(
    path: Path,
    pair_scores: list[PairHealthScore],
    frame_healths: list[FrameHealthScore],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "record_type", "rank", "frame", "i_plus", "i_minus", "v_plus",
            "v_minus", "baseline_rms_kohm", "max_abs_kohm", "kept_pairs",
            "dropped_pairs", "kept_ratio", "current_median_ua",
            "current_spread_ua", "quality_label",
        ])
        for frame_index, metric in enumerate(frame_healths, start=1):
            writer.writerow([
                "frame", "", frame_index, "", "", "", "", "", "",
                metric.kept_pairs, metric.dropped_pairs, f"{metric.kept_ratio:.6f}",
                f"{metric.current_median_ua:.6f}", f"{metric.current_spread_ua:.6f}",
                metric.quality_label,
            ])
        for rank, score in enumerate(pair_scores, start=1):
            writer.writerow([
                "pair", rank, "", base.index_to_electrode(score.i_pair[0]),
                base.index_to_electrode(score.i_pair[1]),
                base.index_to_electrode(score.v_pair[0]),
                base.index_to_electrode(score.v_pair[1]),
                f"{score.baseline_rms_kohm:.9f}", f"{score.max_abs_kohm:.9f}",
                "", "", "", "", "", "",
            ])


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


def discard_warmup_frames(
    ser: serial.Serial,
    count: int,
    expected_pattern: str,
) -> None:
    for index in range(1, count + 1):
        frame = request_frame(ser)
        if frame.pattern != expected_pattern:
            raise ValueError(
                f"Firmware returned {frame.pattern}, expected {expected_pattern}"
            )
        currents = np.asarray([abs(record.current_ua) for record in frame.records])
        qualities = sorted({record.quality for record in frame.records})
        print(
            f"[warmup {index}/{count}] frame={frame.frame_id} "
            f"current_median={np.median(currents):.2f}uA "
            f"qualities={','.join(qualities)}"
        )


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
    # Stability is decided on shape alone (validity-audit D-03). The absolute
    # arm used to be OR-ed in here, which let an offset-dominated rig - whose
    # transfer resistances collapse toward zero - clear a flat 2 ohm threshold
    # while failing the shape test outright, reporting a baseline with no signal
    # in it as stable. AND-ing it instead fails legitimate baselines, because a
    # 1 percent drift on a 2 kOhm signal is already 20 ohm absolute: the
    # threshold tracks drive level, not quality. The value is still reported for
    # diagnostics.
    stable = stable_by_relative_shape
    return BaselineStability(
        stable,
        max_relative_rms,
        max_absolute_rms,
        min_correlation,
    )


def require_stable_baseline(
    vectors: list[np.ndarray],
    allow_unstable: bool = False,
) -> BaselineStability:
    result = assess_baseline_stability(vectors)
    if not result.stable:
        if allow_unstable:
            return result
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
    reciprocity_sink: list[dict[tuple[tuple[int, int], tuple[int, int]], float]] | None = None,
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
        if reciprocity_sink is not None:
            reciprocity_sink.append(paired_transfer_resistance(frame, strict=False))
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
    parser.add_argument("--pattern", choices=("adjacent", "opposite", "skip-1", "skip-2"), default="adjacent")
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
    parser.add_argument(
        "--colorbar-limit",
        type=float,
        default=None,
        help=(
            "Pin reconstruction colorbars to +/- this value (relative conductivity "
            "change) instead of auto-scaling to each run's own max. Set this to a "
            "fixed value shared across a run set before comparing images between runs "
            "-- otherwise a noise-only run and a strong-signal run render with the "
            "same visual saturation."
        ),
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
    parser.add_argument(
        "--allow-unstable-baseline",
        action="store_true",
        help="Bypass the baseline stability gate temporarily and continue anyway",
    )
    parser.add_argument(
        "--reciprocity-threshold-pct",
        type=float,
        default=RECIPROCITY_THRESHOLD_PERCENT,
        help=(
            "Max allowed percent error between a measurement and its reciprocal "
            "(I:A,B/V:C,D vs I:C,D/V:A,B) computed on the baseline capture. "
            "Reported to a CSV, not used to reject the run."
        ),
    )
    parser.add_argument(
        "--target-settle-s",
        type=float,
        default=0.0,
        help=(
            "Seconds to wait after the target-placement prompt before capturing "
            "target frames, letting the tank settle (recommend 300-600s after "
            "inserting/moving a target)"
        ),
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
    if args.colorbar_limit is not None and args.colorbar_limit <= 0:
        raise ValueError("--colorbar-limit must be positive when provided")
    if args.reciprocity_threshold_pct <= 0:
        raise ValueError("--reciprocity-threshold-pct must be positive")
    if args.target_settle_s < 0:
        raise ValueError("--target-settle-s cannot be negative")

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
    frame_healths: list[FrameHealthScore] = []

    try:
        ser.write(mode_command)
        ser.write(f"p{args.dac}\n".encode())
        ser.write(f"t{args.settle_ms}\n".encode())
        ser.write(f"n{args.samples}\n".encode())

        if args.warmup_frames:
            print(f"[Warmup] Discarding {args.warmup_frames} settling frames")
            discard_warmup_frames(ser, args.warmup_frames, args.pattern)

        print(f"[Baseline] Capturing {args.baseline_frames} averaged frames")
        baseline_reciprocity_frames: list[dict[tuple[tuple[int, int], tuple[int, int]], float]] = []
        baseline_vectors = capture_vectors(
            ser, protocol, args.baseline_frames, args.pattern,
            logger, run_id, "baseline",
            reciprocity_sink=baseline_reciprocity_frames,
        )
        reciprocity_values = average_measurement_values(baseline_reciprocity_frames)
        reciprocity_scores = reciprocity_errors(reciprocity_values)
        if reciprocity_scores:
            failing = sum(
                1 for error in reciprocity_scores.values()
                if error > args.reciprocity_threshold_pct
            )
            worst_key = max(reciprocity_scores, key=reciprocity_scores.get)
            print(
                f"[Reciprocity] {len(reciprocity_scores)} scored pairs, "
                f"{failing} above {args.reciprocity_threshold_pct:.1f}% threshold, "
                f"worst={reciprocity_scores[worst_key]:.2f}% "
                f"(I={base.index_to_electrode(worst_key[0][0])}-{base.index_to_electrode(worst_key[0][1])} "
                f"V={base.index_to_electrode(worst_key[1][0])}-{base.index_to_electrode(worst_key[1][1])})"
            )
            reciprocity_path = reciprocity_report_path(run_csv_path)
            write_reciprocity_report(reciprocity_path, reciprocity_scores, args.reciprocity_threshold_pct)
            print(f"[Reciprocity] saved report to {reciprocity_path}")
        else:
            print("[Reciprocity] no reciprocal pairs found in this pattern/mesh")
        stability = require_stable_baseline(
            baseline_vectors,
            allow_unstable=args.allow_unstable_baseline,
        )
        baseline = average_vectors(baseline_vectors)
        baseline_status = "Stable" if stability.stable else "UNSTABLE - BYPASSED"
        print(
            f"[Baseline] {baseline_status}: "
            f"max_relative_rms={stability.max_relative_rms_percent:.2f}% "
            f"max_absolute_rms={stability.max_absolute_rms_kohm:.6f}kOhm "
            f"min_correlation={stability.min_correlation:.5f}"
        )
        baseline_pair_scores = analyze_baseline_pair_health(baseline_vectors, protocol)
        print(
            "[Baseline] Top unstable pairs: "
            f"{summarize_top_unstable_pairs(baseline_pair_scores)}"
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
            if args.target_settle_s > 0:
                print(f"[Target] Settling {args.target_settle_s:.0f}s before capture")
                time.sleep(args.target_settle_s)

            fig, ax = base.create_reconstruction_plot()
            print(f"[Run] Capturing {args.frames} comparison frames")
            for frame_index in range(1, args.frames + 1):
                frame = request_frame(ser)
                if frame.pattern != args.pattern:
                    raise ValueError(
                        f"Firmware returned {frame.pattern}, expected {args.pattern}"
                    )
                if logger is not None:
                    logger.write(run_id, f"comparison-{frame_index}", frame)
                current = frame_to_vector(frame, protocol)
                currents = np.asarray([abs(record.current_ua) for record in frame.records])
                filtered = filter_frame_vector_best_effort(
                    baseline=baseline,
                    current=current,
                    pair_scores=baseline_pair_scores,
                    current_median_ua=float(np.median(currents)),
                    current_spread_ua=float(np.max(currents) - np.min(currents)),
                )
                frame_healths.append(filtered.frame_health)
                ds = base.reconstruct_difference(baseline, filtered.filtered_vector, solver)
                reconstructions.append(ds)
                delta_rms = float(np.sqrt(np.mean((filtered.filtered_vector - baseline) ** 2)))
                print(
                    f"[Frame {frame_index}/{args.frames}] "
                    f"transfer_delta_rms={delta_rms:.6f} kOhm "
                    f"kept={filtered.frame_health.kept_pairs}/{len(baseline_pair_scores)} "
                    f"quality={filtered.frame_health.quality_label}"
                )
                base.update_reconstruction_plot(
                    fig,
                    ax,
                    eit_mesh,
                    ds,
                    reconstruction_title(
                        f"Phase 3A {args.pattern.title()} V2 Reconstruction "
                        f"[{filtered.frame_health.quality_label}]",
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
            if frame_healths:
                report_path = consistency_report_path(logger.path)
                write_consistency_report(
                    report_path,
                    baseline_pair_scores,
                    frame_healths,
                )
                print(f"[Consistency] saved report to {report_path}")

    if reconstructions:
        contact_path, average_path = reconstruction_image_paths(run_csv_path)
        save_reconstruction_images(
            eit_mesh,
            reconstructions,
            contact_path,
            average_path,
            args.pattern.title(),
            args.diameter_cm,
            args.colorbar_limit,
        )
        print(f"[Images] saved contact sheet to {contact_path}")
        print(f"[Images] saved average reconstruction to {average_path}")

    if fig is not None:
        base.plt.ioff()
        base.plt.show()


if __name__ == "__main__":
    main()
