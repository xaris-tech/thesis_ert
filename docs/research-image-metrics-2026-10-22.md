# Which metric should score reconstruction images? (2026-10-22)

The question: what is the best metric for scoring reconstructions and target detection
(SSIM, NCC, Dice, PSNR, MAE, MSE, or the GREIT figures of merit), and which of them
best separates target from no-target on the 2026-10-22 saline position series.

Script: `exports/position-series-20261022-contact-sheet/metrics.py`. Output beside it:
`metrics.csv` (one row per image and reference) and `metrics_summary.csv` (one row per
metric).

## Recommendation

The headline stays as the repo already decided (ADR-0047, ADR-0055,
`docs/verification-protocol.md`): **angular localization error, measured at the lobe
centroid**. It is the only metric whose ground truth (photograph, recorded position) is
independent of the solver.

This data adds one rule. **An angle error must be gated by a detection metric.** On its
own it separates poorly: AUC 0.75 for difference images and 0.71 for absolute. A
no-target image still has *some* resistive lobe, and that lobe falls within 30 deg of an
arbitrary target position about one time in six. In this data the controls' median
error was 11 deg for difference images.

For detection and supporting evidence:

1. **NCC against the same-solver physics template (`ncc_physics`) is the detection
   metric.** It was the only template metric with AUC 1.000 on both difference and
   absolute images. It has the largest standardized gap of any shape metric on absolute
   images (2.43). On difference images its gap is 5.88, close behind SSIM's 6.35. It is
   threshold-free, has no tuning constants and ignores scale, which matters because both
   images are in arbitrary units. This is what ADR-0050 already chose. The caveat in
   `verification-protocol.md` still holds: it measures reproducibility, not correctness.
2. **Significance (peak over split-half control peak, ADR-0027) is the detection gate
   for difference images.** It ties for the largest gap in the table (AUC 1.000,
   gap 6.87), but it is not a localization or shape metric. It is **useless for absolute
   images**: the empty tank's absolute solve passes at significance 36-42, so it measures
   noise, not target presence.
3. **Dice against the template** stays as a readable extent figure: AUC 1.000 on
   difference, 0.933 on absolute. Its 0.5 threshold is a judgement call, and it collapses
   to 0 for any blind sector (E2 absolute).
4. **SSIM against the physics template** is a valid fourth number for difference images
   (AUC 1.000, gap 6.35, the best shape-metric gap). It is weaker on absolute images
   (AUC 0.978, gap 1.42). It has more assumptions than NCC: the C1/C2 constants assume a
   known dynamic range, and its luminance term penalizes a correct but dim lobe. It is
   not recommended as the headline.
5. **Do not report PSNR, MSE or MAE as image-quality claims.** They separate here only
   because both images are first divided by their own peak. After that they behave like
   a monotone, weaker copy of NCC, and the result depends on an arbitrary normalization.
   Against the sharp block mask they are weak (AUC 0.83).
6. **GREIT figures of merit are for characterizing the reconstruction algorithm, not
   for detection.** Resolution (RES) and ringing (RNG) score *better* on the empty tank
   (AUC 0.00 and 0.06), because noise has small blobs and little opposite-sign energy.
   Position error (PE) is centre-ward bias and is the same with and without a target
   (AUC 0.42). Use them as Adler et al. intended: on simulated or phantom targets, to
   compare reconstruction settings.

"Scores best" here means **best separation of target from no-target control, plus
consistency across the three repeats**. It does not mean the largest raw number. A raw
score with no null is uninterpretable: the whole-disc SSIM in
`docs/thesis-fidelity-metrics.md` scored 0.90-0.96 on an empty tank.

## Part A: what each metric measures and assumes

