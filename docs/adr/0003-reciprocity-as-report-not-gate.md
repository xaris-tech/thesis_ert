# ADR-0003: Reciprocity error is reported, not enforced as a capture gate

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `phase3a_unified_reconstruct.py` (`reciprocity_errors`,
  `filter_by_reciprocity`, `write_reciprocity_report`, `--reciprocity-threshold-pct`);
  data-quality evidence in the thesis
- **Related:** [ADR-0002](0002-exclude-untrusted-rows-from-solver.md),
  `docs/validity-audit.md` L-02, L-03

## Context

Until now the only data-quality evidence was visual: look at a reconstruction, decide whether
it seems plausible. That is unfalsifiable and a thesis panel will say so.

Reciprocity is the standard check. The medium is reciprocal, so driving current through A,B
while sensing at C,D must give the same transfer resistance as driving C,D while sensing A,B.
Any disagreement is instrumental — bad electrode contact, a failing mux channel, wiring, or
amplifier asymmetry — because the tree does not care which direction it is measured in. It
turns "the image looks wrong" into a per-channel number.

The full-mesh capture already collects both orientations, so no firmware change or extra
capture time is needed to compute it.

## Decision

Reciprocity error is computed on the averaged baseline capture, printed as a summary (count of
scored pairs, count above threshold, worst offender with its electrode labels), and written to
`<run>-reciprocity.csv`. `--reciprocity-threshold-pct` (default 10%) controls what counts as
failing **for reporting purposes only**. A failing reciprocity check does not abort the run,
and reciprocity-based exclusion is not wired into the reconstruction path.

`filter_by_reciprocity()` exists and is tested, but no production caller uses it yet.

## Rationale

The threshold's correct value for this hardware is unknown. Published ERT work uses figures
from under 1% for laboratory instruments up to several percent for field systems; this
prototype has a 3.3 V mux rail (L-01), a current source whose output impedance is comparable to
its load (L-02), and voltage and current that are not sampled simultaneously (L-03). Any of
those could produce a reciprocity error that is a genuine property of the instrument rather
than a fault in a particular channel.

Gating captures on a threshold chosen before any reciprocity data exists would reject good runs
on a guess. Measure first, set the threshold from the distribution, then decide whether to
enforce. 10% is a deliberately loose starting point for *reporting* — it is not a claim about
what this hardware should achieve.

Alternatives rejected:

- **Auto-drop failing channels immediately.** Combined with ADR-0002's row exclusion this could
  silently discard a large fraction of the mesh on the first run, before anyone has seen what
  normal looks like.
- **Compute per-frame rather than on the averaged baseline.** Noisier, and the baseline is the
  capture whose stability is already gated, so it is the right place to characterise the
  instrument rather than the target.

## Consequences

The CSV is currently something a human must read and act on; nothing in the pipeline responds
to it. Until a threshold is chosen from real data, a badly reciprocal channel still reaches the
solver.

Once enough runs exist, the distribution of these errors should set the real threshold, and
this ADR should be superseded by one that decides whether and how to enforce it.

Only pairs whose reciprocal was actually captured are scored; patterns and meshes that do not
produce reciprocal coverage will report zero scored pairs, which is correctly distinguished in
output from "all pairs passed".

## Verification

`tests/test_phase3a_unified_reconstruct.py::TestReciprocityCheck` covers the percent-error
computation (each reciprocal pair scored exactly once, unpaired measurements skipped), the
drop-both-orientations behaviour of the filter, and cross-frame averaging. On hardware, the
check is falsifiable directly: swapping the leads on a channel that reports a low reciprocity
error should leave the transfer resistance essentially unchanged.
