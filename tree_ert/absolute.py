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

A refused run is not an error: ``acquire_until_pass`` re-acquires with the next
drift-tuning profile (continuous recalibration).

Units. Transfer resistance arrives in kohm = V/mA, so a fitted conductivity is
in mS per unit of thickness on the 2-D unit-disc mesh -- a sheet conductance.
Divided by the disc's thickness it becomes S/m. The electrodes are assumed
evenly spaced points on a circle; the real discs are neither perfectly round
nor point-contacted, so absolute values carry a geometry error that the gates
do not measure. That limitation is stated in ADR-0041 and on every figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from pyeit.eit.fem import EITForward

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert import capture_view
from tree_ert.reconstruction import RECIPROCITY_GATE_PERCENT, average_frame_vectors
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

SETTLE_RAMP_MS = (10, 30, 50, 75, 100, 150, 200)
SAMPLES_RAMP = (8, 16, 32, 16, 32, 32, 32)
WARMUP_RAMP = (5, 5, 10, 15, 20, 25, 30)
FRAMES_RAMP = (10, 10, 10, 12, 12, 16, 16)
DAC_STEPS = (1.0, 1.0, 1.0, 0.95, 0.9, 0.85, 0.8)
"""Fraction of the starting DAC code per step. Lower current eases electrode
polarisation and pulls the worst pair back from its rated maximum; sigma0 is
current-normalised, so absolute values stay comparable across steps."""

MS_PER_SAMPLE = 8.3
"""Measured on 2026-10-06: 64 s per 216-record frame at settle 30 / samples 32."""


def recalibration_ladder(settings: UiSettings) -> list[UiSettings]:
    """Recalibration profiles, varied in every capture parameter (ADR-0042).

    Settle ramps 10 -> 200 ms; samples, warmup, frames and DAC vary alongside so
    that consecutive attempts do not repeat the same noise mechanism. Pattern,
    current range and electrode mapping never change -- those change what is
    measured, not how well.
    """
    from dataclasses import replace

    ladder: list[UiSettings] = []
    seen: set[tuple] = set()
    for settle, samples, warmup, frames, dac_frac in zip(
        SETTLE_RAMP_MS, SAMPLES_RAMP, WARMUP_RAMP, FRAMES_RAMP, DAC_STEPS
    ):
        dac = min(int(round(settings.dac * dac_frac)), settings.max_dac_code())
        key = (settle, min(samples, SAMPLES_CEILING), warmup, frames, dac)
        if key in seen:
            continue
        seen.add(key)
        ladder.append(
            replace(
                settings,
                settle_ms=settle,
                samples=min(samples, SAMPLES_CEILING),
                warmup_frames=warmup,
                frames=frames,
                dac=dac,
            ).validate()
        )
    return ladder


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
        x, y = self.centres[self.peak_index][:2]
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
    )


def reconstruct_absolute(
    frames: Sequence[unified.UnifiedFrame], settings: UiSettings
) -> AbsoluteResult:
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
    if recip is None:
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
    candidates: Sequence[UiSettings],
    rounds: int = 1,
    on_attempt: Callable[[int, Attempt], None] | None = None,
) -> tuple[list[Attempt], Attempt | None]:
    """Continuous recalibration: re-acquire with the next profile until the gates pass.

    ``capture(settings)`` configures the instrument, warms up and returns the
    recorded frames. Profiles are tried in order, cycling ``rounds`` times; the
    first passing attempt ends the loop. Returns every attempt and the passing one.
    """
    attempts: list[Attempt] = []
    number = 0
    history: list[tuple[GateReport, tuple]] = []
    for _ in range(rounds):
        for candidate in candidates:
            number += 1
            frames = capture(candidate)
            result, noise, report = evaluate(frames, candidate)
            attempt = Attempt(candidate, frames, result, noise, report)
            attempts.append(attempt)
            if on_attempt is not None:
                on_attempt(number, attempt)
            if report.passed:
                return attempts, attempt
            history.append((report, contact_fault(frames)))
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


def contact_fault(frames: Sequence[unified.UnifiedFrame]) -> tuple[tuple[int, float], ...]:
    """Electrodes flagged as suspect contacts (ADR-0032); empty if none or unscorable."""
    try:
        return capture_view.session_summary(frames).suspect_electrodes
    except Exception:  # noqa: BLE001 - a scoring failure is not a contact verdict
        return ()


def save_absolute(
    attempt: Attempt,
    image_path: Path,
    data_path: Path,
    title: str,
    thickness_mm: float | None = None,
) -> None:
    """Two panels on one scale: structure (sigma - sigma0) and the noise image."""
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
    scale = max(float(np.max(np.abs(result.structure))), float(np.max(np.abs(noise))), 1e-12)

    figure, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    for ax, values, name in (
        (axes[0], result.structure, "sigma - sigma0 (image)"),
        (axes[1], noise, "split-half noise (control)"),
    ):
        mappable = ax.tripcolor(
            pts[:, 0], pts[:, 1], tri, values, shading="flat",
            cmap="RdBu", vmin=-scale, vmax=scale,
        )
        ax.set_title(name)
        ax.set_aspect("equal")
        ax.axis("off")
        for index, x, y in base.electrode_label_positions(eit_mesh):
            ax.text(x, y, f"E{index + 1}", ha="center", va="center", fontsize=8)
    figure.colorbar(mappable, ax=axes, shrink=0.8, label="sheet conductance, mS")

    report = attempt.report
    bulk = f"sigma0 = {result.sigma0:.4g} mS sheet"
    if thickness_mm:
        bulk += f" = {result.sigma0 * 1000.0 / thickness_mm:.4g} S/m"
    verdict = "PASS" if report.passed else "REFUSED: " + "; ".join(report.reasons)
    sig = f"{report.significance:.2f}" if report.significance is not None else "n/a"
    recip = f"{report.reciprocity_percent:.1f}%" if report.reciprocity_percent is not None else "n/a"
    figure.suptitle(
        f"{title}\n{bulk}  |  peak {result.peak_value:+.3g} mS at {result.peak_angle_deg:.0f} deg"
        f"  |  significance {sig}  |  reciprocity {recip}  |  misfit {result.residual_percent:.1f}%"
        f"\n{verdict}  |  circular point-electrode model (ADR-0041)",
        fontsize=9,
    )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(image_path, dpi=150, bbox_inches="tight")
    plt.close(figure)

    np.savez_compressed(
        data_path,
        sigma=result.sigma,
        sigma0=result.sigma0,
        sign=result.sign,
        noise=noise,
        residual_percent=result.residual_percent,
        peak_value=result.peak_value,
        peak_angle_deg=result.peak_angle_deg,
        dropped_indexes=np.asarray(result.dropped_indexes, dtype=int),
        significance=report.significance if report.significance is not None else np.nan,
        reciprocity_percent=(
            report.reciprocity_percent if report.reciprocity_percent is not None else np.nan
        ),
        passed=report.passed,
        pattern=attempt.settings.pattern,
    )
