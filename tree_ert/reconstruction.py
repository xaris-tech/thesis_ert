"""Difference reconstruction between two recorded runs.

Only *difference* imaging. Absolute reconstruction stays unlicensed while the
57.5 percent reciprocity violation is open (ADR-0017, ADR-0018), and a
difference image survives that fault only because a systematic error stable
between the two captures subtracts out. That last clause is load-bearing: it is
why the settings of the two runs are checked before anything is computed, and
why a mismatch is refused rather than annotated.

What a difference image can show is what *changed* between the two states.
A feature present in both -- the drilled void in the trunk specimen, say --
subtracts out and is structurally invisible, which is the null recorded in
ADR-0019.

Solver setup, protocol construction and the backprojection itself all come from
``phase3a_reconstruct``; nothing here reimplements them.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert import capture_view
from tree_ert.settings import UiSettings

RECIPROCITY_GATE_PERCENT = 10.0
"""Median reciprocity error above which a difference image is refused (ADR-0030).

Reconstruction maps a voltage change onto a location only if swapping drive and
sense electrodes gives the same reading. Good EIT systems reach under 1 percent;
10 percent is the edge the literature still calls usable. It is a gate on the
data, not on the picture: no solver setting recovers geometry the measurement
set no longer carries."""

# Settings that define the measurement itself. Two runs that differ in any of
# these did not measure the same quantity, so their difference is meaningless:
# pattern and current range change the measurement set and the scaling
# outright, DAC/settle/samples change the amplitude and noise the vectors carry,
# and the electrode mapping changes which physical electrode each row refers to.
#
# Frame and warmup counts are deliberately NOT here. Baselining over 5 frames
# and targeting over 10 is normal practice and says nothing about comparability.
MEASUREMENT_SETTINGS = (
    "pattern",
    "current_range",
    "dac",
    "settle_ms",
    "samples",
    "electrode_offset",
    "electrode_reversed",
)


class SettingsMismatch(RuntimeError):
    """Raised when two runs cannot honestly be differenced.

    A hard refusal rather than a warning on the figure. The operator chose this
    over annotation: an image that looks confident and is built on incomparable
    data is the failure mode this project has spent months undoing, and unlike
    reciprocity (ADR-0003, reported not enforced) this one is decidable exactly
    rather than being a matter of degree.
    """

    def __init__(self, differences: Sequence[str]) -> None:
        self.differences = list(differences)
        detail = "; ".join(self.differences)
        super().__init__(
            f"baseline and target were captured with different settings: {detail}"
        )


def settings_mismatch(baseline: dict, target: dict) -> list[str]:
    """Measurement settings that differ, as readable 'field: a vs b' strings.

    A field missing from either side counts as differing rather than matching:
    an older run that did not record the setting cannot be shown to be
    comparable, and silently assuming it was is the whole problem.
    """
    differences: list[str] = []
    for field in MEASUREMENT_SETTINGS:
        left = baseline.get(field, "<missing>")
        right = target.get(field, "<missing>")
        if left != right:
            differences.append(f"{field}: {left} vs {right}")
    return differences


def require_compatible(baseline: dict, target: dict) -> None:
    differences = settings_mismatch(baseline, target)
    if differences:
        raise SettingsMismatch(differences)


@dataclass(frozen=True)
class ReconstructionResult:
    """A difference image plus everything needed to read it honestly."""

    values: np.ndarray
    """Per-element conductivity change, in the solver's arbitrary units."""

    baseline_vector: np.ndarray
    target_vector: np.ndarray
    dropped_indexes: list[int]
    kept_pairs: int
    total_pairs: int
    quality_label: str

    peak_value: float
    """Signed magnitude of the largest excursion. The number a claim rests on."""

    peak_xy: tuple[float, float]
    peak_angle_deg: float
    """Angle of the peak in mesh coordinates, for comparison with ground truth."""

    noise_floor_kohm: float | None
    """Control drift for scale, when known. A peak below this is not a detection."""

    @property
    def kept_ratio(self) -> float:
        return self.kept_pairs / self.total_pairs if self.total_pairs else 0.0

    @property
    def limit(self) -> float:
        """Symmetric colour limit: the largest absolute excursion."""
        return float(np.max(np.abs(self.values))) if self.values.size else 0.0


def average_frame_vectors(
    frames: Sequence[unified.UnifiedFrame],
    protocol,
    settings: UiSettings,
) -> np.ndarray:
    """Mean measurement vector across frames, lenient about flagged records.

    Lenient because a single flagged record in one frame should cost that pair
    in that frame, not the whole run. Pairs missing everywhere stay NaN and are
    dropped from the solver by the caller rather than being invented.
    """
    if not frames:
        raise ValueError("no frames to reconstruct from")
    vectors = [
        unified.frame_to_vector(
            frame,
            protocol,
            strict=False,
            electrode_offset=settings.electrode_offset,
            electrode_reversed=settings.electrode_reversed,
        )
        for frame in frames
    ]
    stacked = np.vstack(vectors)
    with warnings.catch_warnings():
        # A pair flagged in every frame averages over nothing. That is the
        # normal "dropped everywhere" case, handled by the caller as a NaN row
        # excluded from the solver -- not a condition worth warning about.
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(stacked, axis=0)


