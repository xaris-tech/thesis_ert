# ADR-0048: Take the reported angle from the lobe centroid, not the strongest pixel

- **Status:** Accepted; its angle figures corrected by [ADR-0051](0051-the-centroid-angle-estimator-has-a-measured-bias.md), which found the estimator under-reports by 0.45 deg
- **Date:** 2026-10-05
- **Affects:** `tree_ert/ssim.py` (`score_blocks`, `BlockScore`, `SsimScore.max_abs_centroid_angle_error`), every reported `angle_error_deg`. Reconstruction is unchanged.
- **Related:** ADR-0044, ADR-0045, ADR-0046, ADR-0047; `ssim/saline-tank-2026-10-02/`

## Context

The operator reported that some of the angle errors in the 2026-10-02 series looked
too bad to be right. E6 was recorded at 18.2 deg off in a run whose neighbours were
within 2 deg, and E6 in its pair at 15.0 deg.

`score_blocks` located each block by taking `argmax` of the resistive lobe inside the
block's ±45 deg wedge. That assumes the single strongest pixel is the block. On the
lobes this solver actually produces it often is not: the reconstruction is broad and
diffuse, and a compact rim artefact within the same wedge can outrank the block's own
maximum while sitting tens of degrees away.

Re-measured both estimators over all 24 angled block placements in the series:

| estimator | mean | median | max | ≤5 deg | ≤10 deg |
|---|---|---|---|---|---|
| strongest pixel (previous) | 5.47 | 2.92 | 18.18 | 15/24 | 20/24 |
| **lobe centroid** | **3.00** | 2.97 | **9.87** | **21/24** | **24/24** |

The centroid also fixes the two-block runs, which is not obvious: a centroid taken over
the whole disc collapses to the tank centre when two lobes merge, giving radius
0.03–0.13 and meaningless angles. Confining the centroid to the block's own wedge —
the region already computed for the search — keeps the two lobes apart, and all six
pair runs land within 4 deg.

## Decision

Report `centroid_angle_deg`, `centroid_radius` and `centroid_angle_error_deg` per
block, and add `SsimScore.max_abs_centroid_angle_error`. Keep `angle_error_deg` and
`peak_radius` as reported fields.

The centroid becomes the headline angle; the single-pixel estimate stays available
because the two disagreeing is itself informative.

## Rationale

- **The max error halves, 18.18 deg to 9.87 deg, and every placement lands within
  10 deg.** On photographic ground truth that is the difference between "two runs look
  wrong" and "the worst run is 9.9 deg off, which is under a third of an electrode
  sector".
- **It needs no new information.** The region was already being computed for the
  argmax; the centroid is a second summary of the same pixels.
- **Wedge restriction is what makes it work for pairs**, and it is free — the region
  already exists, so nothing new can go wrong.
- **Rejected: a Gaussian fit to the lobe.** A more accurate centre in principle, but it
  needs an optimiser and a convergence guard, and it will fit artefacts as readily as
  signal on a lobe this diffuse. The centroid needs neither.
- **Rejected: median of the resistive pixels.** Robust, but the median position of a
  radially-smeared lobe is biased toward the rim, which is the opposite of the error
  being corrected.
- **Kept the single-pixel estimate rather than deleting it.** The gap between the two
  is a usable diagnostic: where they disagree by more than a few degrees, the strongest
  pixel is being captured by something that is not the block.

## Consequences

- The headline angle result improves from "median 2.9 deg, 20 of 24 within 10 deg" to
  **"median 3.0 deg, 24 of 24 within 10 deg, max 9.9 deg"**. Note the *median* is
  essentially unchanged at 2.92 → 2.97; what improves is the tail. Anyone quoting the
  median alone sees no difference, and the old figure should not be described as wrong.
- The centroid is intensity-weighted, so a bright compact artefact still drags it. In a
  synthetic check a spike six times the lobe amplitude placed 35 deg away inside the
  wedge pulled the centroid 7.6 deg off, against 35 deg for the argmax. It is much
  less sensitive, not immune — `tests/test_ssim.py` asserts the ratio rather than a
  tight bound, and the docstring records the limitation.
- `centroid_radius` reads ~0.50 against a block at 0.80, so **the inward radial bias is
  confirmed, not resolved.** Changing the angle estimator does not move it. ADR-0046
  still stands and the radius axis of every existing reconstruction remains untrustworthy.
- `ssim_eval.py` does not emit the centroid columns yet, so `ssim_results.csv` is still
  stale. Same deliberate deferral as ADR-0047: hand-editing a generated file would be
  undone on the next run.

## Verification

`tests/test_ssim.py::CentroidAngleTests` covers the properties the decision rests on:
a bright spike inside the wedge that wins the argmax but leaves the centroid within
half the argmax's error; a clean lobe giving both a correct angle and a radius of 0.8;
two opposite blocks both reported away from the tank centre, which is what wedge
restriction buys; a flat image reporting no centroid rather than NaN; and the
`max_abs_centroid_angle_error` property.

What is not covered: the 24-placement table above is an offline pass over recorded runs,
not a unit test, because the suite is board-free by design.