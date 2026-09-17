# ADR-0030: Reciprocity gates the difference image

- **Status:** Accepted
- **Date:** 2026-09-17
- **Affects:** `tree_ert/reconstruction.py` (`RECIPROCITY_GATE_PERCENT`, `reciprocity_gate`), `tree_ert/qt/worker.py`, `tree_ert/qt/main_window.py`, `run_record.INDEX_COLUMNS` (new `reciprocity_gate` column)
- **Related:** ADR-0003 (reciprocity reported, not enforced), ADR-0017, ADR-0018, ADR-0021, ADR-0026, ADR-0027

## Context

ADR-0003 chose to *report* reciprocity and not enforce it. Since then the saline tank, which
should be reciprocal by physics apart from the electrode interfaces, measured 79.1 % and 73.7 %
median error on 2026-09-16 and 90.6–92.9 % on 2026-09-17. A known wood target near E6/E7 did not
localise: the change was spread evenly across pairs. Every difference image since has been
readable only by the operator remembering that reciprocity was broken; the UI rendered them the
same as a valid image.

Reconstruction maps a change in voltage onto a location using the assumption that swapping drive
and sense electrodes gives the same reading. EIT literature uses reciprocity as a data-quality check
before imaging; good systems reach under 1 %, and about 10 % is described as the poor-but-usable edge.

## Decision

The Qt UI refuses to produce a difference image when either the baseline or the target run has a
median reciprocity error above **10 %**, or has no scorable reciprocal pairs. Capture is never
blocked: frames, summary and index row are still written. An operator checkbox overrides the gate;
an overridden image carries `RECIPROCITY OVERRIDDEN - NOT VALID DATA` in its figure and
`reconstruction.txt`, and every run's index row records `reciprocity_gate` as
`pass` / `fail` / `overridden` (empty for a baseline).

## Rationale

- **Gate the image, not the capture** (operator's choice). Capture must stay possible because the
  reciprocity fault itself is investigated with captured frames. Refusing capture would block the
  work that fixes the problem.
- **10 %** (operator's choice among 5 / 10 / 20 %). A 5 % gate is closer to what a tank should
  physically give but leaves no margin for a DC instrument with polarising nail electrodes; 20 %
  has no literature anchor. 10 % is a judgement, not a derived value.
- **Median, not max.** A single bad pair should cost that pair, not the run; max error is
  dominated by near-zero readings where a percentage error blows up.
- **Both runs gated.** A difference is only as good as its worse side.
- **Unmeasurable fails.** A run with no reciprocal pairs cannot be shown to be good.
- **Override, stamped** (operator's choice over a hard block). A hard block would push the operator
  to the CLI or Tkinter UI, which have no gate and no stamp, which is worse. The stamp sits in the
  figure itself, so a copied PNG still carries it.
- This supersedes ADR-0003's "report, not enforce" for the Qt UI only.

## Consequences

- With the instrument as measured on 2026-09-16/17 (73–93 %), **no un-overridden image will be
  produced** until the reciprocity fault is fixed. That is the intended effect.
- The CLI (`phase3a_unified_reconstruct.py`) and the frozen Tkinter UI (ADR-0024) are **not** gated.
  Images from them carry no such check.
- Images saved before this change are not re-stamped. Their reciprocity is in `index.csv`.
- The baseline's own `control.png` (ADR-0029) is not gated: it is a noise image, not a claim.
- `reciprocity_gate` is appended at the end of `INDEX_COLUMNS`; older rows read it as empty.
- The threshold applies equally to tree and tank. A real tree may never reach 10 % under DC; if so,
  this gate will need revisiting with measured evidence, via a superseding ADR.

## Verification

- `tests/test_reconstruction_module.py::ReciprocityGateTests`: threshold value, pass, boundary,
  fail at the measured 79.1 %, unmeasurable fails.
- `tests/test_tree_ert_qt.py`: `test_failed_reciprocity_refuses_the_image_but_keeps_the_frames`,
  `test_override_images_anyway_and_stamps_it_everywhere`, `test_demo_data_passes_the_gate`.
- Worker tests force the gate with a mock; the gate has **not** been exercised on hardware yet.
  Next hardware run on the tank should show the refusal message in red and `fail` in `index.csv`.
