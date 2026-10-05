# ADR-0047: Report NCC and Dice beside SSIM rather than replacing it

- **Status:** Accepted
- **Date:** 2026-10-05
- **Affects:** `tree_ert/ssim.py` (`score`, `SsimScore`, new `ncc` and `dice`), any series scored offline. Does **not** change how reconstructions are produced.
- **Related:** ADR-0045, ADR-0046; `ssim/saline-tank-2026-10-02/`

## Context

ADR-0046 left a specific problem: the reconstruction peaks at 0.27–0.61 R against a
block at 0.80 R, so the recovered image does not resemble a sharp footprint, and every
image-similarity score against that footprint comes out low. SSIM made this worse than
necessary, for a reason that has nothing to do with the reconstruction.

SSIM's luminance term compares absolute brightness. The reconstructed lobe is routinely
dimmer than the mask it is compared against, and SSIM counts that dimness as a
structural mismatch. Separately, SSIM saturates: averaged over a region that is mostly
background, both images approach zero everywhere the mask is not, and the score stops
responding to the target at all. That failure was severe enough to rank all 19 runs of
the 2026-10-02 series below an empty tank before ADR-0046's region fix.

Three alternatives were measured on that series against each run's own empty-tank
control, using a simulated block as the reference image:

| metric | min | max | mean | empty tank | beats its control |
|---|---|---|---|---|---|
| SSIM | −0.061 | 0.272 | 0.130 | 0.023 | 16 / 19 |
| **NCC** | **−0.155** | **0.873** | **0.569** | **−0.011** | **17 / 19** |
| Dice | 0.000 | 1.000 | 0.588 | 0.085 | 15 / 19 |
| mutual information | 0.348 | 0.573 | 0.515 | 0.362 | 16 / 19 |

Mutual information was rejected outright: its empty-tank score (0.362) is most of the
way to its detection score (0.515), so it barely discriminates.

## Decision

Add `ncc` and `dice` to `SsimScore` and populate them in `score()`. Keep SSIM.

`score()` gains an optional `template` argument so both metrics can be computed against
a simulated expected image instead of the geometric mask, which is the comparison that
separated 17 of 19.

## Rationale

**NCC** is the Pearson correlation of the pixel values. Three properties made it the
best of the candidates for this instrument:

- *Scale-invariant.* A correct but dim blob is not punished for being dim, which is
  precisely the artefact that makes SSIM uninformative here.
- *Position-sensitive.* A blob in entirely the wrong place scores near zero. This is
  the property the registered-crop variant destroyed: it scored 0.97 for detections
  **and 0.94 for the empty tank** (see ADR-0046's ruled-out table), because removing
  position is what removed its meaning.
- *No threshold and no tuning.* Dice needs one, and its discrimination is the weakest
  of the three at 15 of 19.

**Why not replace SSIM.** SSIM answers a question NCC does not: SSIM is sensitive to
absolute level and contrast, so it flags a reconstruction whose lobe amplitude is
wrong even when its shape and place are right. That is a real defect class. Dropping a
metric because it is inconvenient for one dataset discards information, and the two
together cost nothing.

**Why Dice is kept despite being weakest.** It is the only one of the three a
non-specialist can read without a glossary: "what fraction of the claimed block is
where the block is". Reporting it costs one threshold, which is stated explicitly as
`DICE_THRESHOLD`.

**What NCC is not.** It is not a similarity index in the SSIM sense and must never be
described as one, nor as "SSIM-like". It measures linear agreement of an intensity
pattern. Two blobs of completely different size but the same bright centre correlate
highly. It carries no null on its own, so **the empty-tank control must be scored the
same way and reported next to it** — the 17 of 19 figure above is meaningless without
the −0.011 beside it.

## Consequences

- Three numbers per run instead of one, each with a different blind spot: SSIM catches
  wrong amplitude, NCC catches wrong place or wrong shape, Dice is readable. None is
  sufficient alone, and the null is mandatory for all three.
- `SsimScore` grew two optional fields, so existing construction and any code reading
  `ssim_raw` is unaffected.
- The scores in `ssim_results.csv` are still stale, because `ssim_eval.py` writes the
  SSIM columns only and has not been changed to emit `ncc`/`dice`. The CSV is a
  generated artifact (ADR-0046) and adding hand-written columns to it would be
  destroyed on the next run, so this is deliberately left as a follow-up rather than
  patched by hand.
- NCC's high score for the centre run (0.873) reflects that a centred blob has no
  radial bias to suffer from. It should not be read as "the centre case works better
  than the others" without that context.

## Verification

`tests/test_ssim.py::NccTests` covers the properties the decision rests on: identical
images correlate 1.0, inverted images −1.0, a dimmed image still 1.0 (the reason NCC is
here), flat images return 0.0 rather than NaN, and a blob at the opposite side of the
tank scores below 0.3 while one in the right place scores above 0.5. `dice` is checked
for the empty/empty and identical-lobe cases.

What is *not* covered: no test pins NCC's discrimination against a real empty-tank
control, because that needs recorded runs and the suite is board-free by design. The
17-of-19 figure comes from the offline pass over `ssim/saline-tank-2026-10-02/` and is
reproducible from the stored `reconstruction.npz` files.