| metric | measures | needs | assumes | fit for EIT here |
|---|---|---|---|---|
| MSE / PSNR | mean squared pixel difference; PSNR = 10 log10(peak²/MSE) | a reference image in the **same units and scale** | intensities are comparable; error is spatially uniform and independent of signal (Wang & Bovik 2009) | poor. EIT images are in arbitrary units, centre-biased and blurred. A mask is binary and the image is continuous, so MSE mostly measures blur and normalization. |
| MAE | mean absolute difference | same as MSE | same as MSE | poor, for the same reasons |
| SSIM | product of local luminance, contrast and structure agreement (Gaussian window), averaged (Wang et al. 2004) | a reference image and a dynamic range L (for C1 = (0.01L)², C2 = (0.03L)²) | the reference is a perfect-quality version of the image; images are on a comparable intensity scale | usable only against a template blurred to the system's resolution, and only averaged near the target. Whole-disc averaging is dominated by the background (`tree_ert/ssim.py`, `REGION_DILATE_PX`). |
| NCC (Pearson r) | linear agreement of the two intensity patterns | a reference pattern | nothing about scale or offset | good: invariant to gain and offset, sensitive to position |
| Dice | 2\|A∩B\| / (\|A\|+\|B\|) of two sets (Dice 1945) | two **binary** sets, so a threshold for a continuous image | the threshold defines the object; small objects are punished hard for one-pixel shifts (Maier-Hein et al. 2024) | usable for extent; the threshold is a judgement call (ADR-0050) |
| GREIT figures of merit: AR, PE, RES, SD, RNG | amplitude response, position error, resolution, shape deformation, ringing, each computed on the 1/4-max (here 1/2-max) set of the image of a **small known target** (Adler et al. 2009) | a known small target and the reconstructed image of it | a known target; used to compare and tune algorithms over many target positions (uniform AR and RES, small PE, SD and RNG) | right for characterizing a solver, wrong for detection: none of them tests "is something there" |
| angle / position error | distance between the reconstructed lobe centroid and the true position | the true position only | the lobe is the target (ADR-0055) | the only metric with ground truth that is independent of the solver. Radial error is biased by the solver (GREIT PE), so angle is the robust part. |
| detection significance | image peak divided by the noise-image peak (ADR-0027) | a noise image in the same units | the noise is stationary | right for detection on difference images |

Why PSNR, MSE and MAE are not meaningful against a binary block mask:

- **Arbitrary units.** The image has to be rescaled first (here, divided by its peak),
  and the score then depends on that choice.
- **Low resolution.** Linear one-step reconstructions spread a small target over a lobe
  many times its area. Adler & Guardo (1996) and Adler et al. (2009) treat this blur as
  a property to measure (RES), not as an error. Pixel error against a sharp mask is
  therefore mostly the solver's point-spread function, and a perfectly located target
  still scores badly.
- **Squared error does not reflect structure.** Wang & Bovik (2009) show that images with
  identical MSE can look completely different. This is why SSIM was proposed. But SSIM
  still assumes a reference image on the same intensity scale.

Detection against a null is a separate question from image fidelity. The standard
summary of separation is the ROC area: the probability that a randomly chosen target
case outscores a randomly chosen control (Hanley & McNeil 1982). That statistic is used
below.

## Part B: what the repo already decided

- ADR-0047: the headline is angle error. SSIM (raw and blurred) is reported beside it.
- ADR-0048: the image is the resistive lobe only, rasterized to 64×64 and scaled to its
  peak. The SSIM window and constants are the Wang et al. defaults. The PSF blur is 0.2 R.
- `tree_ert/ssim.py` `REGION_DILATE_PX`: SSIM averaged over the whole disc rated an empty
  tank 0.90-0.96, higher than any detection. It is now averaged over the dilated mask
  region.
- ADR-0050: NCC and Dice are reported beside SSIM. NCC against a simulated template
  separated the most runs (17 of 19 at that time).
- ADR-0055: the lobe centroid uses a connected component at half of the peak, not a
  window.
- ADR-0068 and ADR-0071: detection means a trough within ±30 deg of the true position,
  with significance ≥2.0 for difference images and the ADR-0041 gates for absolute images.
- `docs/verification-protocol.md` and `docs/thesis-fidelity-metrics.md`: the three
  metrics are angle, NCC and Dice. Each is reported as a margin over its own empty-tank
  control. NCC and Dice may claim reproducibility only.

Nothing below contradicts these decisions. This note adds two findings:

1. Angle error needs a detection gate.
2. Significance is not a detection gate for absolute images.

## Part C: scoring the 2026-10-22 position series

### Data and method

- **Target runs:** 45, from 134226 onward, positions e1-e12 and centre. e1 and e2 were
  run twice, three repeats each time. 212425 is skipped.
- **Difference images:** each run against the empty-last tank 211625
  (`reconstruction.reconstruct`).
- **Absolute images:** log10(σ/σ0) from each run's `absolute.npz`, with E2 excluded.
- **Images:** `ssim.resistive_image`, the resistive lobe scaled to [0, 1].
- **References, three per position:**
  - the sharp block mask (`ssim.block_mask`, at the default "near Ek" radius 55/98);
  - the blurred mask (σ = 0.2 R);
  - a physics template: the same block simulated through the same JAC solver
    (`verify_device.physics_template`).
- **Scoring region:** SSIM, NCC, Dice and the pixel errors use the dilated mask region
  for the mask references, and the whole disc for the physics template.
- **Controls (no target):**
  - Difference images: the empty-first tank 134226 (a real 6.5-hour drift null) and the
    split-half image of 211625.
  - Absolute images: the empty-first (134226) and empty-last (211625) tanks.
  - Each control image is scored against **every** position's reference, giving 26
    control scores per metric.
- **Separation statistics:**
  - **AUC:** the fraction of (target, control) pairs scored against the same reference
    where the target scores better.
  - **Gap:** the standardized mean difference, (mean_T − mean_C)/pooled SD, signed so
    that positive means better.
  - **Repeat SD:** the median, over positions, of the SD across repeats.

