# ADR-0039: The coconut preset is adjacent / high / DAC 620 / 30 ms / 32 samples, validated

- **Status:** Accepted
- **Date:** 2026-09-29
- **Affects:** `tree_ert/settings.py` (`SPECIMEN_PRESETS`, the "Coconut" entry, formerly
  "Coconut (provisional)"); the locked profile for the intact-disc cohort; field scanning of
  standing trees
- **Related:** preset rules [ADR-0036](0036-specimen-presets-carry-their-provenance.md); cohort
  lock [ADR-0035](0035-intact-disc-survey-measures-between-specimen-spread.md); survey arithmetic
  [ADR-0038](0038-survey-distances-on-normalised-vectors.md); disc vs tree roles
  [ADR-0034](0034-living-tree-images-illustrate-the-cut-trunk-pilot-proves.md)

## Context

ADR-0036 shipped the coconut preset as `Coconut (provisional)` at DAC 400 / 16 samples — the
values that happened to be set — and committed to moving values and provenance together, and to
setting `validated=True` only once tuned.

Tuning on a standing coconut tree on 2026-09-23, one change at a time:

| Change | Result | Kept |
|---|---|---|
| DAC 400 → 500 | noise 0.90 → 0.60 %, offset/signal 3.13 → 2.67× | yes |
| Samples 16 → 32 | noise 0.60 → 0.47 % | yes |
| Settle 30 → 60 ms | apparent gain was drift; a bracketing control at 30 ms read better | no |
| DAC 500 → 620 (`20260923-182816`) | reciprocity 2.5 % median / 32 % max (best of session), weakest pair 191 → 225 ADC steps, worst-pair current 473 µA | open |

The DAC 620 decision was left open pending three back-to-back runs. On 2026-09-29 the profile was
run on a dry cut coconut disc, which is coconut tissue of the kind the cohort will contain:

| Run | Noise | Reciprocity median | Worst pair |
|---|---|---|---|
| `20260929-153440` | 0.45 % | 4.1 % | 478 µA |
| `20260929-154607` | 0.50 % | 4.4 % | 481 µA |
| `20260929-160743` | 0.41 % | 4.5 % | 484 µA |

All three were 216/216 OK with no sign flips. The same disc, drilled near E7-E9, then gave a
difference image peaking in the drilled sector at 3.6× its noise image, and a survey
`S_defect / S_noise` of 2.65 (ADR-0038). Earlier that day the same disc with its surface wetted
gave 0.8 mV signal against 3.6 mV dry, and noise of 11-22 %.

## Decision

The coconut preset is **adjacent / high / DAC 620 / settle 30 ms / 32 samples / 5 warmup /
5 baseline / 5 target warmup / 10 frames**, named `Coconut`, marked `validated=True`, and covers
cut discs and standing trees. Its provenance names both the disc runs and the tree run, the
current margin, and the requirement that the surface be dry.

## Rationale

**Why DAC 620 over 500.** Reciprocity is the project's quality instrument and the reason adjacent
was kept over skip-2. DAC 620 gave the best reciprocity on the tree, and every signal metric
improved over 500. Its noise on 2026-09-23 was ambiguous; on the disc it is the lowest coconut
noise recorded (0.41-0.50 %). Nothing measured favours 500.

**Why validated.** ADR-0036 reserves `validated` for a profile shown to work on the specimen
class. It has been: three consecutive clean runs on coconut tissue, a detected defect at a known
position, and one clean run on a standing tree. The alternative — keeping it provisional until
the tree back-to-back runs exist — would leave the cohort's locked profile labelled as a guess
while the survey is being run on it.

**Why one entry for disc and tree.** The same values were measured on both. `matching_preset`
names the first preset whose values equal the current settings, so two entries with identical
values would show the disc name while scanning a tree, or the reverse, after every restart.

**Why frames stay at 10.** Every run the evidence rests on used 10. Raising it to 20 would reduce
estimator noise, but the profile would then be one nobody has measured.

**The back-to-back question is narrowed, not closed.** The handoff's test was: three runs
agreeing within ~10 % means session drift, ~1.5× apart means estimator noise. The disc's three
runs span 0.41-0.50 % (1.22×), against 1.6× across the tree runs on 2026-09-23. That is better
agreement than before and does not cleanly decide either way. It does not bear on the preset
values, which were not the question.

## Consequences

**Easier.** Selecting `Coconut` gives the profile the disc cohort must be locked to (ADR-0035).
The survey refuses any run at other settings, so the preset is also the cohort's gate in practice.

**Harder.** The profile runs 33-49 s per frame against about 28 s at 16 samples, so 8-12 minutes
per 10-frame run with warmup. The variation between identical runs (33 s for `153440`, 46 s for
`160743`) is unexplained; PGA autoranging is the untested suspect.

**Will bite later.**
- **Current margin is thin.** The worst pair reached 486 µA on the disc and 473 µA on the tree,
  against the 500 µA biological limit in `CONTEXT.md`. The firmware does not enforce that limit.
  A wetter trunk will draw more. The worst-pair current must be checked on the first warmup line
  of every new specimen; if it exceeds 500 µA the DAC comes down for that specimen, and the run is
  then outside the cohort profile.
- **Surface moisture ruins the profile.** Wetting the disc surface cut the signal 4.5× and raised
  noise 25-50×. That is recorded in the provenance, not enforced anywhere.
- **Tree validation rests on one run.** The standing-tree back-to-back runs have still not been
  taken. If they disagree with the disc, this ADR is superseded, not edited.

## Verification

- `tests/test_tree_ert_settings.py`: the Coconut preset carries these values, is validated, names
  its disc and tree runs and the 500 µA limit, and no other preset duplicates its profile.
- `tests/test_tree_ert_qt.py`: choosing Coconut applies DAC 620 / 32 samples / 30 ms and shows the
  provenance without the PROVISIONAL prefix.
- In force when the Settings panel shows `Coconut` with DAC 620 and the survey reports the profile
  `dac=620, samples=32, settle_ms=30`.
