"""Absolute (static) reconstruction of one recorded run, gated (ADR-0041).

``reconstruction.py`` images only what *changed* between two runs. That cannot
image a cut disc that was never scanned intact, so here each run is solved on
its own: a homogeneous conductivity is fitted to the measured transfer
resistances, then refined element by element with a damped Gauss-Newton solve.

An absolute image has no subtraction to cancel a systematic error, so the two
gates matter more here than for a difference image:

* reciprocity -- the same 15 % median gate as the difference image (ADR-0032);
* misfit -- the fitted model must reproduce the data to ``MISFIT_GATE_PERCENT``;
* noise -- the run is split in half, both halves are solved absolutely and
  differenced. That image is what noise looks like through this solver, and the
  structure in the real image (its departure from the homogeneous fit) must be
  at least ``SIGNIFICANCE_GATE`` times its peak (the ADR-0027 rule).

A refused run is not an error: ``acquire_until_pass`` re-acquires with settings
chosen by ``next_settings`` from the earlier attempts (adaptive recalibration,
ADR-0060).

Units. Transfer resistance arrives in kohm = V/mA, so a fitted conductivity is
in mS per unit of thickness on the 2-D unit-disc mesh -- a sheet conductance.
Divided by the disc's thickness it becomes S/m. The electrodes are assumed
evenly spaced points on a circle; the real discs are neither perfectly round
nor point-contacted, so absolute values carry a geometry error that the gates
do not measure. That limitation is stated in ADR-0041 and on every figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from pyeit.eit.fem import EITForward

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert import capture_view
from tree_ert.reconstruction import (
    RECIPROCITY_GATE_PERCENT,
    average_frame_vectors,
    pattern_has_reciprocals,
    save_view,
)
from tree_ert.settings import UiSettings

SIGNIFICANCE_GATE = 2.0
"""Image structure must be this many times the split-half noise image (ADR-0027)."""

MISFIT_GATE_PERCENT = 15.0
"""RMS model misfit above which the absolute image is refused. On the 2026-09-29
dry disc the healthy runs fit to 5.7-6.1 %; the run with E8's contact lost
(165833) read 31 % and the wet-surface run (151207) 50 % -- both of which still
passed the significance gate, so significance alone cannot catch a model that
does not fit (ADR-0041)."""

GN_MAX_ITER = 30
GN_REGULARISATION = 0.03
"""Tikhonov weight on log(sigma / sigma0), relative to the largest diagonal of
J'J at the homogeneous start. A prior on the *solution*, not just a step damper:
without it the solve kept fitting noise into single elements beside the
electrodes. Swept 0.003-0.1 on the 2026-09-29 dry disc (ADR-0042): misfit
5.5-9.2 % throughout, element range [0.08, 17]x sigma0 at 0.003 narrowing to
[0.17, 3.2]x at 0.03; bad runs stayed at 28-61 % at every weight, so the misfit
gate does not depend on this choice."""

SAMPLES_CEILING = 32
"""Firmware ``n`` command clamps sample averaging to 1..32. A ladder step above
this would be silently clamped and recorded with the wrong value."""

WOOD_SETTLE_MS = (10, 20, 30, 40, 50)
"""Settle values recalibration may try (ADR-0060). On disc-01 with unchanged
contacts, 2026-10-07: 10 ms 7.3 %, 30 ms 6.5 %, 100 ms 13.9 % reciprocity --
longer dwell polarises the screws, so the old ramp to 200 ms moved the wrong way."""

NOISE_LIMIT_PERCENT = 3.0
"""Median frame-to-frame pair spread above which the next attempt averages more
before it changes settle (ADR-0058, ADR-0060). Every run that imaged well in the
saline tank sat near 1 %."""

FRAMES_CEILING = 16
DAC_BACKOFF = 0.9
"""One lower-current attempt from the best settle: eases polarisation."""

ADAPTIVE_MAX_ATTEMPTS = 6
"""A frame takes about a minute; six attempts is about two hours at most."""

MS_PER_SAMPLE = 8.3
"""Measured on 2026-10-06: 64 s per 216-record frame at settle 30 / samples 32."""


def _attempt_key(settings: UiSettings) -> tuple:
    return (settings.settle_ms, settings.samples, settings.frames, settings.dac)


def next_settings(
    start: UiSettings, tried: Sequence[tuple[UiSettings, "GateReport"]]
) -> UiSettings | None:
    """The next recalibration attempt, chosen from what the earlier ones measured.

    ``tried`` is (settings, gate report) per finished attempt, oldest first.
    From the attempt with the lowest median reciprocity so far: if its noise is
    above ``NOISE_LIMIT_PERCENT``, average more at the same settle; otherwise try
    the nearest untried settle in ``WOOD_SETTLE_MS``; then one lower-DAC attempt.
    Returns None when nothing untried is left or the cap is reached. Pattern,
    current range and electrode mapping never change -- those change what is
    measured, not how well (ADR-0060).
    """
    from dataclasses import replace

    if not tried:
        return start
    if len(tried) >= ADAPTIVE_MAX_ATTEMPTS:
        return None

    def recip(item):
        value = item[1].reciprocity_percent
        return float("inf") if value is None else value

    best, report = min(tried, key=recip)
    seen = {_attempt_key(s) for s, _ in tried}
    candidates: list[UiSettings] = []

    if report.noise_relative_percent is not None and report.noise_relative_percent > NOISE_LIMIT_PERCENT:
        candidates.append(replace(
            best,
            samples=SAMPLES_CEILING,
            frames=min(FRAMES_CEILING, best.frames + 4),
            warmup_frames=best.warmup_frames + 5,
        ))
    for settle in sorted(WOOD_SETTLE_MS, key=lambda s: (abs(s - best.settle_ms), s)):
        candidates.append(replace(best, settle_ms=settle))
    candidates.append(replace(
        best, dac=min(int(round(best.dac * DAC_BACKOFF)), best.max_dac_code())
    ))

    for candidate in candidates:
        if _attempt_key(candidate) not in seen:
            return candidate.validate()
    return None


def estimated_minutes(settings: UiSettings, records: int = 216) -> float:
    """Wall time of one attempt (warmup + frames) at these settings."""
    per_frame_s = records * (settings.settle_ms + settings.samples * MS_PER_SAMPLE) / 1000.0
    return per_frame_s * (settings.warmup_frames + settings.frames) / 60.0


CONTACT_FAULT_STREAK = 3
"""Stop recalibrating after this many consecutive attempts that each flag a
suspect electrode: no capture setting repairs a contact (2026-10-06, disc-02:
the flagged electrode wandered E1/E2/E5 -> E2 -> E3 across attempts while
misfit stayed 65-73 %)."""

STALL_STREAK = 3
STALL_FACTOR = 1.2
"""Also stop after ``STALL_STREAK`` consecutive attempts whose median reciprocity
stays above ``STALL_FACTOR`` x the gate (18 %). The contact rule above only
fires when one electrode stands out; when every electrode is bad together it
never fires (2026-10-06, disc-08: 19.8 / 26.1 / 19.3 % with no electrode
flagged, and the ramp went on into a 23-minute step)."""

LOG_SIGMA_BOUND = float(np.log(100.0))
"""Element conductivity is clipped to sigma0 / 100 .. sigma0 x 100. Wood, voids
and sap all sit inside that range; outside it the value is a solver runaway, not
a material (2026-10-06, disc-08 attempt 3 peaked at 7e17 x sigma0)."""


TROUGH_LOBE_FRACTION = 0.5
"""Elements at or below this fraction of the deepest log(sigma/sigma0), and
edge-connected to it, form the trough lobe. Half of peak, as in ADR-0055."""


@dataclass(frozen=True)
class TroughLobe:
    angle_deg: float
    """Weighted centroid angle of the lobe, mesh convention (E1 at 180 deg)."""
    radius: float
    elements: tuple[int, ...]
    electrodes: tuple[int, ...]
    """0-based electrodes whose node lies on the lobe. Non-empty means the
    trough cannot be told apart from a contact fault at that electrode."""


def _edges(tri):
    a, b, c = (int(n) for n in tri)
    return ((min(a, b), max(a, b)), (min(b, c), max(b, c)), (min(a, c), max(a, c)))


def trough_lobe(
    values: np.ndarray, elements: np.ndarray, nodes: np.ndarray, electrode_nodes: np.ndarray
) -> TroughLobe | None:
    """The connected low-conductivity region around the deepest element (ADR-0062).

    ``values`` are per-element log(sigma/sigma0). Elements are connected when
    they share an edge. None when nothing is below sigma0.
    """
    values = np.asarray(values, dtype=float)
    seed = int(np.argmin(values))
    if values[seed] >= 0.0:
        return None
    deep = values <= TROUGH_LOBE_FRACTION * values[seed]
    by_edge: dict[tuple[int, int], list[int]] = {}
    for index, tri in enumerate(elements):
        for edge in _edges(tri):
            by_edge.setdefault(edge, []).append(index)
    member, stack = {seed}, [seed]
    while stack:
        for edge in _edges(elements[stack.pop()]):
            for other in by_edge[edge]:
                if deep[other] and other not in member:
                    member.add(other)
                    stack.append(other)
    lobe = np.array(sorted(member))
    corners = np.asarray(nodes, dtype=float)[np.asarray(elements)[lobe]][:, :, :2]
    centres = corners.mean(axis=1)
    edge1, edge2 = corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]
    area = 0.5 * np.abs(edge1[:, 0] * edge2[:, 1] - edge1[:, 1] * edge2[:, 0])
    weight = -values[lobe] * area
    cx, cy = (weight[:, None] * centres).sum(axis=0) / weight.sum()
    on_lobe = set(np.asarray(elements)[lobe].ravel().tolist())
    return TroughLobe(
        angle_deg=float(np.degrees(np.arctan2(cy, cx)) % 360.0),
        radius=float(np.hypot(cx, cy)),
        elements=tuple(int(i) for i in lobe),
        electrodes=tuple(i for i, n in enumerate(electrode_nodes) if int(n) in on_lobe),
    )


@dataclass(frozen=True)
class AbsoluteResult:
    sigma: np.ndarray
    """Per-element sheet conductance, mS (multiply by 1000/thickness_mm for S/m)."""

    sigma0: float
    """Best homogeneous sheet conductance, mS: the bulk number for the specimen."""

    sign: int
    """+1 if the instrument's transfer resistance has pyeit's sign, else -1."""

    residual_percent: float
    """RMS model misfit over the kept rows, percent of RMS measurement.
    Large values mean the 2-D circular model does not fit the specimen."""

    iterations: int
    dropped_indexes: list[int]
    kept_pairs: int
    total_pairs: int
    centres: np.ndarray
    nodes: np.ndarray
    elements: np.ndarray
    electrode_nodes: np.ndarray

    @property
    def structure(self) -> np.ndarray:
        """Departure from the homogeneous fit -- what the image actually claims."""
        return self.sigma - self.sigma0

    @property
    def peak_index(self) -> int:
        return int(np.argmax(np.abs(self.structure)))

    @property
    def peak_value(self) -> float:
        return float(self.structure[self.peak_index])

    @property
    def peak_angle_deg(self) -> float:
        return self._angle(self.peak_index)

    @property
    def trough_value(self) -> float:
        """Most negative sigma - sigma0, mS. A void lowers sigma0, so its largest
        |structure| is a positive overshoot beside it; the trough is what
        locates a void or decay (ADR-0061)."""
        return float(np.min(self.structure))

    @cached_property
    def trough(self) -> TroughLobe | None:
        """The connected trough region and the electrodes it touches (ADR-0062)."""
        return trough_lobe(
            np.log(self.sigma / self.sigma0), self.elements, self.nodes, self.electrode_nodes
        )

    @property
    def trough_angle_deg(self) -> float | None:
        return self.trough.angle_deg if self.trough else None

    def trough_text(self) -> str:
        lobe = self.trough
        if lobe is None:
            return "no trough"
        text = f"trough {self.trough_value:+.3g} mS, lobe at {lobe.angle_deg:.0f} deg"
        if lobe.electrodes:
            names = ",".join(f"E{i + 1}" for i in lobe.electrodes)
            text += f" (touches {names}: may be contact)"
        return text

    def _angle(self, index: int) -> float:
        x, y = self.centres[index][:2]
        return float(np.degrees(np.arctan2(y, x)) % 360.0)


def solve_absolute(
    vector: np.ndarray,
    protocol,
    max_iter: int = GN_MAX_ITER,
    regularisation: float = GN_REGULARISATION,
) -> AbsoluteResult:
    """Fit sheet conductance to one measurement vector (kohm). NaN rows are dropped.

    The solve is in log-conductance so the result stays positive, and NaN rows
    are excluded from the misfit rather than substituted (ADR-0002).
    """
    vector = np.asarray(vector, dtype=float)
    kept = ~np.isnan(vector)
    if not kept.any():
        raise ValueError("every measurement pair was unusable; nothing to reconstruct")
    eit_mesh, _ = base.create_solver(protocol)
    forward = EITForward(eit_mesh, protocol)

    unit = np.real(forward.solve_eit(perm=1.0))
    projection = float(np.dot(unit[kept], vector[kept]))
    if projection == 0.0:
        raise ValueError("measurement is orthogonal to the homogeneous model")
    sign = 1 if projection > 0 else -1
    measured = sign * vector
    # v(c * sigma) = v(sigma) / c, so the least-squares homogeneous fit is closed form.
    sigma0 = float(np.dot(unit[kept], unit[kept]) / abs(projection))

    log_prior = np.full(eit_mesh.n_elems, np.log(sigma0))
    log_sigma = log_prior.copy()
    lam = None
    iterations = 0
    for iterations in range(1, max_iter + 1):
        jac, simulated = forward.compute_jac(perm=np.exp(log_sigma))
        # pyeit's compute_jac returns -dV/dsigma (checked against a finite
        # difference); the chain rule into log-sigma adds the sigma factor.
        jac = -np.real(jac)[kept] * np.exp(log_sigma)[None, :]
        residual = measured[kept] - np.real(simulated)[kept]
        normal = jac.T @ jac
        if lam is None:
            # Fixed from the homogeneous Jacobian so the objective does not move
            # between iterations.
            lam = regularisation * float(np.max(np.diag(normal)))
        step = np.linalg.solve(
            normal + lam * np.eye(normal.shape[0]),
            jac.T @ residual - lam * (log_sigma - log_prior),
        )
        # Backtrack until the regularised objective falls. A full Gauss-Newton
        # step overshoots on real data (log-sigma swung by e^20 on the disc runs).
        objective = float(residual @ residual + lam * np.sum((log_sigma - log_prior) ** 2))
        scale = 1.0
        for _ in range(8):
            trial = np.clip(
                log_sigma + scale * step,
                log_prior - LOG_SIGMA_BOUND,
                log_prior + LOG_SIGMA_BOUND,
            )
            trial_v = np.real(forward.solve_eit(perm=np.exp(trial)))[kept]
            trial_r = measured[kept] - trial_v
            trial_obj = float(trial_r @ trial_r + lam * np.sum((trial - log_prior) ** 2))
            if np.isfinite(trial_obj) and trial_obj < objective:
                break
            scale *= 0.5
        else:
            break
        log_sigma = trial
        if np.max(np.abs(scale * step)) < 1e-4 or objective - trial_obj < 1e-6 * objective:
            break

    final = np.real(forward.solve_eit(perm=np.exp(log_sigma)))
    misfit = measured[kept] - final[kept]
    rms_measured = float(np.sqrt(np.mean(measured[kept] ** 2)))
    residual_percent = float(np.sqrt(np.mean(misfit**2)) / rms_measured * 100.0)

    return AbsoluteResult(
        sigma=np.exp(log_sigma),
        sigma0=sigma0,
        sign=sign,
        residual_percent=residual_percent,
        iterations=iterations,
        dropped_indexes=[int(i) for i in np.flatnonzero(~kept)],
        kept_pairs=int(kept.sum()),
        total_pairs=int(vector.size),
        centres=np.mean(eit_mesh.node[eit_mesh.element], axis=1),
        nodes=np.asarray(eit_mesh.node),
        elements=np.asarray(eit_mesh.element),
        electrode_nodes=np.asarray(eit_mesh.el_pos),
    )


def exclude_electrodes(
    frames: Sequence[unified.UnifiedFrame], electrodes: Sequence[int]
) -> list[unified.UnifiedFrame]:
    """Frames without any record that drives or senses on ``electrodes`` (1-based).

    The removed pairs become NaN rows, which the solver already drops (ADR-0002),
    so leaving an electrode out costs its measurements and nothing else (ADR-0064).
    """
    from dataclasses import replace

    excluded = {int(e) - 1 for e in electrodes}
    if not excluded:
        return list(frames)
    return [
        replace(
            frame,
            records=[
                record for record in frame.records
                if not excluded & {*record.i_pair, *record.v_pair}
            ],
        )
        for frame in frames
    ]


def reconstruct_absolute(
    frames: Sequence[unified.UnifiedFrame], settings: UiSettings
) -> AbsoluteResult:
    frames = exclude_electrodes(frames, settings.absolute_exclude_electrodes)
    protocol, _ = unified.protocol_and_command(settings.pattern)
    return solve_absolute(average_frame_vectors(frames, protocol, settings), protocol)


def split_half_noise(
    frames: Sequence[unified.UnifiedFrame], settings: UiSettings
) -> np.ndarray | None:
    """Absolute(first half) - absolute(second half): the noise image. None if < 4 frames."""
    if len(frames) < 4:
        return None
    mid = len(frames) // 2
    first = reconstruct_absolute(frames[:mid], settings)
    second = reconstruct_absolute(frames[mid:], settings)
    return second.sigma - first.sigma


def significance(result: AbsoluteResult, noise: np.ndarray) -> float:
    noise_peak = float(np.max(np.abs(noise))) if noise.size else 0.0
    signal_peak = abs(result.peak_value)
    if noise_peak <= 0.0:
        return float("inf") if signal_peak > 0.0 else 0.0
    return signal_peak / noise_peak


@dataclass(frozen=True)
class GateReport:
    reciprocity_percent: float | None
    noise_relative_percent: float | None
    significance: float | None
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.reasons


def gate(
    frames: Sequence[unified.UnifiedFrame],
    result: AbsoluteResult | None,
    noise: np.ndarray | None,
) -> GateReport:
    """Every reason this run's absolute image may not be trusted. Empty = pass."""
    reasons: list[str] = []
    recip = capture_view.reciprocity_summary(frames)
    noise_stats = capture_view.noise_summary(frames)
    if frames and not pattern_has_reciprocals(frames[0].pattern):
        pass  # unmeasurable with this pattern: not a reason to refuse (ADR-0073)
    elif recip is None:
        reasons.append("reciprocity could not be measured (no reciprocal pairs)")
    elif recip.median_error_percent > RECIPROCITY_GATE_PERCENT:
        reasons.append(
            f"median reciprocity {recip.median_error_percent:.1f}% "
            f"> {RECIPROCITY_GATE_PERCENT:.0f}%"
        )
    sig = None
    if result is None:
        reasons.append("absolute solve failed")
    elif noise is None:
        reasons.append("too few frames for a split-half noise image (need 4)")
    else:
        if result.residual_percent > MISFIT_GATE_PERCENT:
            reasons.append(
                f"model misfit {result.residual_percent:.1f}% > {MISFIT_GATE_PERCENT:.0f}%"
            )
        sig = significance(result, noise)
        if sig < SIGNIFICANCE_GATE:
            reasons.append(f"significance {sig:.2f} < {SIGNIFICANCE_GATE:.1f}")
    return GateReport(
        reciprocity_percent=recip.median_error_percent if recip else None,
        noise_relative_percent=(
            noise_stats.median_pair_relative_percent if noise_stats else None
        ),
        significance=sig,
        reasons=tuple(reasons),
    )


