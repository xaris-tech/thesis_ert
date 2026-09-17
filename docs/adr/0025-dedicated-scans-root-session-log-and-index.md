# ADR-0025: A dedicated scans root, an append-only session log, and a scan index

- **Status:** Accepted
- **Date:** 2026-09-16
- **Affects:** where captures are written, `run_record.py`, `tree_ert/qt/`, `tree_ert_qt.py`,
  what a thesis reader can check about a series
- **Related:** extends [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md);
  serves [ADR-0021](0021-saline-tank-as-the-deferred-phantom.md) and
  [ADR-0022](0022-titrate-the-medium-with-the-instrument.md);
  [ADR-0024](0024-pyqt6-front-end-tkinter-frozen.md)
- **Evidence:** `tests/test_run_record.py`, `tests/test_tree_ert_qt.py`

## Context

ADR-0023 gave each capture a self-contained run folder, and ADR-0024 built a UI that cannot
write a run without also writing its conditions. Three gaps remained, and all three bite in the
saline-tank sessions those ADRs exist to serve.

**The runs had nowhere of their own.** They were written under `phase3a_logs/`, alongside ~190
flat CSVs from the legacy capture path. Those legacy files record nothing about the specimen,
which is the defect ADR-0023 was written to fix — and mixing the two makes the fix unverifiable
by inspection. "Does every capture in this series have a conditions sheet?" stopped being a
question anyone could answer by looking at a directory.

**The log was in-memory.** The UI's log pane showed warmup frames, quality flags, cancellations
and failures, and then discarded all of it when the window closed. That material never reaches
`frames.csv` by design — warmup frames are deliberately not recorded — yet it is often the only
evidence of why a recorded run looks the way it does. A frame that read badly before the run
started, an attempt cancelled and retried, a serial failure: all invisible afterwards.

**Nothing listed the series.** ADR-0022 titrates the medium across many short captures, and the
analysis is a table: resistance against concentration, reciprocity against grounding. Building
that table meant opening twenty directories and reading twenty JSON files by hand, which is how
a series stops being analysed.

## Decision

Captures are recorded under a dedicated **`scans/`** root, separate from `phase3a_logs/`. It is
the default for `tree_ert_qt.py`; `--log-dir` still overrides it.

The root gains two files beside `runs/`:

- **`session.log`** — append-only, timestamped, one per root rather than one per run. Everything
  the UI's log pane prints is mirrored to it, with a banner at each session start, each run, and
  each session end. It survives closing the window and accumulates across sessions.
- **`index.csv`** — one row per scan: identity, the full conditions, the instrument settings, the
  frame count, the reciprocity and noise-floor metrics, the git commit, and an `outcome` of
  `complete`, `cancelled` or `failed`.

Cancelled and failed runs are indexed too.

Settings are migrated once from the legacy folder on first use of the new root, so moving does
not silently reset the port and current range the operator had already dialled in.

`scans/README.md` states the layout, how to read the index for each comparison this project
needs, and the caveats.

## Rationale

**Why a separate root rather than a subfolder of `phase3a_logs/`.** The point is that membership
is checkable by looking. Everything under `scans/` has a conditions sheet; nothing in
`phase3a_logs/` does. A subfolder would preserve the ambiguity it is meant to remove, and a path
that still reads `phase3a_logs` invites exactly the mixing this is avoiding.

**Why the session log is per-root, not per-run.** During titration the interesting sequence is
usually *between* runs — salt added, stirred, rescanned, abandoned, retried. Splitting that
across run folders would fragment the one narrative that explains the series. Per-run material
is already in the run.

**Why index failed and cancelled runs.** A series with silent gaps is a series someone will
misread: a missing step looks like a step that was never attempted rather than one that failed.
Recording the outcome makes the gap legible. Indexing on failure is best-effort and wrapped —
a second failure while recording the first must not replace it in the error the operator sees.

**Why an index at all, when every value is already in `conditions.json`.** It is a convenience
and is documented as one, with the run folder named as the authority on disagreement. The
justification is purely that the convenience is load-bearing: the ADR-0022 analysis is a table,
and a table that takes twenty file-opens to assemble does not get assembled.

**Why `index_row()` lives on `RunRecorder`.** So the conditions and settings in the index come
from the same objects that wrote `conditions.json` and cannot drift from them. The caller
supplies only the computed metrics.

**Known imperfections.** The index is append-only and never reconciled against `runs/`: delete a
run folder and its row remains, edit a `conditions.json` by hand and the index still shows the
old value. Rebuilding it from the run folders would fix that and is not implemented. The
alternative of computing the table on demand from the run folders was considered and rejected
for now as more code than the problem currently justifies — but it is the better long-term shape
and this ADR should be superseded rather than patched if the drift becomes real.

## Consequences

**Easier.** The documented series is unambiguous and checkable by inspection. The titration and
grounding comparisons are one CSV open. Sessions accumulate a narrative that survives restarts.
A failed or abandoned scan leaves a trace instead of a hole.

**Harder.** There are now two capture roots, and the CLI and Tkinter paths still write to the old
one — a reader has to know which tool produced which. `index.csv` is a second copy of data that
already exists, so it can drift from its source.

**Committed to.** `scans/` is now a documented layout other tools may read. `INDEX_COLUMNS`
should be treated as append-only: `append_index_row` ignores unknown keys and writes missing ones
empty, so adding a column cannot break reading an older file, but renaming one breaks every row
already written.

**Will bite later.** The index records what the operator typed, with the same authority as a
measured value, and nothing cross-checks it — a mistyped concentration produces a clean-looking
table with a wrong point in it. The per-run photograph is the only independent check, and it is
only as good as the discipline of taking it.

## Verification

- `tests/test_run_record.py` — `SessionLogTests` (timestamping, flushing before close, appending
  across sessions, banners), `ScanIndexTests` (header written once, missing values empty, unknown
  keys ignored without shifting columns, float formatting, ordering), `IndexRowTests` (the row is
  built from the run's own conditions and settings).
- `tests/test_tree_ert_qt.py` — a completed demo capture appends exactly one indexed row; three
  captures accumulate three rows carrying their concentrations; a cancelled run indexes as
  `cancelled` with the frames it got; a run that fails on the first frame still reaches the index
  as `failed`; the log pane is mirrored to a file that survives the window and appends across two
  windows; startup reports the folder and counts existing scans; settings migrate from the legacy
  folder exactly once and never overwrite live settings.
- Full suite: 331 tests passing.

To falsify: run a capture, kill the process mid-run, and confirm `session.log` holds the frames
logged so far and `index.csv` does not yet hold the run. Then check the run folder is still
readable — the crash-safety claim of ADR-0023 is what makes an unindexed run recoverable.
