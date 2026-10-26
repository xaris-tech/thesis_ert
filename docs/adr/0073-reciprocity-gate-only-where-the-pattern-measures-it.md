# ADR-0073: Gate on reciprocity only where the drive pattern can measure it

- **Status:** Accepted
- **Date:** 2026-10-26
- **Affects:** `tree_ert/reconstruction.py` (`pattern_has_reciprocals`), `tree_ert/qt/worker.py` (difference gate), `tree_ert/absolute.py` (`gate`), `tree_ert/acquisition.py` (`SerialAcquisition.connect`); what an opposite / skip image claims
- **Related:** ADR-0030 (reciprocity gate), ADR-0041 (absolute gates), ADR-0043 (stall rule), ADR-0056 (run corrections)

## Context

Reciprocity compares (I:A,B / V:C,D) with (I:C,D / V:A,B). Every pattern this
instrument drives senses on adjacent electrodes, so a measurement's reciprocal is
in the protocol only when its drive pair is adjacent too. Computed from the
protocols: adjacent has reciprocal pairs; opposite, skip-1 and skip-2 have none.

ADR-0030 refuses a difference image when reciprocity "could not be measured", and
ADR-0041 refuses an absolute image the same way. For opposite, skip-1 and skip-2
both gates therefore refuse every run, whatever the contacts are like: the
patterns were selectable but could never produce an image without the
override, which also stamps the image NOT VALID DATA, a claim about the data
that nobody had checked.

The same session (2026-10-26) found a run recorded as opposite whose frames were
all adjacent (`20261026-130420-disc-01-hole-near-e1-e2`). Its 43.4 % reciprocity
looked like an opposite-drive reciprocity, but it was not one. On the Pi's
native-USB port the mode command, the first byte sent after the port opened,
had been lost while the board was booting.

## Decision

The reciprocity requirement applies only to a pattern whose protocol contains
reciprocal pairs (`pattern_has_reciprocals`, derived from the protocol). For any
other pattern the difference image is made and stamped *RECIPROCITY NOT
MEASURABLE - <pattern> drive has no reciprocal pairs; contact quality unverified
by reciprocity*. The index records `reciprocity_gate = not applicable`. The
absolute gate drops the reciprocity reason, but its misfit and significance
gates still apply.

Separately: `SerialAcquisition.connect` waits for the board to answer `?` before
anything is configured, and the capture worker refuses any frame whose pattern
differs from the one requested.

## Rationale

- *Keep refusing*: makes three of four patterns unusable, and gives a refusal
  that says nothing about the data.
- *Use the override*: stamps NOT VALID DATA on images nobody showed to be
  invalid, and trains the operator to tick the override, which blunts it for
  adjacent drive, where it matters.
- *Pass the gate silently*: hides that contact quality was never checked. The
  stamp keeps that visible on the figure, the text and the index.
- *Hard-code "opposite"*: deriving the answer from the protocol also covers skip-1 and
  skip-2, and any later pattern, without a list to keep in sync.

## Consequences

- Opposite and skip images exist now, with no reciprocity check on contacts.
  Contact problems show up only through the other gates (split-half
  significance; absolute misfit) and the per-pair quality flags. One way to
  check contacts for an opposite run is an adjacent run on the same set-up
  just before it; that is not automated.
- Adjacent drive is gated exactly as before.
- A run whose frames do not match the requested pattern now fails instead of
  being recorded under the wrong pattern. A flash that never answers `?`
  still connects (after a 6 s wait); the pattern check then catches a lost mode command.
- `20261026-130420-disc-01-hole-near-e1-e2` is corrected under ADR-0056.

## Verification

`tests/test_reconstruction_module.py::PatternReciprocalsTests`,
`tests/test_absolute.py::GateReciprocityApplicabilityTests`,
`tests/test_tree_ert_qt.py` (`test_opposite_images_without_a_reciprocity_gate`,
`test_frames_of_another_pattern_are_refused`), and
`tests/test_tree_ert_controller.py::TestSerialWaitsForBoot`. Not yet confirmed on
the board: an opposite capture on the Pi whose frames report `opposite`.
