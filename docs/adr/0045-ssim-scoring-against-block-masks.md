# ADR-0045: SSIM is scored on the resistive lobe against block masks, with a 0.2 R blur and per-block wedge search

- **Status:** Accepted
- **Date:** 2026-10-02
- **Affects:** `tree_ert/ssim.py`, `ssim_eval.py`, thesis localisation and SSIM claims
- **Related:** ADR-0026, ADR-0027, ADR-0044

## Context

ADR-0044 committed the saline series to three numbers per run: raw SSIM, SSIM
against a blurred mask, and angle error. That leaves judgement calls: how to
turn the per-element image and the operator's target text into two comparable
rasters, what blur to use, and where to look for each block's peak.
`scikit-image` is not installed in the project venv.

First run (2026-10-02, 14 runs): raw SSIM 0.28–0.59 (mean 0.466), blurred
0.32–0.70 (mean 0.486). Peaks sit at 0.33–0.52 R for blocks at 0.8 R.

## Decision

- Rasterise onto a 64 × 64 grid over the unit disc (5 mm per pixel at R = 160 mm)
  by element lookup, not interpolation.
- Image = the **resistive lobe only**: negate, clip at zero, scale so the
  maximum is 1. The mask is the binary 23 × 22 mm footprint, oriented to the
  radius.
- Block positions come from the mesh's `el_pos`, at 128/160 R for "near Ek" and
  0 for "centre". They are parsed from the target text and never assumed from a
  `180 − 30k` formula.
- SSIM uses Wang et al. (2004) with a Gaussian window (σ = 1.5 px,
  C1 = (0.01)², C2 = (0.03)²), averaged inside the disc only. It is
  implemented on `scipy.ndimage`.
- `ssim_blurred` uses a Gaussian with σ = 0.2 R (`--psf-sigma`).
- Angle error, per block: take the strongest resistive pixel within ±45° of the
  block's true angle. A centre block is searched within 0.4 R and has no angle.

## Rationale

- **Resistive lobe only.** Wood in saline lowers conductivity. Keeping the
  conductive side would let an unrelated artifact score as structure.
- **Wedge search, not the global peak.** For two-block runs the global peak
  finds only one block. ±45° is half the gap between opposite-pair blocks
  (180°) and wider than any single-block error seen (≤ 12°).
- **σ = 0.2 R.** This is about the blob width seen in the 2026-10-02 contact
  sheet. It is a judgement value, not a fitted point-spread function. Blurring
  barely helps SSIM here, because the dominant error is the radial pull toward
  the centre, not width. A larger σ would mostly reward background.
- **Own SSIM.** Adding `scikit-image` for a single function was rejected. The
  formula is short and is tested against the identity case.
- **Element lookup.** Interpolating would smooth the image before SSIM sees it,
  hiding mesh resolution.

## Consequences

- SSIM about 0.5 here reflects a correct angle combined with a wrong radius.
  The thesis must quote angle error beside SSIM and say plainly that raw SSIM
  is depressed by the solver's centre bias.
- A large part of the image is background where both rasters are near zero,
  which pulls SSIM up uniformly. Compare SSIM between runs of this series; do
  not compare it with absolute SSIM values from other papers.
- Angle error from the wedge search is measured at pixel resolution (about
  ±5° at 0.4 R). It can differ by several degrees from the UI's element-centroid
  peak; for example E6 gives +18° here against +9° in the UI.
- The target text must name the electrodes (`e5`, `at 10`, `and e7`) or say
  `at centre`. A run with an empty target is refused, not guessed.

## Verification

- `tests/test_ssim.py` checks: target parsing of every form used on
  2026-10-02; that the mesh puts E1 at 180°, E4 at 90°, E7 at 0° and E10 at
  270°; that the mask lands on the block; that SSIM of identical images is 1;
  that a blob in the right place outscores one in the wrong place; and that a
  conductive lobe scores as nothing.
- `ssim_eval.py <series>` writes `ssim_results.csv` and
  `ssim_contact_sheet.png`. Look at the contact sheet before quoting any
  number.
- σ = 0.2 R is unverified as a point-spread function. Verifying it would take
  fitting the blob width across all runs.