def evaluate(
    frames: Sequence[unified.UnifiedFrame], settings: UiSettings
) -> tuple[AbsoluteResult | None, np.ndarray | None, GateReport]:
    result = noise = None
    # Filtered once here so the reciprocity gate judges the same records the
    # solve uses; reconstruct_absolute filtering again is a no-op.
    frames = exclude_electrodes(frames, settings.absolute_exclude_electrodes)
    try:
        result = reconstruct_absolute(frames, settings)
        noise = split_half_noise(frames, settings)
    except (ValueError, np.linalg.LinAlgError):
        pass
    return result, noise, gate(frames, result, noise)


@dataclass(frozen=True)
class Attempt:
    settings: UiSettings
    frames: list
    result: AbsoluteResult | None
    noise: np.ndarray | None
    report: GateReport


def acquire_until_pass(
    capture: Callable[[UiSettings], list],
    start: UiSettings,
    on_attempt: Callable[[int, Attempt], None] | None = None,
    max_attempts: int = ADAPTIVE_MAX_ATTEMPTS,
) -> tuple[list[Attempt], Attempt | None]:
    """Continuous recalibration: re-acquire until the gates pass (ADR-0060).

    ``capture(settings)`` configures the instrument, warms up and returns the
    recorded frames. ``start`` runs first; each later attempt is chosen by
    ``next_settings`` from the earlier results. The first passing attempt ends
    the loop. Returns every attempt and the passing one.
    """
    attempts: list[Attempt] = []
    history: list[tuple[GateReport, tuple]] = []
    tried: list[tuple[UiSettings, GateReport]] = []
    while len(attempts) < max_attempts:
        candidate = next_settings(start, tried)
        if candidate is None:
            break
        frames = capture(candidate)
        result, noise, report = evaluate(frames, candidate)
        attempt = Attempt(candidate, frames, result, noise, report)
        attempts.append(attempt)
        tried.append((candidate, report))
        if on_attempt is not None:
            on_attempt(len(attempts), attempt)
        if report.passed:
            return attempts, attempt
        history.append((report, contact_fault(frames, candidate.absolute_exclude_electrodes)))
        if stop_reason(history):
            return attempts, None
    return attempts, None


