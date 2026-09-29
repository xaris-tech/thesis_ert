"""Intact-disc survey: how far specimens differ, against how far a defect moves one.

ADR-0035 decided the question and left the arithmetic unwritten; ADR-0038 records
the choices made here. The survey compares **normalised measurement vectors**:
each run's 108 transfer resistances divided by their own mean magnitude. For a
roughly circular specimen that cancels resistivity and size exactly and leaves
the angular arrangement, so two healthy discs of different wetness or diameter
should land close together, and a drilled disc should land far from its own
intact self. No solver is involved, so nothing here inherits the circular-mesh
assumption the images carry.

Three spreads, always reported separately (ADR-0035):

``S_noise``    one specimen rescanned untouched -- the floor
``S_between``  different intact specimens against each other
``S_defect``   one specimen before and after drilling

A spread is a root-mean-square distance between normalised vectors, over the
cells both vectors have, as a percentage of the mean transfer resistance.

The contrast metrics (max/min ratio, spread) compare a run only with itself.
They are computed on apparent resistivity -- each transfer resistance divided by
what a homogeneous disc would give on the same pair -- because the raw ratio on
an adjacent pattern is dominated by geometry: near pairs read many times the far
pairs on a perfectly uniform specimen.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
import run_record
from tree_ert.reconstruction import MEASUREMENT_SETTINGS, SettingsMismatch

STATE_INTACT = "intact"
STATE_DEFECT = "defect"
STATE_EXCLUDED = "excluded"
VALID_STATES = (STATE_INTACT, STATE_DEFECT, STATE_EXCLUDED)

# ADR-0035's bands, committed before the data. Ratio of S_defect to S_between.
LICENSED_RATIO = 3.0
MARGINAL_RATIO = 1.5

# Cells whose homogeneous response is below this fraction of the largest are
# left out of the contrast metrics: dividing by a near-zero geometric factor
# turns measurement noise into apparent contrast (ADR-0038).
MIN_GEOMETRY_FRACTION = 0.02


@dataclass(frozen=True)
class SurveyScan:
    """One run, reduced to what the survey compares."""

    run_id: str
    specimen_id: str
    state: str
    created_at: str
    settings: dict
    vector: np.ndarray
    """Transfer resistance per cell in kohm, solver order, NaN where no cell
    survived in any frame."""
    bad_cells: int
    """Cells with no usable reading. A nonzero count usually means a contact."""
    frames: int
    note: str = ""


@dataclass(frozen=True)
class Contrast:
    ratio: float
    """max / min apparent resistivity, as ADR-0035 names it."""
    robust_ratio: float
    """95th / 5th percentile -- the same idea with one bad cell unable to set it."""
    spread: float
    """(max - min) / median apparent resistivity."""


@dataclass
class SurveyReport:
    profile: dict
    scans: list[SurveyScan]
    excluded: list[tuple[str, str, str]]
    contrast: dict[str, Contrast]
    noise_pairs: list[tuple[str, str, str, float]]
    between_pairs: list[tuple[str, str, float]]
    centre_distance: dict[str, float]
    defects: list[tuple[str, str, float, float | None]]
    """(run_id, specimen, distance from its intact reference, minutes since its
    last intact scan)."""
    cell_share: list[tuple[str, float]]
    electrode_share: dict[str, float]
    notes: list[str] = field(default_factory=list)

    @property
    def s_noise(self) -> float | None:
        return _median([d for *_, d in self.noise_pairs])

    @property
    def s_between(self) -> float | None:
        return _median([d for *_, d in self.between_pairs])

    @property
    def s_defect(self) -> float | None:
        return _median([d for _, _, d, _ in self.defects])


# --- loading ----------------------------------------------------------------


def _electrode_index(label: str) -> int:
    return int(label.strip().upper().lstrip("E")) - 1


def load_frames(run_dir: Path) -> list[unified.UnifiedFrame]:
    """Rebuild the frames of a recorded run from its ``frames.csv``."""
    grouped: dict[int, list[dict[str, str]]] = {}
    with (run_dir / "frames.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(int(row["frame_index"]), []).append(row)
    frames: list[unified.UnifiedFrame] = []
    for index in sorted(grouped):
        rows = grouped[index]
        first = rows[0]
        records = [
            unified.MeasurementRecord(
                polarity=row["polarity"],
                i_pair=(_electrode_index(row["i_plus"]), _electrode_index(row["i_minus"])),
                v_pair=(_electrode_index(row["v_plus"]), _electrode_index(row["v_minus"])),
                voltage_mv=float(row["voltage_mv"]),
                current_ua=float(row["current_ua"]),
                quality=row["quality"],
            )
            for row in rows
        ]
        frames.append(
            unified.UnifiedFrame(
                frame_id=int(first["frame_id"]),
                pattern=first["pattern"].upper(),
                dac_code=int(first["dac_code"]),
                settle_ms=int(first["settle_ms"]),
                sample_count=int(first["sample_count"]),
                records=records,
            )
        )
    return frames


def run_vector(frames: Sequence[unified.UnifiedFrame], settings: dict) -> np.ndarray:
    """Per-cell transfer resistance averaged over frames, NaN where never valid.

    Lenient per frame, so one weak reading costs one cell of one frame rather
    than the run; a cell bad in every frame stays NaN and is left out of every
    comparison instead of being filled (ADR-0002).
    """
    protocol, _ = unified.protocol_and_command(settings["pattern"])
    stacked = np.vstack(
        [
            unified.frame_to_vector(
                frame,
                protocol,
                strict=False,
                electrode_offset=int(settings.get("electrode_offset", 0) or 0),
                electrode_reversed=bool(settings.get("electrode_reversed", False)),
            )
            for frame in frames
        ]
    )
    with np.errstate(all="ignore"):
        counts = np.sum(np.isfinite(stacked), axis=0)
        mean = np.nansum(stacked, axis=0) / np.where(counts == 0, 1, counts)
    mean[counts == 0] = np.nan
    return mean


def load_scan(run_dir: Path, specimen_id: str, state: str, note: str = "") -> SurveyScan:
    if state not in VALID_STATES:
        raise ValueError(f"state must be one of {VALID_STATES}, got {state!r}")
    record = run_record.load_run(run_dir)
    settings = record.get("settings", {})
    frames = load_frames(run_dir)
    if not frames:
        raise ValueError(f"{run_dir.name} has no frames")
    vector = run_vector(frames, settings)
    return SurveyScan(
        run_id=run_dir.name,
        specimen_id=specimen_id,
        state=state,
        created_at=record.get("created_at", ""),
        settings=settings,
        vector=vector,
        bad_cells=int(np.sum(~np.isfinite(vector))),
        frames=len(frames),
        note=note,
    )


@dataclass(frozen=True)
class ManifestRow:
    run_id: str
    specimen_id: str
    state: str
    note: str = ""


def read_manifest(path: Path) -> list[ManifestRow]:
    """``run_id,specimen_id,state[,note]``. Lines starting with # are comments.

    A manifest exists because runs taken before ADR-0037 carry no usable
    specimen ID, and because exclusion is a decision the operator records,
    not something inferred.
    """
    rows: list[ManifestRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip() and not line.lstrip().startswith("#")]
    for row in csv.DictReader(lines):
        state = row["state"].strip().lower()
        if state not in VALID_STATES:
            raise ValueError(f"{row['run_id']}: state must be one of {VALID_STATES}")
        rows.append(
            ManifestRow(
                run_id=row["run_id"].strip(),
                specimen_id=row["specimen_id"].strip(),
                state=state,
                note=(row.get("note") or "").strip(),
            )
        )
    return rows


def manifest_from_conditions(scans_root: Path, medium: str | None = None) -> list[ManifestRow]:
    """Derive the manifest from each run's own conditions (ADR-0037 runs onward).

    A run with a target description is a defect run; one without is intact.
    Runs whose specimen ID does not follow the naming rule are skipped, since
    they predate it and cannot be grouped reliably.
    """
    rows: list[ManifestRow] = []
    for run_dir in run_record.list_runs(scans_root):
        conditions = run_record.load_run(run_dir)["conditions"]
        specimen = conditions.specimen_id or ""
        if not run_record.SPECIMEN_ID_PATTERN.match(specimen):
            continue
        if medium is not None and conditions.medium != medium:
            continue
        state = STATE_DEFECT if conditions.target_description else STATE_INTACT
        rows.append(ManifestRow(run_dir.name, specimen, state))
    return rows


# --- arithmetic -------------------------------------------------------------


def normalise(vector: np.ndarray) -> np.ndarray:
    """Divide by the mean magnitude, which cancels resistivity and size."""
    scale = np.nanmean(np.abs(vector))
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("vector has no usable cells")
    return vector / scale


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """RMS difference over the cells both have, in percent of the mean."""
    shared = np.isfinite(a) & np.isfinite(b)
    if not np.any(shared):
        return float("nan")
    return float(np.sqrt(np.mean((a[shared] - b[shared]) ** 2)) * 100.0)


def reference(vectors: Sequence[np.ndarray]) -> np.ndarray:
    """Average of already-normalised vectors, renormalised."""
    with np.errstate(all="ignore"):
        return normalise(np.nanmean(np.vstack(vectors), axis=0))


@lru_cache(maxsize=None)
def homogeneous_response(pattern: str) -> tuple[float, ...]:
    """What a uniform circular disc gives on every cell, in solver order."""
    import pyeit.mesh as pyeit_mesh
    from pyeit.eit.fem import EITForward

    protocol, _ = unified.protocol_and_command(pattern)
    forward = EITForward(pyeit_mesh.create(base.N_ELECTRODES, h0=0.08), protocol)
    return tuple(float(v) for v in np.real(forward.solve_eit()))


def contrast(vector: np.ndarray, geometry: np.ndarray) -> Contrast:
    usable = np.isfinite(vector) & (
        np.abs(geometry) >= MIN_GEOMETRY_FRACTION * np.max(np.abs(geometry))
    )
    apparent = np.abs(vector[usable] / geometry[usable])
    if apparent.size < 2 or np.min(apparent) == 0:
        nan = float("nan")
        return Contrast(nan, nan, nan)
    return Contrast(
        ratio=float(np.max(apparent) / np.min(apparent)),
        robust_ratio=float(np.percentile(apparent, 95) / np.percentile(apparent, 5)),
        spread=float((np.max(apparent) - np.min(apparent)) / np.median(apparent)),
    )


def cell_labels(pattern: str) -> list[str]:
    protocol, _ = unified.protocol_and_command(pattern)
    labels: list[str] = []
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        for meas_pair in protocol.meas_mat[ex_index]:
            labels.append(
                f"E{int(ex_pair[0]) + 1}-E{int(ex_pair[1]) + 1}"
                f"|E{int(meas_pair[1]) + 1}-E{int(meas_pair[0]) + 1}"
            )
    return labels


def _median(values: Iterable[float]) -> float | None:
    finite = [v for v in values if np.isfinite(v)]
    return float(np.median(finite)) if finite else None


def _minutes_between(earlier: str, later: str) -> float | None:
    try:
        return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() / 60.0
    except (TypeError, ValueError):
        return None


def check_profile(scans: Sequence[SurveyScan]) -> dict:
    """Every scan must share one settings profile; the survey has no other gate.

    Normalisation cancels resistivity and size, not a change of DAC or current
    range, so a mixed cohort would compare silently and wrongly (ADR-0035).
    """
    profile = {name: scans[0].settings.get(name, "<missing>") for name in MEASUREMENT_SETTINGS}
    differences: list[str] = []
    for scan in scans[1:]:
        for name in MEASUREMENT_SETTINGS:
            value = scan.settings.get(name, "<missing>")
            if value != profile[name]:
                differences.append(f"{scan.run_id} {name}: {value} vs {profile[name]}")
    if differences:
        raise SettingsMismatch(differences)
    return profile


def analyse(scans: Sequence[SurveyScan], excluded: Sequence[ManifestRow] = ()) -> SurveyReport:
    included = [s for s in scans if s.state != STATE_EXCLUDED]
    if not included:
        raise ValueError("no scans to analyse")
    profile = check_profile(included)
    pattern = str(profile["pattern"])
    geometry = np.asarray(homogeneous_response(pattern))
    labels = cell_labels(pattern)

    normalised = {s.run_id: normalise(s.vector) for s in included}
    by_specimen: dict[str, list[SurveyScan]] = {}
    for scan in included:
        by_specimen.setdefault(scan.specimen_id, []).append(scan)

    report = SurveyReport(
        profile=profile,
        scans=list(included),
        excluded=[(r.run_id, r.specimen_id, r.note) for r in excluded],
        contrast={s.run_id: contrast(s.vector, geometry) for s in included},
        noise_pairs=[],
        between_pairs=[],
        centre_distance={},
        defects=[],
        cell_share=[],
        electrode_share={},
    )

    references: dict[str, np.ndarray] = {}
    for specimen, members in sorted(by_specimen.items()):
        intact = [s for s in members if s.state == STATE_INTACT]
        for a, b in combinations(intact, 2):
            report.noise_pairs.append(
                (specimen, a.run_id, b.run_id, distance(normalised[a.run_id], normalised[b.run_id]))
            )
        if intact:
            references[specimen] = reference([normalised[s.run_id] for s in intact])
            last_intact = max(s.created_at for s in intact)
        for scan in members:
            if scan.state != STATE_DEFECT:
                continue
            if specimen not in references:
                report.notes.append(
                    f"{scan.run_id}: defect run of {specimen} has no intact scan to compare with"
                )
                continue
            report.defects.append(
                (
                    scan.run_id,
                    specimen,
                    distance(normalised[scan.run_id], references[specimen]),
                    _minutes_between(last_intact, scan.created_at),
                )
            )

    for a, b in combinations(sorted(references), 2):
        report.between_pairs.append((a, b, distance(references[a], references[b])))

    if len(references) >= 2:
        centre = reference(list(references.values()))
        for specimen, vector in references.items():
            report.centre_distance[specimen] = distance(vector, centre)
        squared = np.nanmean(
            np.vstack([(vector - centre) ** 2 for vector in references.values()]), axis=0
        )
        total = np.nansum(squared)
        if total > 0:
            share = np.nan_to_num(squared / total)
            order = np.argsort(share)[::-1]
            report.cell_share = [(labels[i], float(share[i] * 100)) for i in order]
            electrodes: dict[str, float] = {}
            for label, value in zip(labels, share):
                # Each cell involves four electrodes; its share is split evenly
                # so the per-electrode shares still sum to 100 percent.
                for name in {part for half in label.split("|") for part in half.split("-")}:
                    electrodes[name] = electrodes.get(name, 0.0) + value * 25.0
            report.electrode_share = dict(
                sorted(electrodes.items(), key=lambda item: int(item[0][1:]))
            )
    else:
        report.notes.append(
            "S_between needs intact scans of at least two specimens; "
            f"this survey has {len(references)}."
        )

    for scan in included:
        if scan.bad_cells:
            report.notes.append(
                f"{scan.run_id}: {scan.bad_cells} cells had no valid reading in any frame "
                "(usually a lost contact) and are left out of its comparisons"
            )
    return report


def verdict(report: SurveyReport) -> str:
    """ADR-0035's committed outcome for the headline ratio, or why there is none."""
    s_between, s_defect = report.s_between, report.s_defect
    if s_between is None or s_defect is None or s_between == 0:
        return "no verdict: needs both S_between and S_defect"
    ratio = s_defect / s_between
    if ratio >= LICENSED_RATIO:
        band = "cross-specimen comparison LICENSED"
    elif ratio >= MARGINAL_RATIO:
        band = "MARGINAL - reported, no classifier claim"
    else:
        band = "BELOW 1.5 - fall back to within-specimen contrast only"
    return f"S_defect / S_between = {ratio:.2f}  ->  {band}"


