# ADR-0051: The centroid angle estimator has a measured −0.45° bias; the centroid window was validated

- **Status:** Accepted
- **Date:** 2026-10-05
- **Affects:** how `centroid_angle_error_deg` in `tree_ert/ssim.py` may be quoted, and every angle figure in `ssim/saline-tank-2026-10-02/`. Refines [ADR-0048](0048-take-the-angle-from-the-lobe-centroid.md).
- **Related:** ADR-0048, ADR-0049, ADR-0050

## Context

ADR-0048 replaced the single-pixel angle estimator with a lobe centroid and reported
"median 3.0°, 24 of 24 within 10°, worst 9.9°". That was checked here for the first time
against a *known* answer, which no previous angle claim in this project had been.

Method: place a simulated block of the real footprint at a known radius, rotate it by a
known offset from a chosen electrode, reconstruct it through the same solver, and ask
what the estimator reports. Twelve angles per offset, so the measurement is independent
of any real run.

The estimator **under-reports.** A window centred on the true angle and only ±45° wide
clips an off-centre lobe and drags the centroid back toward the truth:

| injected offset | reported (±45° window) |
|---|---|
| 5° | 4.6° |
| 10° | 8.9° |
| 20° | 16.1° |
| 30° | 23.4° |

So the headline "worst case 9.9°" was flattering itself by roughly half a degree at these
magnitudes, and the effect grows with offset.

## Decision

Test two alternative windows, then keep the ±45° window and **document its bias rather
than correct it in code**.

| window | bias over 0–10° | real series: median / max / ≤10° |
|---|---|---|
| **±45°, truth-anchored (kept)** | **−0.45°** | **2.97 / 9.87 / 24 of 24** |
| ±90°, truth-anchored | +0.11° | 4.70 / 14.32 / 20 of 24 |
| ±45°, peak-anchored | +0.33° | 3.55 / 14.54 / 23 of 24 |

`CENTROID_HALF_DEG` records the choice and the correction to apply.

## Rationale

- **The unbiased-on-paper window is worse on the real data.** ±90° is unbiased on an
  isolated synthetic blob, but real lobes carry neighbouring structure that a single
  simulated block does not, so a wider window contaminates the centroid and drops the
  result to 20 of 24 within 10°. Synthetic bias and real performance disagree, and the
  real series is what gets reported.
- **A peak-anchored window is not safe.** It is unbiased on clean data, but the window
  then follows whatever the argmax found. `tests/test_ssim.py` has a rim-artefact case
  that this window fails outright: the centroid is dragged 13.3° off by a spike 35° away.
- **Correcting in code would hide the problem.** Adding 0.45° inside `score_blocks` makes
  the number look better-motivated while making it impossible for a caller to see that
  a bias correction was applied. `centroid_angle_error_deg` stays raw and the correction
  lives in the docs next to the claim.

## Consequences

- **The quoted angle figures gain a stated uncertainty.** Measured: n = 24, median 2.97°,
  mean 3.00°, max 9.87°, 21/24 within 5°, 24/24 within 10°. With the measured −0.45°
  bias added: median ≈3.4°, max ≈10.3°. So "every placement within 10°" holds as
  measured and is marginal once the known bias is included. Say so rather than rounding
  in your favour.
- The bias is only characterised for 0–30° offsets and at one radius (0.56 of the
  electrode ring). It has not been checked at other radii or against a pair of blocks.
- Two of the three candidate windows are recorded with their numbers so they are not
  silently retried.
- The series README and ADR-0048 quoted the pre-validation figures. ADR-0048 is left
  standing as the decision to use a centroid; its numbers are corrected here and in the
  README.

## Verification

Reproduce from a synthetic block at a known offset — no board and no recorded run
needed. Any future change to `score_blocks` or `CENTROID_HALF_DEG` should be re-checked
against injected offsets before any angle number is quoted, since the failure mode is
silent: a biased estimator still returns plausible-looking degrees.
