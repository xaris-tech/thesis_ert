# ADR-0052: Measure the lobe itself, not a window around it

- **Status:** Accepted
- **Date:** 2026-10-05
- **Affects:** `tree_ert/ssim.py` (`_lobe_centroid`, `LOBE_THRESHOLD`, `score_blocks`), every reported `centroid_angle_error_deg`, and the angle figures in `ssim/saline-tank-2026-10-02/`. Supersedes the window choice in [ADR-0051](0051-the-centroid-angle-estimator-has-a-measured-bias.md).
- **Related:** ADR-0048, ADR-0049, ADR-0051

## Context

ADR-0051 chose between angular windows and kept ±45°, documenting a −0.45° bias. The
operator then asked whether the numbers were accurate, having seen a ~14° deviation
somewhere earlier in the session.

They were right. Putting all three window candidates side by side on every real
placement:

| window | bias (synthetic, 0–10°) | real: median / max / ≤10° |
|---|---|---|
| ±45°, truth-anchored | −0.45° | 2.97 / 9.87 / 24 of 24 |
| ±90°, truth-anchored | +0.11° | 4.70 / 14.32 / 20 of 24 |
| ±45°, peak-anchored | +0.33° | 3.55 / 14.54 / 23 of 24 |

**The window choice moves a single placement by up to 12.3°.** The 14° figures the
operator remembered were real: run `175516` at E5 reads 1.1° under ±45° and 12.5° under
±90°; run `180403` at E6 reads 7.0° and 14.3°. Four placements cross 10° under some
window. The ±45° window that shipped was the one that flattered the result most, and
"24 of 24 within 10°" was an artefact of that choice, not a measurement.

The root problem is that an angular window is the wrong object. A lobe is a physical
region; a window is an analyst's cut through it, and the cut either clips the lobe
(under-report) or admits a neighbour (over-report). There was no principled way to pick
one, which is why picking the best-scoring one was wrong.

## Decision

Drop the window. Threshold the resistive image at half the lobe's peak, take the
**connected component** the strongest pixel falls in, and use that component's
centroid. `LOBE_THRESHOLD = 0.5`. The wedge is retained only to *find* the peak, and as
a fallback if the component is implausibly wide.

## Rationale

- **It removes the analyst's cut.** Nothing is chosen after the fact; the lobe boundary
  comes from the data.
- **Its uncertainty is small where the windows' was not.** Threshold 0.5 → 0.6 moves a
  placement by 1–2°, against up to 12.3° for the window choice. That is the property
  that makes the number quotable with a stated confidence.
- **It does not under-report.** Bias against synthetic blocks at known offsets is
  −0.7° to −0.5° over 0–20°, and it tracks a 30° offset that the ±45° window read as
  23.4°.
- **Rejected: lowering the threshold for a cleaner lobe.** At 0.3 a two-block run's lobes
  merge and the centroid lands 60–170° off — three of 24 placements catastrophically
  wrong. Documented in `LOBE_THRESHOLD`; do not lower it.

## Consequences

- **The headline gets worse and more honest.** n = 24 placements: **median 3.07°,
  mean 3.71°, max 11.87°, 18 of 24 within 5°, 23 of 24 within 10°.** The previous
  "median 2.97°, 24 of 24 within 10°" is withdrawn — it depended on the window that
  flattered it most.
- **"Every placement within 10°" is false.** One placement is outside: run `165444` at
  E2, **11.9°** — the run the series README already identifies as drift-affected. That
  is now a real reported deviation, not one hidden by an analysis choice.
- **The median barely moved** (2.92 argmax → 2.97 → 3.07), which is reassuring: the
  typical placement has been stable throughout. Only the tail was being moved around.
- **A compact artefact still drags the centroid.** The lobe is the component containing
  the strongest pixel, so a spike brighter than the block becomes the lobe. No centroid
  avoids this — the artefact *is* the strongest signal. `tests/test_ssim.py` now
  asserts this as a known limitation instead of asserting a property it does not have,
  and `BlockScore` keeps both `angle_error_deg` and `centroid_angle_error_deg` so a
  disagreement between them stays visible.
- The bias has been characterised only for 0–20° offsets, at one radius, against
  simulated blocks. It is not yet verified at other radii or with noise added.

## Verification

`tests/test_ssim.py::CentroidAngleTests` covers a clean lobe's angle and radius, two
opposite blocks not collapsing to the tank centre, a flat image reporting no centroid,
threshold insensitivity between 0.5 and 0.6, and the artefact limitation. The threshold
sensitivity test mutates `LOBE_THRESHOLD` and restores it, so the guard cannot be left
altered by a failing assertion.

Any future change here should be re-checked both against injected offsets and against
the per-run table in `ssim/saline-tank-2026-10-02/`, because the failure mode is silent —
a biased estimator still returns plausible-looking degrees.
