# ADR-0029: A baseline run saves its own control image, named as noise

- **Status:** Accepted
- **Date:** 2026-09-17
- **Affects:** `tree_ert/qt/worker.py` (`CaptureWorker._save_baseline_control`), contents of `scans/runs/<run>/`
- **Related:** ADR-0023, ADR-0026, ADR-0027

## Context

Under the session-baseline model (ADR-0026) the first run of a session is the reference and
has no difference image. Its run folder held only `conditions.*`, `frames.csv` and
`summary.txt`, while every later run folder also held `reconstruction.png/.npz/.txt`. The
operator asked that the baseline folder carry an image too, so that every run folder has one.

A baseline has nothing to be differenced against, but it does have the control image of
ADR-0027: its first half of frames against its second half. That image was already computed
for every later run, but only ever saved inside the *later* run's folder.

## Decision

When a run completes as the session baseline with at least 4 frames, the worker saves the
split-half control of that run into its own folder as `control.png`, `control.npz` and
`control.txt`. The figure title and text file state that it is noise, not a reconstruction.

## Rationale

- **Named `control.*`, not `reconstruction.*`.** A file named `reconstruction.png` in a baseline
  folder would read as a detection. Every image in this project auto-scales to fill its colour
  range, so a noise image looks as vivid as a real one (the misreading ADR-0027 exists to
  prevent). The file name is the one label that survives being copied out of the folder.
- **Rejected: a copy of the first target's two-panel figure.** That image belongs to the target
  run, and it does not exist when the baseline is saved.
- **Rejected: a blank placeholder image.** It would carry no information. The control image
  tells a reader how quiet the reference was, which decides whether any later run could be
  significant at all.
- Fewer than 4 frames: nothing is saved and the log says why, matching `split_half_control`,
  which refuses to understate noise from single-frame halves.
- A failure while saving never fails the capture, like the existing reconstruction path.

## Consequences

- Every baseline folder with at least 4 frames now has an image; target folders are unchanged.
- The index (`index.csv`) is not changed: the baseline's control peak is not recorded there.
  A reader comparing baselines must open `control.txt`.
- Runs captured before this change have no `control.*` files. They can be regenerated from
  `frames.csv`, but nothing does that automatically.
- Tkinter UI and CLI are not changed (Tkinter frozen, ADR-0024).

## Verification

`tests/test_tree_ert_qt.py`:
`test_a_baseline_run_saves_its_control_image_not_a_reconstruction` (files present, no
`reconstruction.png`, text says noise) and `test_a_short_baseline_saves_no_control_and_does_not_fail`.
Both run against `DemoAcquisition`. Not yet verified on a hardware session.
