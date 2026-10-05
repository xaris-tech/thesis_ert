# ADR-0046: Reconstruction settings cannot currently be validated, and the recorded series disagrees with the forward model

- **Status:** Accepted
- **Affects:** `phase3a_reconstruct.create_solver`, every reconstruction path, and any claim about target radius or about tuning `jac_normalized`, `p`, `lamb`, or mesh density.
- **Related:** ADR-0044, ADR-0045; `ssim/saline-tank-2026-10-02/`

## Context

Scoring the 2026-10-02 saline series against a forward-modelled template required
knowing where the reconstructed blob *should* land, and that check failed. The block
was placed with its centre about 128 mm from the tank centre — 0.80 R — and
`ssim_results.csv` recorded `peak_radius` between 0.27 and 0.61 R. A factor-of-two
inward collapse, written up in the series README as an inherent property of one-step
JAC reconstruction.

Two candidate explanations:

1. The reconstruction is biased, and `jac_normalized=False` is why.
2. The forward model used for scoring does not reproduce this instrument's
   measurement chain, so simulated ground truth cannot adjudicate the question.

These make opposite predictions, and both were tested.

**Simulated ground truth** (exact `PyEITAnomaly_Circle`, perm 0.08, half-width
0.0708 = the 23 mm block face on a 160 mm radius, 8 angles per radius, driven
through this repository's own `create_solver` + `reconstruct_difference`):

| true R | peak R, `jac_normalized=False` | peak R, `True` |
|---|---|---|
| 0.30 | 0.261 | 0.470 |
| 0.40 | 0.378 | 0.569 |
| 0.50 | 0.423 | 0.635 |
| 0.60 | 0.552 | 0.827 |
| 0.70 | 0.788 | 0.895 |
| 0.80 | 0.843 | 0.898 |

Mean absolute radius error: **0.053 unnormalised, 0.166 normalised.** The
unnormalised solver is the more accurate of the two here, and neither is unbiased —
`True` overshoots outward by up to 0.23 R. Changing the flag was tried and reverted;
it made simulated accuracy worse, not better.

**The recorded series** disagrees. Reconstructing the same runs' stored 108-vectors:

| setting | mean peak R | mean abs angle error |
|---|---|---|
| `jac_normalized=False` (shipped) | 0.40 | 9.4 deg |
| `jac_normalized=True` | 0.80 | 13.8 deg |

So the real data collapses roughly twice as hard as the simulation predicts, and only
the normalised setting puts it back on the photographic radius. An initial sweep that
appeared to confirm the change used an element-resolution disc rather than an exact
circle; the disc's effective radius was larger than nominal, which biased the result
toward the change. The exact-circle rerun reversed the conclusion.

## Decision

Change no reconstruction parameter. Record the discrepancy as an open defect and
name the simulation as unfit for adjudicating reconstruction settings until the
reason for the disagreement is found.

`jac_normalized` stays `False`, `p=0.45`, `lamb=0.01`, `h0=0.12` unchanged.

## Rationale

- **Tuning on one dataset is not validation.** `jac_normalized=True` demonstrably
  improves the 2026-10-02 numbers and demonstrably worsens simulated accuracy. A
  change that helps the only dataset it has been tried on, and is contradicted by an
  independent measurement of the same quantity, is fitted rather than corrected.
- **The photos are ground truth, but one dataset is not a tuning set.** The block was
  demonstrably at 0.80 R. That makes the 0.40 R result wrong, but it does not identify
  *why* — the candidate causes include electrode contact impedance, the block being a
  23x22x51 mm rectangular solid rather than a disc, an unknown wood conductivity, and
  the DAC ceiling clipping the drive on some pairs. Each implies a different fix.
- **Changing a shared solver on this evidence would silently move every image in the
  repo**, including the Qt UI, the CLI, the disc surveys and all committed
  reconstructions, in a direction chosen by one afternoon of analysis.
- `p=0.0, lamb=0.05` was also measured: it moves the recorded series' peaks onto the
  true radius (0.67-0.87 R) *and* lowers mean angle error (9.4 → 7.9 deg). Rejected for
  the same reason — it helps this dataset only, and it degrades simulated accuracy at
  inner radii (mean radius error 0.065 → 0.130). Noted here so the option is not
  silently rediscovered and adopted.

## Consequences

- **The recorded series' radius axis remains untrustworthy.** Any statement about
  target distance from the rim, or about target size derived from image extent, is
  unsupported for all runs in `scans/runs/` and `ssim/`. Angle results are unaffected:
  angle error is measured from the peak's angle, which the inward bias does not
  change.
- **Reconstruction settings are frozen by default, not by decision.** There is
  currently no defensible way to tune them, and no test guards peak radius, so a
  silent change would not fail the suite.
- Synthetic validation of the reconstruction is currently unavailable in principle,
  because the forward model does not describe this instrument. That blocks the
  resolution-study route to choosing `lamb`, and it is a prerequisite for absolute
  reconstruction.
- A one-line diagnostic exists to make progress: compare a simulated measurement
  vector against a real one on the same electrode pair, normalised. If the shapes
  disagree, the contact/measurement chain is the culprit; if they agree, the block
  model is.

## Verification

The two tables above are the check, and they disagree with each other — that is the
finding. Reproduce the simulated table by building the solver with either flag,
driving `PyEITAnomaly_Circle` through `EITForward.solve_eit`, reconstructing with
`reconstruct_difference`, and taking the radius of the strongest resistive element.
Reproduce the recorded table by loading `target` and `baseline` from any
`reconstruction.npz` and doing the same.

What would close this: establishing why a simulated 0.60 R target reconstructs at
0.552 R while the recorded equivalent reconstructs at 0.40 R. Until then the radius
column of any reconstruction is unexplained.