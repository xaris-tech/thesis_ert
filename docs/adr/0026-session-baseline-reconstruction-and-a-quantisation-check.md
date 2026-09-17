# ADR-0026: Session-baseline reconstruction in the UI, and a quantisation check replacing the resistance window

- **Status:** Accepted
- **Date:** 2026-09-16
- **Affects:** `tree_ert/reconstruction.py`, `tree_ert/capture_view.py`, `tree_ert/qt/`,
  `run_record.py` index columns, what a scan folder contains, what a reconstruction image is
  allowed to claim
- **Related:** supersedes the target-resistance window of
  [ADR-0022](0022-titrate-the-medium-with-the-instrument.md); extends
  [ADR-0024](0024-pyqt6-front-end-tkinter-frozen.md) and
  [ADR-0025](0025-dedicated-scans-root-session-log-and-index.md);
  applies [ADR-0002](0002-exclude-untrusted-rows-from-solver.md),
  [ADR-0004](0004-opt-in-pinned-colorbar.md), [ADR-0019](0019-image-the-void-by-inserting-a-target.md)
- **Evidence:** `phase3a_logs/post-repair-baseline-20260902.npz`;
  `tests/test_reconstruction_module.py`, `tests/test_capture_view.py`, `tests/test_tree_ert_qt.py`

## Context

Two things came together in one session on 2026-09-16.

**The resistance window was wrong by two orders of magnitude.** ADR-0022 set a target band of
200 ohm - 2 kohm, described as "tree-like", citing transfer resistances "around 2 kohm". That
figure was not measured. It came from a line in `docs/validity-audit.md` using "a 2 kOhm signal"
as an *illustration* while arguing about drift thresholds. The measured baseline for this
specimen says otherwise:

```text
post-repair-baseline-20260902.npz, 1080 pairs
  median 0.0094 kohm    min 0.0023    max 0.4700
```

**Median 9.4 ohm.** A live capture on the trunk that day read 17 ohm median at 363 uA with
216/216 records OK — a healthy scan that the UI labelled `OUT OF WINDOW` on every frame. The
threshold produced a false alarm on every legitimate measurement, which trains an operator to
ignore the one channel the UI has for saying something is wrong.

**The UI had no reconstruction.** ADR-0024 scoped it out on the reasoning that during a saline
titration the image is the least useful thing on screen. That reasoning does not survive the
move to the trunk specimen, where the image is the point.

## Decision

### Reconstruction

The Qt UI reconstructs difference images, on a **session-baseline** model: the first completed
run of a session becomes the baseline, and every later run in that session is differenced
against it and stores its own image. The baseline run itself has no image, and the UI says so
rather than leaving the absence unexplained. `Clear baseline` re-arms the next run as a new one.

Each imaged run gains `reconstruction.png`, `reconstruction.npz` (values, both vectors, the
dropped mask, the peak) and `reconstruction.txt`, inside its existing run folder. The index gains
`baseline_run`, `peak_value` and `peak_angle_deg`.

Three rules govern what the image may claim:

- **Untrusted rows are dropped from the solver**, not substituted (ADR-0002).
- **Mismatched capture settings are a hard refusal.** Pattern, current range, DAC, settle,
  samples and electrode mapping must match. Frame and warmup counts need not.
- **The colour scale is per-image, and the magnitude is printed on the figure**: peak value and
  angle, the scale itself, kept-pair count, and the measurement noise floor with the sentence
  "a change below this is not a detection". An identically zero image says so in words.

### Quantisation check

The fixed transfer-resistance window is removed. In its place, every frame is scored on how many
ADC steps separate its forward and reverse readings. A pair whose differential is under
**4 steps** is quantisation-limited; a frame with more than **10 percent** such pairs is flagged.
The PGA range is inferred per record using the firmware's own selection rule, since the `FRAME`
record carries converted millivolts and not the gain that produced them.

## Rationale

**Why session-baseline rather than a post-hoc pair picker.** The operator asked that every scan
carry a reading and an image. A pair picker gives neither automatically. The baseline model gives
both while staying physically honest: a difference image needs two states, and the baseline is
the one state everything else is measured against. The baseline id is recorded on the figure, in
`conditions.json` and in the index, so an image can always be traced to what produced it.