### Results

T and C are the medians of the target and control scores. The arrow shows which
direction is better.

**Difference images (vs empty-last 211625)**

| metric | dir | T | C | AUC | gap |
|---|---|---|---|---|---|
| significance | ↑ | 27.7 | 4.80 | 1.000 | 6.87 |
| trough magnitude | ↑ | 0.289 | 0.050 | 1.000 | 6.87 |
| SSIM vs physics | ↑ | 0.731 | 0.074 | 1.000 | 6.35 |
| MAE vs physics | ↓ | 0.054 | 0.219 | 1.000 | 6.27 |
| **NCC vs physics** | ↑ | 0.850 | 0.016 | **1.000** | 5.88 |
| Dice vs physics | ↑ | 0.647 | 0.000 | 1.000 | 5.18 |
| MSE vs physics | ↓ | 0.014 | 0.085 | 1.000 | 5.07 |
| PSNR vs physics | ↑ | 18.7 | 10.7 | 1.000 | 3.59 |
| GREIT AR (mean resistive amplitude) | ↑ | 0.027 | 0.011 | 1.000 | 2.22 |
| Dice vs mask | ↑ | 0.677 | 0.000 | 0.967 | 5.52 |
| Dice vs blurred mask | ↑ | 0.853 | 0.000 | 0.967 | 5.50 |
| SSIM vs mask | ↑ | 0.141 | 0.009 | 0.967 | 3.38 |
| MAE / MSE / PSNR vs blurred mask | | | | 0.967 | 2.8-3.5 |
| GREIT SD | ↓ | 0.091 | 0.190 | 0.967 | 1.94 |
| SSIM vs blurred mask | ↑ | 0.421 | 0.047 | 0.933 | 2.19 |
| 2-D centroid position error (R) | ↓ | 0.184 | 0.856 | 0.922 | 2.46 |
| angle error, single pixel (deg) | ↓ | 4.4 | 29.4 | 0.881 | 1.55 |
| NCC vs blurred mask | ↑ | 0.301 | −0.008 | 0.867 | 1.23 |
| NCC / MSE / PSNR vs mask | | | | 0.833 | 1.1 |
| **angle error, lobe centroid (deg)** | ↓ | 3.6 | 11.0 | 0.750 | 0.98 |
| GREIT PE (\|radial\|) | ↓ | 0.181 | 0.201 | 0.422 | 0.23 |
| GREIT RNG | ↓ | 0.382 | 0.204 | 0.056 | −2.15 |
| GREIT RES | ↓ | 0.276 | 0.204 | 0.000 | −4.89 |

**Absolute images (E2 excluded)**

| metric | dir | T | C | AUC | gap |
|---|---|---|---|---|---|
| **NCC vs physics** | ↑ | 0.741 | 0.117 | **1.000** | 2.43 |
| GREIT AR | ↑ | 0.045 | 0.018 | 1.000 | 4.77 |
| GREIT RNG | ↓ | 0.406 | 0.458 | 1.000 | 3.41 |
| MAE / MSE / PSNR vs blurred mask | | | | 1.000 | 2.0-2.3 |
| SSIM vs physics | ↑ | 0.429 | 0.241 | 0.978 | 1.42 |
| trough magnitude | ↑ | 0.374 | 0.177 | 0.967 | 2.65 |
| GREIT SD | ↓ | 0.125 | 0.333 | 0.967 | 4.14 |
| 2-D centroid position error (R) | ↓ | 0.196 | 1.088 | 0.967 | 2.07 |
| Dice vs physics | ↑ | 0.607 | 0.000 | 0.933 | 2.18 |
| significance | ↑ | 80.9 | 23.0 | 0.900 | 1.87 |
| Dice / NCC / SSIM vs (blurred) mask | | | | 0.80-0.87 | 1.2-2.1 |
| angle error, lobe centroid (deg) | ↓ | 5.9 | 26.6 | 0.714 | 1.07 |
| GREIT RES | ↓ | 0.294 | 0.043 | 0.033 | −2.17 |

The control figures here rest on only two empty-tank images, so treat the absolute
results as indicative.

### Reading the results

- **Best separating metric, both image types:** NCC against the physics template.
  - Difference images: target median 0.850 against control median 0.016, AUC 1.000,
    gap 5.88.
  - Absolute images: target median 0.741 against control median 0.117, AUC 1.000,
    gap 2.43.
  - Repeat SD is about 0.004 or less.
- **Larger gaps on difference images.** Significance and trough magnitude (gap 6.87) and
  SSIM vs physics (6.35) separate more widely on difference images. But significance and
  trough only say that *something* changed, and SSIM vs physics drops to 0.978 / 1.42 on
  absolute images.
