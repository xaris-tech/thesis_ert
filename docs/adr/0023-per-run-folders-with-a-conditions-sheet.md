# ADR-0023: Per-run folders with a conditions sheet supersede flat timestamped logs

- **Status:** Accepted
- **Date:** 2026-09-11
- **Affects:** `run_record.py`, `phase3a_logs/` layout, what any capture is allowed to claim
  in the thesis, every future capture session
- **Related:** enables [ADR-0021](0021-saline-tank-as-the-deferred-phantom.md) and
  [ADR-0022](0022-titrate-the-medium-with-the-instrument.md); supersedes nothing, but the flat
  `phase3a-<pattern>-<stamp>.csv` convention is now the legacy path
- **Evidence:** `phase3a_logs/` held 194 flat files at the time of writing, none of which
  records the state of the specimen they were taken from

## Context

Every capture to date writes a single timestamped CSV into a flat `phase3a_logs/` directory.
The *instrument* state survives — the `FRAME` header carries pattern, DAC code, settle time and
sample count — but the *specimen* state is recorded nowhere. What the trunk's moisture was,
where a target sat, whether anything was grounded: all of it lived in conversation and in the
operator's memory.

On a trunk this was survivable. The specimen changed only between sessions, and a date was
usually enough to reconstruct what it had been.

The saline tank breaks that. ADR-0022 titrates the medium *during* a session: tap water, then
salt added in measured increments, rescanning after each. Ten captures minutes apart, each at a
different conductivity, produce ten files distinguishable only by a timestamp. Nothing in the
data says which concentration produced which file. The dataset is unusable within an hour of
being collected, and no later analysis can repair it.

The same gap already limits existing data. `phase3a_logs/20260906-232050-reciprocity.csv` scores
reciprocity, but nothing in the tree states the water status or temperature it was taken at —
both documented major confounds in tree ERT (Frontiers in Plant Science, 2019). A reviewer
asking "under what conditions" has no answer available.

## Decision

Each capture writes a self-contained directory under `phase3a_logs/runs/`:

```text
runs/<timestamp>-<label>/
    conditions.json     conditions, instrument settings, git commit, incompleteness list
    conditions.md       the same, rendered for a lab notebook
    frames.csv          every record of every frame, unaveraged
    raw/frame-NNN.txt   verbatim serial text as received
    media/              photographs; the top-down tank shot is ground truth
```

`run_record.Conditions` names the fields explicitly rather than accepting a free-form dict:
medium, saline g/L, fill depth, water temperature, electrode protrusion, grounding state, tank
contents, target description, electrode map, operator, notes.

Three properties are load-bearing:

- **Conditions are written when the run opens, not when it closes.** A session that crashes
  mid-capture still leaves an interpretable run.
- **Frames are stored unaveraged, and flushed one at a time.** Frame-to-frame spread *is* the
  noise floor, and the noise floor is what licenses any detection claim.
- **Unrecorded fields are named in the record itself**, in an `incomplete` list, rather than
  being indistinguishable from fields that happened to be zero.

## Rationale

**Why named fields rather than a free-text note.** A note is written when the operator
remembers. A field is visibly empty when they do not, and `validate()` turns that into an
explicit line in the run's own record. The titration variable in particular has to be
machine-readable: the whole point of ADR-0022 is plotting resistance against concentration,
which a prose note cannot support.

**Why `grounding` is flagged when unrecorded, unlike the other optional fields.** It is the
discriminator for the surviving CMRR hypothesis behind the 57.5 percent reciprocity violation
(ADR-0017, ADR-0018). A run whose grounding state was not noted cannot join the
floating-versus-grounded comparison at all, so silence about it is a defect rather than a gap.

**Why the raw serial text is kept alongside the parsed CSV.** The parsed CSV is a lossy view: a
record the parser rejected leaves no trace in it. When a later argument turns on whether the
instrument or the parser was at fault — and on this project that argument has already happened
more than once — the raw text is the only artifact that can settle it. The cost is a few
kilobytes per frame.

**Why not extend the existing CSV header with comment lines.** Considered and rejected. It
keeps data and metadata inseparable, which is the main virtue, but it requires a reader-side
parser change everywhere, and images and reports still land in a different directory from the
conditions that produced them. A directory keeps everything together without touching the CSV
format that `phase3a_unified_reconstruct.py` and its tests already agree on.

**Why not a single append-only session logbook.** Lowest effort, and it was the operator's
fallback choice. Rejected because the link from a logbook row to its data file is by filename
convention only, and because it depends on the operator writing the row — the same failure mode
that produced 194 undocumented files.

**Why a new top-level module rather than a method on `FrameLogger` or a helper in `tree_ert`.**
The dependency direction in this repo runs `tree_ert` → `phase3a_*`, never back. A run recorder
that both the CLI and the forthcoming PyQt UI must use cannot live in `tree_ert` without
inverting that. `run_record.py` is imported by both and imports neither; it is deliberately
free of any `phase3a_unified_reconstruct` import and duck-types the frame it is handed.

**Known imperfection.** Nothing yet *forces* a capture through `RunRecorder`. The existing CLI
and Tkinter paths still write flat files, and will until they are migrated. Until then the
convention is enforced by the operator choosing the new path, which is exactly the weakness this
ADR criticises in the logbook alternative. The mitigation is that the PyQt UI — the entry point
the tank sessions will actually use — is being built on `RunRecorder` from the start and offers
no flat-file path.

## Consequences

**Easier.** A run is citable on its own: a reviewer asking where a number came from opens one
directory and finds the number, the conditions, the code version, and a photograph of the
apparatus. The titration series becomes analysable, because concentration is a machine-readable
field rather than a memory. Reprocessing old data against new code is possible, because the
commit that produced each run is recorded, with a `-dirty` marker when the tree had uncommitted
edits.

**Harder.** Every capture now asks for metadata, which is friction at exactly the moment the
operator wants to press the button. The friction is the point, but it is real, and a session
running long will feel it. Disk use rises: raw serial text plus per-frame retention is
substantially more than one averaged CSV, though still small in absolute terms.

**Committed to.** `phase3a_logs/runs/` is now a documented layout other tools may read.
Renaming a field in `Conditions` breaks already-written records, so the schema should be treated
as append-only in practice — add fields, do not rename them.

**Will bite later.** The 194 existing flat files are not migrated and cannot be, because their
conditions were never recorded. Any analysis spanning old and new data must handle two layouts,
and the old half will stay condition-less permanently. Second, `conditions.json` records what
the operator *typed*, not what was true; a mistyped concentration is as authoritative-looking as
a correct one. The photograph is the only independent check, which is part of why it is in the
schema.

## Verification

`tests/test_run_record.py` — 23 tests, all passing, no hardware required. The ones that carry
the decisions above:

- `test_conditions_are_written_on_open_not_on_close` — a crashed run stays interpretable
- `test_every_frame_is_kept_unaveraged` — three frames yield six rows, not one averaged row
- `test_frames_are_flushed_per_frame` — frame one is readable before the run closes
- `test_raw_serial_text_is_stored_verbatim` — line endings normalised, content untouched
- `test_incomplete_fields_are_named_in_the_record` — under-documented runs say so themselves
- `test_load_run_round_trips_conditions` — the record reads back as the dataclass it was

Full suite: 240 tests passing.

To falsify: open a run, kill the process before closing it, and confirm `conditions.json` and
the frames written so far are both present and readable. If either is absent, the crash-safety
claim is wrong.
