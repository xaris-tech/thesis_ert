# ADR-0044: Naming gaps warn instead of refusing a scan

- **Status:** Accepted
- **Date:** 2026-10-01
- **Affects:** `run_record.naming_problems`, `run_record.run_label`, `MainWindow.start_capture` / `start_problems`
- **Related:** Supersedes the refusal in [ADR-0037](0037-refuse-a-scan-without-a-named-specimen.md); keeps [ADR-0040](0040-generate-the-run-label-from-specimen-and-target.md)

## Context

ADR-0037 made the Qt UI refuse to start when the medium was not chosen, the specimen ID was
empty or did not match `SPECIMEN_ID_PATTERN`, or a held session baseline was from a different
specimen. At the bench the operator found this too restrictive and asked for the hard gate
to go while keeping the automatic label.

## Decision

The same checks still run, but they are now warnings. They appear in the existing
"Incomplete conditions… Capture anyway?" dialog together with `Conditions.validate()` and are
written to the session log. The label is still generated and read-only (ADR-0040). When there
is no specimen ID, the medium stands in for it (`cut-disc-intact`). If the medium is not one
of `KNOWN_MEDIA` either, `run` is used (`run-baseline`), so every run is named.

## Rationale

The operator decides whether to go ahead, which matches the existing principle that a capture
worth taking is never refused over metadata. Removing the checks completely was rejected
because the gaps that broke the 2026-09-29 records would then pass silently. The warning
keeps them visible at the moment they can still be fixed.

## Consequences

Runs with no specimen ID, or with a free-text medium, can be recorded again. The survey
cannot group them by conditions, so they need a manifest (`disc_survey.py --manifest`).
A run differenced against a baseline from a different specimen now produces an image after
one warning. That image shows the two specimens' difference, not a change in one specimen.
Read it with that in mind.

## Verification

`tests/test_tree_ert_qt.py::StartGateTests.test_naming_gaps_warn_but_do_not_refuse` checks
that an unnamed start shows the question dialog, not the refusal.
`tests/test_run_record.py::RunLabelTests.test_no_specimen_falls_back_to_the_medium` covers
the label fallback.