# --- output -----------------------------------------------------------------


def _fmt(value: float | None, suffix: str = " %") -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.2f}{suffix}"


def format_report(report: SurveyReport, top_cells: int = 10) -> str:
    lines: list[str] = ["INTACT-DISC SURVEY (ADR-0035, ADR-0038)", ""]
    lines.append(
        "Profile: " + ", ".join(f"{k}={v}" for k, v in report.profile.items())
    )
    lines.append("Distances are RMS differences of normalised vectors, % of mean |R|.")
    lines.append("")

    lines.append("Spreads (reported separately, never combined):")
    lines.append(f"  S_noise    {_fmt(report.s_noise):>10}   same specimen rescanned untouched")
    lines.append(f"  S_between  {_fmt(report.s_between):>10}   different intact specimens")
    lines.append(f"  S_defect   {_fmt(report.s_defect):>10}   same specimen, before vs after drilling")
    s_noise, s_defect = report.s_noise, report.s_defect
    if s_noise and s_defect:
        lines.append(f"  S_defect / S_noise   = {s_defect / s_noise:.2f}  (same-specimen detectability)")
    if s_noise and report.s_between:
        lines.append(f"  S_between / S_noise  = {report.s_between / s_noise:.2f}")
    lines.append("  " + verdict(report))
    lines.append("")

    lines.append("Scans:")
    lines.append(
        f"  {'run':<44} {'specimen':<16} {'state':<7} {'bad':>4} {'max/min':>8} {'p95/p5':>7} {'spread':>7}"
    )
    for scan in report.scans:
        c = report.contrast[scan.run_id]
        lines.append(
            f"  {scan.run_id:<44} {scan.specimen_id:<16} {scan.state:<7} {scan.bad_cells:>4}"
            f" {_fmt(c.ratio, ''):>8} {_fmt(c.robust_ratio, ''):>7} {_fmt(c.spread, ''):>7}"
        )
    for run_id, specimen, note in report.excluded:
        lines.append(f"  {run_id:<44} {specimen:<16} EXCLUDED  {note}")
    lines.append("")

    if report.noise_pairs:
        lines.append("S_noise pairs:")
        for specimen, a, b, d in report.noise_pairs:
            lines.append(f"  {specimen:<16} {a} vs {b}: {_fmt(d)}")
        lines.append("")
    if report.defects:
        lines.append("S_defect (each defect run against its specimen's intact reference):")
        for run_id, specimen, d, minutes in report.defects:
            gap = "" if minutes is None else f"  ({minutes:.0f} min after last intact scan)"
            lines.append(f"  {specimen:<16} {run_id}: {_fmt(d)}{gap}")
        lines.append("")
    if report.between_pairs:
        lines.append("S_between pairs:")
        for a, b, d in report.between_pairs:
            lines.append(f"  {a} vs {b}: {_fmt(d)}")
        lines.append("")
        lines.append("Distance of each specimen from the cohort centre (outliers first):")
        for specimen, d in sorted(report.centre_distance.items(), key=lambda i: -i[1]):
            lines.append(f"  {specimen:<16} {_fmt(d)}")
        lines.append("")
        lines.append(f"Cells contributing most to S_between (top {top_cells}):")
        for label, share in report.cell_share[:top_cells]:
            lines.append(f"  {label:<18} {share:5.1f} %")
        lines.append("Per-electrode share of S_between (contact faults live here):")
        lines.append(
            "  " + "  ".join(f"{e} {v:.1f}%" for e, v in report.electrode_share.items())
        )
        lines.append("")
    if report.notes:
        lines.append("Notes:")
        lines.extend(f"  - {note}" for note in report.notes)
    return "\n".join(lines).rstrip() + "\n"