def stop_reason(history: Sequence[tuple[GateReport, tuple]]) -> str | None:
    """Why recalibration should give up, or None to keep going.

    ``history`` is (gate report, suspect electrodes) per refused attempt, oldest
    first. Both rules say the same thing: the fault is in the specimen or its
    contacts, and no capture setting will repair it (ADR-0043).
    """
    if len(history) >= CONTACT_FAULT_STREAK and all(
        suspects for _, suspects in history[-CONTACT_FAULT_STREAK:]
    ):
        named = ", ".join(f"E{e + 1}" for e, _ in history[-1][1])
        return (
            f"{CONTACT_FAULT_STREAK} attempts in a row flagged electrode contacts "
            f"(latest {named})"
        )
    limit = STALL_FACTOR * RECIPROCITY_GATE_PERCENT
    recent = [report.reciprocity_percent for report, _ in history[-STALL_STREAK:]]
    if len(recent) >= STALL_STREAK and all(r is not None and r > limit for r in recent):
        shown = " / ".join(f"{r:.1f}" for r in recent)
        return (
            f"reciprocity stayed above {limit:.0f}% for {STALL_STREAK} attempts "
            f"({shown}%) with no single electrode to blame -- likely wet faces"
        )
    return None


def contact_fault(
    frames: Sequence[unified.UnifiedFrame], excluded: Sequence[int] = ()
) -> tuple[tuple[int, float], ...]:
    """Electrodes flagged as suspect contacts (ADR-0032); empty if none or unscorable.

    Electrodes already left out of the absolute solve (``excluded``, 1-based)
    are not reported: a known-bad channel must not stop recalibration (ADR-0064).
    """
    try:
        frames = exclude_electrodes(frames, excluded)
        return capture_view.session_summary(frames).suspect_electrodes
    except Exception:  # noqa: BLE001 - a scoring failure is not a contact verdict
        return ()


