# Scans

Every capture taken from **2026-09-16** onward, recorded by the PyQt UI
(`tree_ert_qt.py`). See [ADR-0025](../docs/adr/0025-dedicated-scans-root-session-log-and-index.md).

This is the documented series. Everything in here has a conditions sheet saying
what the specimen was when it was measured. The ~190 flat CSVs in
`phase3a_logs/` are the legacy capture path and carry no such record — they are
not part of this series and should not be mixed into it.

## Layout

```text
scans/
    index.csv                       one row per scan, with conditions and headline metrics
    session.log                     append-only log of every session, across runs
    ui_settings.json                last-used instrument settings
    runs/
        20260916-144022-step-1/
            conditions.json         conditions, settings, git commit, unrecorded fields
            conditions.md           the same, for the lab notebook
            frames.csv              every record of every frame, unaveraged
            summary.txt             reciprocity and noise floor for the run
            raw/frame-001.txt       verbatim serial text as received
            media/                  photographs; the top-down tank shot is ground truth
```

## Reading it

`index.csv` is the table to open first — it is built for exactly the comparisons
this project needs:

- **Titration series** — sort by `saline_g_per_l`, read `frames` and the
  reciprocity columns. Resistance should fall monotonically with concentration.
- **CMRR test** — filter by `grounding`, compare `reciprocity_median_percent`
  between `floating` and `grounded` at the same concentration (ADR-0021).
- **Detection floor** — `noise_median_kohm` and `noise_median_percent` are the
  frame-to-frame spread. A later difference smaller than this is not a detection.
- **What actually happened** — `outcome` is `complete`, `cancelled` or `failed`.
  Failed and cancelled scans are indexed too; a series with gaps in it is a
  series someone will otherwise misread.

The index is a convenience, not the record. Every value in it also lives in the
run's own `conditions.json`, which is the authority if they ever disagree.

`session.log` holds what the UI printed, including the parts that never reach
`frames.csv`: discarded warmup frames, a cancelled attempt, a failure and the
retry after it. That is usually where the answer is when a run looks odd.

## Caveats

- `conditions.json` records what the operator **typed**, not what was true. A
  mistyped concentration looks exactly as authoritative as a correct one. The
  photograph in `media/` is the only independent check.
- A `git_commit` ending in `-dirty` means the run was taken against uncommitted
  edits and is not reproducible from the hash alone.
- Demo-mode runs are synthetic. They exercise the pipeline; their numbers are
  fixture artifacts, not instrument performance.