- **Absolute empty tanks are not blank.** The empty-tank absolute solves score NCC
  0.40-0.49 against the e5 template, and the empty-last solve passes the gates at
  significance 42. The contact artefacts are structured.
  - This is why absolute separation is weaker, and why significance cannot be the
    absolute gate. The gate there has to be residual and reciprocity (ADR-0041) plus
    comparison against an empty-tank absolute image.
- **E2 is blind in the absolute image (E2 excluded).**
  - Angle error is about 33 deg, Dice is 0 and NCC is about 0.25 for all six E2 runs.
  - ADR-0071 already routes E1-E3 to the difference headline. The metrics agree with
    that choice.
- **Not every absolute run passes its gates.** Runs 135625, 140455 and 160858 still give
  normal NCC and angle values. That is consistent with "a refused image is not
  necessarily wrong, just unlicensed".
- **The difference control is real drift.** 134226 vs 211625 has peak 0.090 against block
  troughs of 0.23-0.36, so it is a stringent null.
- **Mask-based metrics lose about 0.1-0.2 AUC.**
  - The reconstruction peaks nearer the centre than the mask (GREIT PE ≈ 0.18 R). The
    mask radius 55/98 is itself still unmeasured (`NEAR_RADIUS_MM`).
  - A template run through the same solver absorbs that bias. That is also why it cannot
    detect that bias (the reproducibility caveat).

## Limitations

- **Small control set:** 2 control images per image type, scored against 13 references.
  AUC = 1.000 means no overlap in this sample. It is not a population estimate.
- **The physics template is a linear JAC difference template.** For absolute
  (Gauss-Newton log σ) images it is only an approximate shape reference.
- **GREIT measures are adapted.** Half-max is used instead of GREIT's quarter-max, and
  the image is the resistive lobe only. The numbers are not comparable to published
  GREIT tables.
- **Literature claims are cited from the primary records listed below.** No web
  retrieval was done in this session to re-read the PDFs. DOIs should be checked before
  they go into the thesis bibliography.

## References

- Adler A, Arnold JH, Bayford R, Borsic A, Brown B, Dixon P, Faes TJC, Frerichs I,
  Gagnon H, Gärber Y, Grychtol B, Hahn G, Lionheart WRB, Malik A, Patterson RP, Stocks J,
  Tizzard A, Weiler N, Wolf GK (2009). GREIT: a unified approach to 2D linear EIT
  reconstruction of lung images. *Physiological Measurement* 30(6):S35-S55.
  doi:10.1088/0967-3334/30/6/S03. Source for the figures of merit (AR, PE, RES, SD, RNG),
  defined on the quarter-max set of small-target images and used to design and compare
  algorithms, not to detect targets.
- Adler A, Guardo R (1996). Electrical impedance tomography: regularized imaging and
  contrast detection. *IEEE Transactions on Medical Imaging* 15(2):170-179.
  doi:10.1109/42.491418. Treats EIT image quality as detectability of a contrast against
  noise, not as pixel fidelity.
- Wang Z, Bovik AC, Sheikh HR, Simoncelli EP (2004). Image quality assessment: from error
  visibility to structural similarity. *IEEE Transactions on Image Processing*
  13(4):600-612. doi:10.1109/TIP.2003.819861. Source for SSIM's definition, the C1/C2
  constants with K1 = 0.01 and K2 = 0.03, and the 11×11 Gaussian window with σ = 1.5. It
  assumes a distortion-free reference image.
- Wang Z, Bovik AC (2009). Mean squared error: love it or leave it? A new look at signal
  fidelity measures. *IEEE Signal Processing Magazine* 26(1):98-117.
  doi:10.1109/MSP.2008.930649. Source for MSE/PSNR's implicit assumptions and their
  failure to track structure.
- Dice LR (1945). Measures of the amount of ecologic association between species.
  *Ecology* 26(3):297-302. doi:10.2307/1932409. Source for the Dice coefficient, defined
  on presence/absence sets.
- Maier-Hein L, Reinke A, et al. (2024). Metrics reloaded: recommendations for image
  analysis validation. *Nature Methods* 21:195-212. doi:10.1038/s41592-023-02151-z.
  Source for metric choice by task: Dice's instability for small structures, and
  detection and localization as separate problems from segmentation.
- Hanley JA, McNeil BJ (1982). The meaning and use of the area under a receiver operating
  characteristic (ROC) curve. *Radiology* 143(1):29-36.
  doi:10.1148/radiology.143.1.7063747. Source for AUC as a probability that a case
  outranks a control.
- Liu B, Yang B, Xu C, Xia J, Dai M, Ji Z, You F, Dong X, Shi X, Fu F (2018). pyEIT: a
  python based framework for electrical impedance tomography. *SoftwareX* 7:304-308.
  doi:10.1016/j.softx.2018.09.005. The solver used here.