def trough_index_fields(result: AbsoluteResult | None) -> dict:
    """index.csv columns for the trough lobe (ADR-0062)."""
    lobe = result.trough if result is not None else None
    return {
        "absolute_trough_angle_deg": lobe.angle_deg if lobe else None,
        "absolute_trough_electrodes": (
            " ".join(f"E{i + 1}" for i in lobe.electrodes) if lobe else None
        ),
    }


DISPLAY_PERCENTILE = 98.0
"""Colour scale = this percentile of the image's |log10(sigma/sigma0)|, so a few
contact spikes saturate instead of flattening the rest of the disc to grey
(ADR-0061). The noise panel is drawn on the image's scale and saturates when it
is larger (ADR-0063)."""


def display_values(
    sigma: np.ndarray, sigma0: float, noise: np.ndarray
) -> tuple[np.ndarray, np.ndarray, float, int, int]:
    """(image, noise, scale, image clipped, noise clipped) in log10(sigma/sigma0).

    The split-half noise is a difference of conductances; it is converted to
    log units to first order, noise / (sigma ln 10). Display only: the gates
    and the saved arrays stay in mS.
    """
    image = np.log10(sigma / sigma0)
    noise_log = np.asarray(noise) / (sigma * np.log(10.0))
    scale = max(float(np.percentile(np.abs(image), DISPLAY_PERCENTILE)), 1e-6)
    clipped = int(np.count_nonzero(np.abs(image) > scale))
    noise_clipped = int(np.count_nonzero(np.abs(noise_log) > scale))
    return image, noise_log, scale, clipped, noise_clipped


