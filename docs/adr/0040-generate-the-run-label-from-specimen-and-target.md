# ADR-0040: Generate the run label from specimen and target instead of typing it

- **Status:** Accepted
- **Date:** 2026-09-29
- **Affects:** `run_record.run_label`, `tree_ert/qt/main_window.py` (the Label field, now
  read-only); run folder names from now on
- **Related:** supersedes the label rule (Decision item 3) of
  [ADR-0037](0037-refuse-a-scan-without-a-named-specimen.md); the rest of ADR-0037 stands.
  Defect-vs-intact grouping from [ADR-0038](0038-survey-distances-on-normalised-vectors.md)

## Context

ADR-0037 required the typed label to start with the specimen ID and describe the run. The
operator pointed out that the label only restates what the Conditions panel already holds: which
specimen, and what the run is imaging (the Target field). Typing it twice invites the two to
disagree, and on 2026-09-29 the typed labels described the settings (`coconut-620-dry-32-samples`)
rather than the specimen.

## Decision

The label is generated and read-only: `<specimen ID>-<slugified target>`, or
`<specimen ID>-intact` for a cut disc with no target, or `<specimen ID>-baseline` for any other
medium with no target. It is empty until a specimen ID is entered, and the start gate
(`naming_problems`) still refuses an empty or malformed one.

## Rationale

**One source of truth.** The survey already reads defect-vs-intact from `target_description`, not
from the label (ADR-0038). Deriving the label from the same field means the folder name cannot
say "intact" while the conditions say "hole at E7".

**Why `intact` only for discs.** "Intact" is the ADR-0035 term for an undrilled cut disc. For a
standing tree it would be a claim about its interior that nobody can make, so a tree with no
target is a `baseline`.

**Why settings are not in the label.** They are in `conditions.json` and `index.csv` already, and
the survey refuses mixed settings. Putting them in the folder name repeats them a third time and
gives a label that can disagree with the record.

**Rejected: an editable field pre-filled with the generated text.** It would reintroduce exactly
the drift this removes, one edit at a time.

## Consequences

**Easier.** Starting a run needs only Medium, Specimen and (for a defect) Target. Folder names
match the conditions by construction.

**Harder.** A run cannot carry a free-form note in its folder name. Notes go in the Notes field.

**Will bite later.** Two runs of the same specimen and target differ only by timestamp in their
folder names; repeats are told apart by time, as they already are in `index.csv`. A long target
description is cut to 60 characters by `slugify`.

## Verification

- `tests/test_run_record.py` (`RunLabelTests`): intact disc, target, tree baseline, empty
  specimen, and a generated label always passing `naming_problems`.
- `tests/test_tree_ert_qt.py` (`StartGateTests.test_the_label_is_generated_and_not_typed`): the
  field is read-only and follows Specimen, Target and Medium as they change.
