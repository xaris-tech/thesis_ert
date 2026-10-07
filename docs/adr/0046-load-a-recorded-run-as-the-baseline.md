# ADR-0046: Load a recorded run as the baseline, remembered as the default

- **Status:** Accepted
- **Date:** 2026-10-01
- **Affects:** `tree_ert/qt/worker.py` (`baseline_from_run`, `read_default_baseline`,
  `write_default_baseline`, `cross_specimen_note`), `tree_ert/qt/main_window.py`
  ("Load baseline from run..." button, startup load), `<scans root>/default_baseline.txt`,
  every reconstruction made against a baseline from another specimen
- **Related:** ADR-0026 (session-baseline model), ADR-0027 (split-half significance),
  ADR-0035/0038 (intact-disc survey), ADR-0037/0044 (cross-specimen baseline warns)

## Context

Until now the Qt UI's baseline was always the first run of the current session (ADR-0026).
A restart lost it, and there was no way to reconstruct a scan against an earlier recorded run.

The operator wants to test whether a defect can be found without a before-scan of the same
specimen. The test: take an intact disc's recorded run as a fixed reference, scan other discs
(some intact, some drilled) against it, and see whether the drilled ones stand out. The trees
would come later.

The 2026-10-01 survey measured S_between = 131 % across the intact discs on adjacent drive.
That is about 40× the expected hole effect. So a difference image against another specimen's
baseline is dominated by the difference between the specimens, not by the defect.

## Decision

The Qt UI can load any recorded run under `runs/` as the baseline. The chosen run id is written
to `<scans root>/default_baseline.txt` and loaded again at startup until "Clear baseline" is
pressed.

Any image whose baseline specimen differs from the run's specimen is stamped
`CROSS-SPECIMEN BASELINE (<baseline> -> <run>)` on the figure, in `reconstruction.txt` and in
the log. The stamp also applies when either specimen ID is unrecorded.

## Rationale

- **Frames come from `frames.csv` through `survey.load_frames`, the same path the survey
  uses.** A second parser would invite a mismatch between the survey's numbers and the
  image's numbers.
- **Settings come from the run's own `conditions.json`.** The existing settings gate
  (`reconstruction.require_compatible`) therefore still refuses a target taken under a
  different pattern, DAC, current range, settle or sample count. Loading a baseline does
  not weaken comparability.
- **A cross-specimen image is stamped, not refused.** Refusing it would block the very
  experiment being run. ADR-0044 already turned the cross-specimen start check into a
  warning. The stamp keeps that warning on the image itself, where a reader of the PNG will
  see it.
- **A file holds the default instead of a `UiSettings` field.** A baseline is a choice about
  data, not an instrument setting, and adding it to `UiSettings` would put it into
  `settings_to_dict` and so into every run's recorded settings.
- **Rejected: averaging several intact discs into a cohort baseline.** It may be the better
  reference later. It needs a survey-style vector average rather than a frame list, though,
  and one disc is enough to run the first test.

## Consequences

- A cross-specimen difference image is mostly specimen difference. A visible blob is not
  evidence of a defect. The test is only interpretable when intact discs are imaged against
  the same baseline alongside the drilled one, and the drilled disc's peak must clearly
  exceed theirs.
- The significance ratio (ADR-0027) still uses the baseline's split-half control. That
  control knows nothing about specimen-to-specimen spread, so for a cross-specimen image it
  overstates significance even more than the 2026-10-01 inter-run false positive (3.6×) did.
  Do not read significance as detection here.
- The stamp's identity comes from `conditions.json`. Runs recorded with a wrong specimen ID
  (several 2026-10-01 disc-4 runs say `disc-07`) are stamped wrongly. The survey manifests
  remain the source of truth for identity.
- A remembered default whose run has disappeared or holds no frames is forgotten at startup
  and logged. It does not crash the window.

## Verification

`tests/test_tree_ert_qt.py::LoadedBaselineTests` covers rebuilding a recorded run into a
baseline, reconstructing against it, the settings gate still refusing a mismatch, the
cross-specimen stamp, the default round-trip, startup loading, clearing, and a stale default.
Smoke-checked on 2026-10-01 against the real runs `20261001-2043..2117-coco-disk-04-opp`
(10 frames each, opposite drive, DAC 620). Not yet checked on the bench by an operator.