def excluded_text(settings: UiSettings, result: AbsoluteResult) -> str:
    """Caption fragment naming electrodes left out of the solve (ADR-0064), or ''."""
    if not settings.absolute_exclude_electrodes:
        return ""
    names = " ".join(f"E{e}" for e in settings.absolute_exclude_electrodes)
    return f"  |  EXCLUDED {names}: {result.kept_pairs}/{result.total_pairs} pairs"


def save_absolute(
    attempt: Attempt,
    image_path: Path,
    data_path: Path,
    title: str,
    thickness_mm: float | None = None,
) -> None:
    """Two panels on one clipped log scale: log10(sigma/sigma0) and the noise image (ADR-0061)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    result = attempt.result
    if result is None:
        return
    protocol, _ = unified.protocol_and_command(attempt.settings.pattern)
    eit_mesh, _ = base.create_solver(protocol)
    pts, tri = eit_mesh.node, eit_mesh.element
    noise = attempt.noise if attempt.noise is not None else np.zeros_like(result.sigma)
    image, noise_log, scale, clipped, noise_clipped = display_values(
        result.sigma, result.sigma0, noise
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    for ax, values, name in (
        (axes[0], image, "log10(sigma / sigma0) (image)"),
        (axes[1], noise_log, "split-half noise (control)"),
    ):
        mappable = ax.tripcolor(
            pts[:, 0], pts[:, 1], tri, values, shading="flat",
            cmap="coolwarm", vmin=-scale, vmax=scale,
        )
        ax.set_title(name)
        ax.set_aspect("equal")
        ax.axis("off")
        for index, x, y in base.electrode_label_positions(eit_mesh):
            ax.text(x, y, f"E{index + 1}", ha="center", va="center", fontsize=8)
    figure.colorbar(
        mappable, ax=axes, shrink=0.8, extend="both",
        label="log10(sigma / sigma0): blue less, red more conductive",
    )

    report = attempt.report
    bulk = f"sigma0 = {result.sigma0:.4g} mS sheet"
    if thickness_mm:
        bulk += f" = {result.sigma0 * 1000.0 / thickness_mm:.4g} S/m"
    verdict = "PASS" if report.passed else "REFUSED: " + "; ".join(report.reasons)
    sig = f"{report.significance:.2f}" if report.significance is not None else "n/a"
    recip = f"{report.reciprocity_percent:.1f}%" if report.reciprocity_percent is not None else "n/a"
    figure.suptitle(
        f"{title}\n{bulk}  |  peak {result.peak_value:+.3g} mS at {result.peak_angle_deg:.0f} deg"
        f"  |  {result.trough_text()}"
        f"\nsignificance {sig}  |  reciprocity {recip}  |  misfit {result.residual_percent:.1f}%"
        f"\n{verdict}  |  colour clipped at {DISPLAY_PERCENTILE:.0f}th percentile"
        f" ({clipped} image, {noise_clipped} noise elements saturated)  |  circular point-electrode model (ADR-0041)",
        fontsize=9,
    )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(image_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    save_view(eit_mesh, image, title, scale, image_path)

    np.savez_compressed(
        data_path,
        sigma=result.sigma,
        sigma0=result.sigma0,
        sign=result.sign,
        noise=noise,
        residual_percent=result.residual_percent,
        peak_value=result.peak_value,
        peak_angle_deg=result.peak_angle_deg,
        trough_value=result.trough_value,
        trough_angle_deg=(
            result.trough_angle_deg if result.trough_angle_deg is not None else np.nan
        ),
        trough_electrodes=np.asarray(
            result.trough.electrodes if result.trough else (), dtype=int
        ),
        dropped_indexes=np.asarray(result.dropped_indexes, dtype=int),
        significance=report.significance if report.significance is not None else np.nan,
        reciprocity_percent=(
            report.reciprocity_percent if report.reciprocity_percent is not None else np.nan
        ),
        passed=report.passed,
        pattern=attempt.settings.pattern,
    )
