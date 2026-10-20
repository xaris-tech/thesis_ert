# ADR-0056: Correct recorded run conditions in `extra`, never by overwriting

- **Status:** Accepted
- **Date:** 2026-10-08
- **Affects:** `scans/runs/*/conditions.json`; nine runs in commit `0924091`
- **Related:** ADR-0023 (conditions written when a run opens), ADR-0025 (scans root), ADR-0037/0044 (naming)

## Context

On 2026-10-07/08 the Qt start dialog carried the note "with gel" over from earlier runs. As a result, disc-06 (`20261008-002746`, `-003801`) and disc-08 (`20261008-012754`) were recorded "with gel" although no gel was used. The six disc-01 runs (`20261007-221819` to `-231907`) had an empty note and were also dry.

Gel against dry contacts is now the main variable being compared: gel discs scored 13-25 % reciprocity, and dry discs 6.5-8.7 %. A wrong note would therefore corrupt that comparison.

## Decision

A correction to a recorded run is added as a dated key under `conditions.extra` (`correction_YYYY-MM-DD`), naming its source. The originally recorded fields, including `notes`, and `conditions.md` are left exactly as written.

## Rationale

- **Rejected: overwriting `notes`.** It would destroy the record of what the operator entered at capture time, which ADR-0023 makes load-bearing. It would also hide that a mistake happened.
- **Rejected: a separate corrections file.** A reader of `conditions.json` would not see it.
- **Chosen: a key under `extra`.** `extra` already exists for free-form fields. A dated key is visible next to the original value and can be found with grep.

## Consequences

- Code that reads `notes` to decide gel status will still see "with gel". Any analysis of gel must check `extra` for a correction first.
- `conditions.md` and `index.csv` do not show the correction.
- Root cause not fixed: the start dialog can still carry a stale note into the next run. A dialog change (for example, an explicit gel field) is not implemented.

## Verification

```
grep -l correction_2026-10-08 scans/runs/*/conditions.json
```

This should list exactly the nine runs named above.
