# ADR-0045: The run label is editable, pre-filled from specimen and target

- **Status:** Accepted
- **Date:** 2026-10-01
- **Affects:** `MainWindow` label field and `start_capture`, `run_record.naming_problems`
- **Related:** Supersedes [ADR-0040](0040-generate-the-run-label-from-specimen-and-target.md) (read-only label); follows [ADR-0044](0044-naming-gaps-warn-instead-of-refusing.md)

## Context

ADR-0040 made the label read-only, generated from specimen and target. At the bench the
operator wants to name a run themselves. The label is also what the run folder is named after.

## Decision

The label field is editable. It still fills in from `run_label` while the operator has not
typed in it. Once they type, it keeps their text even if specimen or target change. Emptying
the field leaves it empty (it is not refilled mid-edit). The generated name shows as the
placeholder and is used if the run starts with the field blank. The run folder is `<timestamp>-<slugified label>`. The
label is free text, and `naming_problems` no longer checks it.

## Rationale

The operator knows what the run is, and the generated name stays as the default, so a run is
never unnamed. The timestamp prefix stays because reusing a label would otherwise overwrite or
clash with an earlier run. Grouping does not rely on the label: the survey reads `specimen_id`
and `medium` from `conditions.json`, or a manifest.

## Consequences

Labels can drift into describing settings again, which is the 2026-09-29 problem ADR-0040
fixed. That costs readability in the folder listing, not data, because conditions and settings
are recorded separately.

## Verification

`tests/test_tree_ert_qt.py::StartGateTests.test_a_typed_label_sticks_and_clearing_does_not_refill` and
`test_the_label_is_generated_until_typed`, and
`tests/test_run_record.py::NamingProblemsTests.test_any_label_is_accepted`.