def reconstruct(
    baseline_frames: Sequence[unified.UnifiedFrame],
    target_frames: Sequence[unified.UnifiedFrame],
    settings: UiSettings,
    baseline_settings: dict | None = None,
    target_settings: dict | None = None,
    noise_floor_kohm: float | None = None,
) -> ReconstructionResult:
    """Difference image of target against baseline.

    Rows that are NaN in either vector are excluded from the solver rather than
    substituted with a baseline value (ADR-0002): substitution asserts "nothing
    changed here", which can erase a genuine target, and biases the frame
    scaling factor when many rows are substituted (validity-audit D-05).
    """
    if baseline_settings is not None and target_settings is not None:
        require_compatible(baseline_settings, target_settings)

    protocol, _ = unified.protocol_and_command(settings.pattern)
    eit_mesh, solver = base.create_solver(protocol)

    baseline_vector = average_frame_vectors(baseline_frames, protocol, settings)
    target_vector = average_frame_vectors(target_frames, protocol, settings)

    missing = np.isnan(baseline_vector) | np.isnan(target_vector)
    dropped = [int(index) for index in np.flatnonzero(missing)]
    total_pairs = int(baseline_vector.size)
    kept_pairs = total_pairs - len(dropped)
    if kept_pairs == 0:
        raise ValueError("every measurement pair was unusable; nothing to reconstruct")

    # The solver must not see NaN even in rows it will ignore: they propagate
    # through the scaling dot products before the mask is applied.
    clean_baseline = np.where(missing, 0.0, baseline_vector)
    clean_target = np.where(missing, 0.0, target_vector)

    values = base.reconstruct_difference(
        clean_baseline, clean_target, solver, dropped_indexes=dropped or None
    )
    values = np.asarray(values, dtype=float)

    quality_label = "ok"
    if dropped:
        quality_label = "best-effort"
    if kept_pairs / total_pairs < unified.MIN_RECON_KEPT_PAIR_RATIO:
        quality_label = "low-confidence"

    peak_index = int(np.argmax(np.abs(values))) if values.size else 0
    centres = np.mean(eit_mesh.node[eit_mesh.element], axis=1)
    peak_x, peak_y = float(centres[peak_index][0]), float(centres[peak_index][1])

    return ReconstructionResult(
        values=values,
        baseline_vector=baseline_vector,
        target_vector=target_vector,
        dropped_indexes=dropped,
        kept_pairs=kept_pairs,
        total_pairs=total_pairs,
        quality_label=quality_label,
        peak_value=float(values[peak_index]) if values.size else 0.0,
        peak_xy=(peak_x, peak_y),
        peak_angle_deg=float(np.degrees(np.arctan2(peak_y, peak_x)) % 360.0),
        noise_floor_kohm=noise_floor_kohm,
    )


def reciprocity_gate(frames: Sequence[unified.UnifiedFrame]) -> str | None:
    """Why these frames fail the reciprocity gate, or None if they pass.

    A run with no scorable reciprocal pairs fails rather than passes: an
    unmeasured reciprocity cannot be shown to be good, and silently assuming it
    was is the failure this gate exists to prevent.
    """
    summary = capture_view.reciprocity_summary(frames)
    if summary is None:
        return "reciprocity could not be measured (no reciprocal pairs)"
    if summary.median_error_percent > RECIPROCITY_GATE_PERCENT:
        return (
            f"median reciprocity error {summary.median_error_percent:.1f}% "
            f"exceeds {RECIPROCITY_GATE_PERCENT:.0f}%"
        )
    return None


def split_half_control(
    baseline_frames: Sequence[unified.UnifiedFrame],
    settings: UiSettings,
    noise_floor_kohm: float | None = None,
) -> ReconstructionResult | None:
    """Reconstruct the baseline's first half against its second half.

    Nothing changed between those halves *by construction*, so the resulting
    image is what measurement noise looks like through this solver, on this
    specimen, at these settings -- expressed in the same arbitrary units as a
    real difference image, which is the whole point.

    Without it, a difference image of pure drift and a difference image of a
    real feature are indistinguishable: both auto-scale to fill the colour
    range and both look convincing. The magnitude caption states the peak but
    gives nothing to compare it against, which is the gap this closes.

    Returns None when there are too few frames to split.
    """
    if len(baseline_frames) < 4:
        # Two frames per half is the minimum that carries any spread at all;
        # one per half would make the "control" a single-frame difference,
        # which understates the noise rather than measuring it.
        return None
    midpoint = len(baseline_frames) // 2
    return reconstruct(
        baseline_frames[:midpoint],
        baseline_frames[midpoint:],
        settings,
        noise_floor_kohm=noise_floor_kohm,
    )


