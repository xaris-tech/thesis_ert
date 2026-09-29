# ADR-0037: Refuse to start a scan without a named specimen, and refuse a cross-specimen baseline

- **Status:** Accepted
- **Date:** 2026-09-29
- **Affects:** `run_record.naming_problems`, `run_record.baseline_specimen_problem`,
  `run_record.KNOWN_MEDIA`, `run_record.SPECIMEN_ID_PATTERN`, `tree_ert/qt/main_window.py`
  (`ConditionsPanel.medium`, `MainWindow.start_problems`, the Start button),
  `tree_ert/qt/worker.py` (`SessionBaseline.specimen_id`); every run recorded from now on
- **Related:** recording rules [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md);
  specimen identity [ADR-0033](0033-record-specimen-geometry-with-every-run.md); the survey that
  groups by specimen [ADR-0035](0035-intact-disc-survey-measures-between-specimen-spread.md) and
  [ADR-0038](0038-survey-distances-on-normalised-vectors.md)

## Context

ADR-0033 added `specimen_id` and ADR-0023 made every conditions field optional, returning
warnings rather than refusing, so that a capture already worth taking is never lost over
metadata. On 2026-09-29 that policy failed completely on identity:

- Every one of 20 runs that day — resistor belt and cut disc alike — was recorded as
  `medium=saline tank`, because that was the pre-filled text in the Medium box.
- Not one run had a `specimen_id`. The disc used for the first drill test has no recorded
  identity; its survey manifest carries the placeholder `disc-01`.
- Labels were descriptive of settings (`coconut-620-dry-32-samples`) but not of the specimen,
  so the disc runs are named as if they were the standing tree.
- The "Incomplete conditions — capture anyway?" dialog appeared on every run and was clicked
  through every time. A warning that always fires is not read.

ADR-0035 groups runs by specimen, and ADR-0035's own Consequences flagged the other half: the UI
would happily difference two different specimens, because `MEASUREMENT_SETTINGS` checks
instrument settings only. The operator asked for naming to be enforced hard: never let a scan
start without the right naming.

## Decision

Starting a capture in the Qt UI is **refused** — not warned about — until:

1. **Medium** is one of a fixed list (`cut disc`, `standing tree`, `resistor belt`,
   `saline tank`, `dummy load`), chosen from a dropdown that starts blank.
2. **Specimen ID** is lowercase words joined by hyphens, ending in a number
   (`disc-03`, `coconut-tree-1`).
3. **Label** starts with the specimen ID followed by a description of the run
   (`disc-03-intact`, `disc-03-hole-e7`), compared after slugifying.
4. If a session baseline is held, it is **of the same specimen**. A different specimen, or a
   baseline taken with no specimen ID, is refused until the baseline is cleared.

Everything else in `Conditions.validate()` stays a warning.

## Rationale

**Why block identity when ADR-0023 refuses to block anything.** ADR-0023's argument is that a
value may honestly not have been measured, and refusing the run would lose the data as well as
the value. That holds for water temperature or disc thickness. It does not hold for identity:
which specimen is on the bench is always known at the bench, costs seconds to type, and is
unrecoverable afterwards. The 2026-09-29 record shows the warning path produces no identity at
all. So identity moves from "warn" to "refuse" and nothing else does.

**Why a fixed medium list rather than free text without a default.** Free text lets
`coconut trunk`, `coconut`, `disc` and `cut disc` all describe the same thing, and the survey's
`--medium` filter would silently split one cohort. The list is short and extendable; adding a
medium is a one-line change, reviewed like any other.

**Why the specimen ID must end in a number.** `disc` names a kind, not a specimen. Requiring a
number is the cheapest rule that forces an individual to be named.

**Why the label must start with the specimen ID.** The run folder name is what survives in
listings, `index.csv` and the session log. A folder named `coconut-620-dry-32-samples` for a
disc is actively misleading. Checking the slug, not the raw text, means `Disc-03 Hole E7` passes
because its folder is `disc-03-hole-e7`. A label that is only the ID is refused because it does
not say what the run is.

**Why the baseline check lives here and not in `reconstruction.require_compatible`.** The
settings gate compares two settings dicts and raises inside the worker, after the capture. A
specimen mismatch is known before a single frame is taken, so it is refused at Start, where the
fix — clear the baseline — is one click away. A baseline with an empty specimen ID is refused
rather than assumed to match: the gate exists because matching cannot be assumed.

**Rejected: a naming convention for the descriptor (`intact`, `hole-<electrode>` ...).** The
survey reads defect-or-intact from `target_description`, not from the label, and a vocabulary
for descriptors would be guessed before the drill tests have shown what needs describing.

## Consequences

**Easier.** Every run from now on can be grouped by specimen without a manifest
(`disc_survey.py --from-conditions`). Differencing two discs by accident is no longer possible.

**Harder.** Starting a run costs typing a specimen ID and a matching label. The Label field now
starts empty, so the old default `tank-baseline` no longer appears.

**Committed to.** Identity is required, not optional. Extending `KNOWN_MEDIA` is the only way to
record a new kind of specimen.

**Will bite later.** Only the Qt UI enforces this. The CLI (`phase3a_unified_reconstruct.py`) and
the frozen Tkinter UI (ADR-0024) do not write run records through this path and are not gated.
Runs recorded before today remain unnamed and need a manifest to enter the survey. The rule does
not check that the ID typed is the specimen actually on the bench — it forces a name, not the
right name.

## Verification

- `tests/test_run_record.py` (`NamingProblemsTests`, `BaselineSpecimenTests`): the naming and
  baseline rules as pure functions, including prefix collisions (`disc-03` vs `disc-030`).
- `tests/test_tree_ert_qt.py` (`StartGateTests`): a fresh window cannot start; a refused start
  launches no worker thread; a different specimen is refused while a baseline is held and
  allowed after clearing; the baseline records its specimen.
- In force when every run in `scans/index.csv` after 2026-09-29 has a medium from the list and a
  specimen ID matching the pattern.