**Why a hard refusal on settings mismatch, when reciprocity is only reported (ADR-0003).**
Reciprocity is a matter of degree and gating on it would block legitimate work. Settings equality
is decidable exactly. A difference image survives the open reciprocity violation *only* because a
systematic error stable between the two captures subtracts out — and a settings change is
precisely an error that is not stable between them. Annotating that on the figure was the
alternative and was rejected by the operator: an image that looks confident and is built on
incomparable data is the failure this project has spent months undoing.

**Why per-image colour scaling rather than pinning.** A blank difference auto-scaled to its own
range renders as a vivid, convincing picture of nothing. Pinning to the noise floor would fix
that but makes a real target a featureless blob, and ADR-0004 already made pinning opt-in per run
set. Printing the magnitude keeps single images readable while making the scale impossible to
miss — the operator reads "peak -0.000e+00" under a striking picture and draws the right
conclusion.

**Why the quantisation check replaces the window rather than having its bounds corrected.**
Resistance was the wrong quantity. What limits this instrument is whether the forward/reverse
differential survives the converter, which depends on voltage and the autoranged PGA. That is the
failure already on record: on 2026-08-27 the worst pairs returned `fwd=+60.000 mV` and
`rev=+60.000 mV`, a differential of exactly zero, and D-04's sample averaging was inert because
all 16 samples returned the same count. The new check detects that signature directly rather than
proxying it, and does not fire on a legitimately low-impedance specimen.

**Known imperfections.** Four steps and ten percent are judgement calls, chosen so that one step
cannot be confused with a rounding boundary and so that the legitimately small distant pairs of
an adjacent sweep do not condemn a frame. Neither is derived from a noise model. The baseline is
held in memory, so it does not survive closing the window — a session that spans a restart must
re-baseline. And the peak value is in the solver's arbitrary units while the noise floor is in
kohm, so the figure states both but cannot honestly compare them; deciding whether a peak clears
the floor still requires judgement.

## Consequences

**Easier.** Every scan after the first carries an image, stored with its data and traceable to
its baseline. The negative control — baseline and target with nothing changed — is now a one-click
test of the whole pipeline, and it renders flat, which is what validates it. The UI stops crying
wolf on healthy scans.

**Harder.** The settings gate will refuse comparisons an operator believes are fine, with no
override. Reconstruction adds seconds to the end of each capture. The `.npz` per run adds storage.

**Committed to.** The measurement-settings set in `MEASUREMENT_SETTINGS` now decides what is
comparable; adding a field to it invalidates comparisons that previously worked. `INDEX_COLUMNS`
grew again and stays append-only.

**Will bite later.** A flat image is produced whenever nothing changed *and* whenever the change
is below the instrument's resolution, and the figure cannot distinguish those two cases — only the
noise floor beside it hints at which. The static drilled void remains structurally invisible
(ADR-0019), so a null from this pipeline on an unchanged specimen confirms nothing about the
specimen. And the 4-step threshold was set without a measured noise model; the first time a real
target sits near it, it will need revisiting with data.

## Verification

- `tests/test_capture_view.py` — `QuantisationTests`: range selection mirrors the firmware; the
  exact 2026-08-27 signature (`fwd = rev = +60.000 mV`) scores zero steps and flags the frame; a
  17-ohm specimen at 364 uA is not flagged; a handful of weak pairs does not condemn a frame;
  flagged records are not scored.
- `tests/test_reconstruction_module.py` — identical states reconstruct to nothing; a change
  produces a non-zero image; every measurement setting is gated and frame counts are not; a
  missing setting counts as differing; flagged pairs are dropped rather than substituted; the
  npz round-trips; the caption states the magnitude, the scale and the noise floor.
- `tests/test_tree_ert_qt.py` — a baseline run produces no image *and says why*; a later run is
  differenced and its image, npz and text land in the run folder; the baseline id and peak reach
  the index; a settings mismatch refuses the image while the capture still succeeds; a
  reconstruction failure never fails a capture.
- Full suite: 378 tests passing.
- Manual: a demo baseline/target pair renders a flat grey disc with `peak -0.000e+00` and
  `image is identically zero` on the figure.

**Not verified:** no reconstruction has been produced from real hardware through this path, and
no real target has been imaged. The null behaviour is confirmed; the ability to localise a genuine
target is not.
