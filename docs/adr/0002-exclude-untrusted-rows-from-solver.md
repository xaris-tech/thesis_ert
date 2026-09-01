# ADR-0002: Exclude untrusted rows from the solver rather than substituting baseline values

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `phase3a_reconstruct.py` (`reconstruct_difference`),
  `phase3a_unified_reconstruct.py` (CLI capture loop), `tree_ert/controller.py`
  (`capture_target`); how every difference image must be read
- **Related:** `docs/validity-audit.md` D-05

## Context

When `filter_frame_vector_best_effort` judged a measurement pair untrustworthy — unstable
baseline RMS, or an implausibly large delta — it wrote the **baseline** value into that slot of
the target vector. The intent was "exclude this pair." The effect was the assertion *nothing
changed here*, handed to the solver as though it had been measured.

PyEIT's `JAC.solve_gs` computes `a = (v1·v0)/(v0·v0)` then `dv = v1 - a*v0`. For a substituted
row, `v1 == v0`, so `dv = (1 - a) * v0` — not zero unless `a` happens to equal exactly 1. Worse,
substituted rows are themselves included in the dot products that produce `a`, so a run with
many substitutions biases the global scaling factor as well.

Both effects push the image toward no-change in precisely the regions where data was too poor
to trust. For a decay-detection instrument that is the most dangerous possible direction of
bias: hardware failure renders as a clean, confident, healthy-looking image. Up to 25% of pairs
could be substituted before a run was even labelled `debug-low-confidence`
(`MIN_RECON_KEPT_PAIR_RATIO = 0.75`).

## Decision

`reconstruct_difference()` accepts an optional `dropped_indexes`. When supplied, those rows are
excluded from both the frame-scaling factor `a` and the backprojection sum (`dv[dropped] = 0`
before multiplication by `solver.H`). Both capture paths pass `filtered.dropped_indexes`
through. With `dropped_indexes` omitted the function is `solve_gs` verbatim, so existing
callers are unaffected.

## Rationale

The audit's preferred fix was to drop the rows from the inverse problem — that is, rebuild the
Jacobian without them. `pyeit.eit.jac.JAC` computes `J` and the regularised inverse `H` inside
`setup()`, which is per-protocol, not per-frame. Rebuilding per frame would mean re-running
`setup()` on every capture (expensive, and the mesh/protocol are fixed anyway) or reaching into
PyEIT internals to slice `J` and recompute `H` — a maintenance liability against an upstream
library this project does not control.

Zeroing `dv` for dropped rows achieves the operative goal: the row contributes exactly nothing
to the backprojected image, and nothing to `a`. It differs from a true Jacobian rebuild in that
the regularisation in `H` was computed against the full row set, so the effective
regularisation is marginally different from a properly re-solved reduced problem. For a
difference-imaging prototype whose dominant error sources are electrode contact and drift, that
discrepancy is far below the noise floor.

Alternatives rejected:

- **Keep substituting, just annotate the image.** This was the previous partial fix. Annotation
  stops a human misreading the image but does not stop the solver being fed fiction.
- **Fail the whole frame when any pair is bad.** Discards good data and, given typical
  electrode contact quality on a living trunk, would reject most captures.

## Consequences

Images from runs with many dropped pairs will now look *noisier*, not cleaner — the false
smoothness is gone. This is correct but will read as a regression to anyone who judged quality
by how tidy the image looked.

The residual difference from a true Jacobian rebuild is real, if small, and should be stated if
a thesis panel asks how excluded measurements are handled. It is not a full reduced-problem
solve.

`dropped_indexes` is optional and defaults to `None`, so any future caller that forgets to pass
it silently reverts to the old biased behaviour. The two existing call sites are wired; new
ones must be too.

## Verification

`tests/test_phase3a_reconstruct.py::TestReconstructDifference` — one test asserts the no-argument
path is byte-identical to `solve_gs`, the other constructs a substituted row and asserts the
result matches a hand-computed exclusion *and* differs from the naive `solve_gs` result,
proving the row was excluded rather than merely small.