def significance(result: ReconstructionResult, control: ReconstructionResult) -> float:
    """How many times larger the image is than the noise image, peak for peak.

    The number that answers "is this a detection". Around 1 means the image is
    indistinguishable from the instrument imaging itself. It compares like with
    like -- both peaks are in the solver's arbitrary units -- which the
    measurement noise floor in kohm cannot do.
    """
    if control.limit <= 0.0:
        return float("inf") if result.limit > 0.0 else 0.0
    return result.limit / control.limit


def _magnitude_caption(result: ReconstructionResult) -> str:
    """The line that stops a null being read as a detection.

    A blank difference auto-scaled to its own range renders as a vivid,
    convincing picture of nothing. The colour scale is kept per-image so a real
    result stays readable, and the actual magnitude is printed beneath it so the
    vividness cannot be mistaken for significance (ADR-0026).
    """
    if result.limit == 0.0:
        # An identically zero image has no scale to state, and the colourbar
        # falls back to a nominal range. Saying "+/-0.000e+00" beside a bar
        # reading +/-1.00 reads as a contradiction rather than as a null.
        scale_line = "image is identically zero; colourbar range is nominal"
    else:
        scale_line = f"colour scale +/-{result.limit:.3e}  (auto-scaled to this image)"
    lines = [
        f"peak {result.peak_value:+.3e} at {result.peak_angle_deg:.0f} deg "
        f"(x={result.peak_xy[0]:+.2f}, y={result.peak_xy[1]:+.2f})",
        scale_line,
        f"pairs {result.kept_pairs}/{result.total_pairs} kept  [{result.quality_label}]",
    ]
    if result.noise_floor_kohm is not None:
        lines.append(
            f"measurement noise floor {result.noise_floor_kohm:.5f} kohm "
            "- a change below this is not a detection"
        )
    return "\n".join(lines)


def save_reconstruction(
    result: ReconstructionResult,
    settings: UiSettings,
    image_path: Path,
    data_path: Path | None = None,
    title: str = "Difference reconstruction",
    subtitle: str = "",
    control: ReconstructionResult | None = None,
) -> tuple[Path, Path | None]:
    """Render the image and, optionally, store the vectors beside it.

    The vectors are kept so a later change to the colour scale, the solver
    settings or the electrode mapping can be re-applied to data already
    captured. On a specimen that drifts, re-capturing is not a real option.
    """
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    protocol, _ = unified.protocol_and_command(settings.pattern)
    eit_mesh, _ = base.create_solver(protocol)

    # One colour scale across both panels. Scaling them independently would
    # make the noise image look exactly as dramatic as the real one, which is
    # the misreading this whole feature exists to prevent.
    limit = max(result.limit, control.limit if control else 0.0) or 1.0

    if control is None:
        figure, ax = plt.subplots(figsize=(6.5, 7.2))
        image = unified._draw_reconstruction(ax, eit_mesh, result.values, title, limit)
        figure.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    else:
        figure, axes = plt.subplots(1, 2, figsize=(11.0, 6.4))
        image = unified._draw_reconstruction(axes[0], eit_mesh, result.values, title, limit)
        unified._draw_reconstruction(
            axes[1],
            eit_mesh,
            control.values,
            "Control: baseline against itself\n(this is what noise looks like)",
            limit,
        )
        figure.colorbar(image, ax=axes, fraction=0.035, pad=0.03)

    caption = _magnitude_caption(result)
    if control is not None:
        ratio = significance(result, control)
        verdict = (
            "indistinguishable from noise"
            if ratio < 2.0
            else f"{ratio:.1f}x the noise image"
        )
        caption += (
            f"\ncontrol peak {control.peak_value:+.3e}  |  "
            f"image is {verdict}"
        )
    if subtitle:
        caption = f"{subtitle}\n{caption}"
    figure.text(
        0.5,
        0.02,
        caption,
        ha="center",
        va="bottom",
        fontsize=7,
        family="monospace",
    )
    figure.subplots_adjust(bottom=0.26 if control is None else 0.30)

    image_path = Path(image_path)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(image_path, dpi=150, bbox_inches="tight")
    plt.close(figure)

    if data_path is None:
        return image_path, None

    data_path = Path(data_path)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        data_path,
        values=result.values,
        baseline=result.baseline_vector,
        target=result.target_vector,
        dropped_indexes=np.asarray(result.dropped_indexes, dtype=int),
        peak_value=result.peak_value,
        peak_xy=np.asarray(result.peak_xy, dtype=float),
        peak_angle_deg=result.peak_angle_deg,
        kept_pairs=result.kept_pairs,
        total_pairs=result.total_pairs,
        quality_label=result.quality_label,
        pattern=settings.pattern,
        **(
            {
                "control_values": control.values,
                "control_peak": control.peak_value,
                "significance": significance(result, control),
            }
            if control is not None
            else {}
        ),
    )
    return image_path, data_path