def report_dict(report: SurveyReport) -> dict:
    return {
        "profile": report.profile,
        "s_noise_percent": report.s_noise,
        "s_between_percent": report.s_between,
        "s_defect_percent": report.s_defect,
        "verdict": verdict(report),
        "scans": [
            {
                "run_id": s.run_id,
                "specimen_id": s.specimen_id,
                "state": s.state,
                "created_at": s.created_at,
                "frames": s.frames,
                "bad_cells": s.bad_cells,
                "contrast": report.contrast[s.run_id].__dict__,
            }
            for s in report.scans
        ],
        "excluded": [
            {"run_id": r, "specimen_id": sp, "note": n} for r, sp, n in report.excluded
        ],
        "noise_pairs": [
            {"specimen_id": sp, "a": a, "b": b, "percent": d} for sp, a, b, d in report.noise_pairs
        ],
        "between_pairs": [{"a": a, "b": b, "percent": d} for a, b, d in report.between_pairs],
        "defects": [
            {"run_id": r, "specimen_id": sp, "percent": d, "minutes_after_intact": m}
            for r, sp, d, m in report.defects
        ],
        "centre_distance_percent": report.centre_distance,
        "cell_share_percent": dict(report.cell_share),
        "electrode_share_percent": report.electrode_share,
        "notes": report.notes,
    }


def run_survey(scans_root: Path, manifest: Sequence[ManifestRow]) -> SurveyReport:
    scans: list[SurveyScan] = []
    excluded: list[ManifestRow] = []
    for row in manifest:
        if row.state == STATE_EXCLUDED:
            excluded.append(row)
            continue
        run_dir = Path(scans_root) / run_record.RUNS_DIRNAME / row.run_id
        if not run_dir.is_dir():
            raise FileNotFoundError(f"run {row.run_id} not found under {run_dir.parent}")
        scans.append(load_scan(run_dir, row.specimen_id, row.state, row.note))
    return analyse(scans, excluded)


def save_report(report: SurveyReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    text_path = out_dir / "survey.txt"
    json_path = out_dir / "survey.json"
    text_path.write_text(format_report(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report_dict(report), indent=2, default=float), encoding="utf-8"
    )
    return text_path, json_path
