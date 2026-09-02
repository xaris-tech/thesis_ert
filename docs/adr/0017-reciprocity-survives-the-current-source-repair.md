# ADR-0017: Reciprocity violation survives the current-source repair, so output impedance is not its cause

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** ADR-0014's open question about ADR-0010, the interpretation of every reciprocity
  figure this project reports, and any thesis claim resting on measurement symmetry
- **Related:** answers the open question in
  [ADR-0014](0014-current-sense-feedback-tapped-before-rs.md) Consequences;
  [ADR-0010](0010-reciprocity-error-scales-with-signal.md),
  [ADR-0008](0008-reciprocity-metric-must-not-saturate.md),
  [ADR-0003](0003-reciprocity-as-report-not-gate.md),
  [ADR-0015](0015-measure-output-impedance-with-the-instrument.md),
  `docs/validity-audit.md` L-02, L-03
- **Evidence:** `phase3a_logs/reciprocity-post-repair-20260902.csv`

## Context

ADR-0014 repaired the current-sense feedback and recorded an explicit open question: ADR-0010
had found reciprocity error rising with signal amplitude, and a voltage source with roughly
430 ohm output impedance delivers a current that depends on each drive pair's impedance, which
is a plausible mechanism for exactly that. ADR-0014 concluded that ADR-0010's *observation*
stands but its *interpretation* may not, pending re-measurement on the repaired instrument.

That re-measurement has now been taken, 2026-09-02, on the repaired rig on the tree, adjacent
pattern, DAC code 200, range `eh`, 8 samples, 6 averaged frames.

**The instrument is confirmed healthy for this measurement.** One full frame returned 216 of 216
records `Q,OK`, with drive current across all twelve pairs spanning 508.2 to 528.3 uA - a
3.9 percent spread where a voltage source would track each pair's impedance. The
transconductance reproduces across a power cycle and a reflash:

```text
I = 1.522 uA/code x code + 212.7 uA        (design 1.580, slope error -3.7 percent)
measured 216.1 / 360.5 / 516.6 / 822.7 uA at codes 0 / 100 / 200 / 400
ADR-0014 measured 216.4 / 361.3 / 517.7 / 826.6 uA at the same codes
```

**Reciprocity did not improve.**

| | pre-repair (ADR-0010) | post-repair |
|---|---:|---:|
| median error | — | 57.5 % |
| quartile medians by amplitude | 4.9 / 37.5 / 63.0 / 88.1 | 4.5 / 69.6 / 42.8 / 79.6 |
| correlation with log amplitude | +0.791 | +0.565 |
| sign-flipped pairs | — | 30 of 54 |

## Decision

Output impedance is recorded as **not** the cause of this project's reciprocity violation. The
amplitude dependence ADR-0010 described is real and persists on an instrument that now regulates
current, so ADR-0010's observation is reaffirmed and the mechanism ADR-0014 proposed for it is
withdrawn. The cause remains unidentified.

## Rationale

Two alternative explanations were tested against the data and both were eliminated, which is
what makes this a decision rather than a note.

**A wrong reciprocal-pairing convention in software.** `reciprocity_scores()` pairs
`(i_pair, v_pair)` with `(v_pair, i_pair)`, a straight swap preserving orientation within each
pair. If that convention were wrong, some other orientation should pair better. All four
orientation variants were scored against the same captured data:

```text
(v, i)          n=54  median 57.79%      the current convention
(v_rev, i)      no matched pairs
(v, i_rev)      no matched pairs
both reversed   no matched pairs
```

The protocol emits each electrode combination in exactly one orientation, so no alternative
pairing exists to be chosen. The convention is forced by the data, not selected, and cannot be
the source of the error. This closes the question ADR-0010 left open as needing dummy loads to
separate "the analog path violates reciprocity" from "reciprocals were matched wrongly in
software" - the software half is now answered without dummy loads.

**The known-bad E5/E6 contacts** (`docs/i-sat-investigation-2026-09-02.md` 10.4, issue B, a
5.8x forward/reverse injection asymmetry). Grouping by whether those electrodes appear:

```text
E5/E6 anywhere   n=26  median 61.9%  flips 13/26
E5/E6 absent     n=28  median 45.2%  flips 17/28
```

Pairs with neither electrode still violate reciprocity badly. The contact fault makes things
worse but is not the cause, and this hypothesis - raised on the strength of E5/E6 appearing in
most of the worst individual pairs - is recorded as disproved.

What the data does show is spatial structure. Per-electrode median error over the 18 pairs
touching each electrode:

```text
E1 35.6   E2 42.1   E3 63.3   E4 63.8   E5 69.8   E6 57.8
E7 25.1   E8 19.3   E9 13.1   E10 63.7  E11 64.8  E12 60.4
```

E7-E9 are three to five times better than E3-E6 and E10-E12. Whatever the mechanism is, it is
not uniform around the trunk.

The largest individual violations share a shape worth recording: one orientation reads 10 to
40 times the other, e.g. `I:E8-E9 V:E5-E6` at 0.0083 kohm against its reciprocal at 0.3082 kohm.
A geometric argument says these should match - the separation between drive and sense pair is
the same either way round.

One hypothesis is now favoured but **untested**: the 213 uA offset at zero command
(reaffirmed here at 212.7 uA) is a current that flows without being commanded, and if any part
of it returns through a path other than the specimen - the CD4067 protection diodes are the
known candidate, section 2.5 - then the shunt measures a current the tissue never saw. Transfer
resistance normalises by the shunt reading, so the error would vary with which electrodes are
selected, producing pair-dependent, amplitude-correlated reciprocity failure. This is
speculation until measured.

## Consequences

**Reciprocity cannot yet be used as a quality gate or as evidence of instrument validity**, and
ADR-0003's report-not-gate decision is reaffirmed with a second independent reason. A thesis
claim that the instrument satisfies reciprocity would be false on present evidence.

Difference imaging is not automatically invalidated - a systematic error that is stable between
baseline and target subtracts out - but that stability is assumed, not demonstrated, and the
spatial structure above means the residual is not uniform across the mesh.

The dummy-load sweep of ADR-0015 gains a third purpose. It was already the output-impedance
measurement and the discriminating test for the offset; it is now also the cleanest way to test
the leakage hypothesis, since a fixed resistor with the electrodes disconnected removes both the
tissue and the electrode interface from the circuit. If reciprocity is still violated into
resistors, the fault is in the instrument; if it is clean, the fault is at the electrodes or in
the specimen path.

ADR-0010's title - "reciprocity error scales with signal amplitude" - remains accurate. Its
deferral pending dummy loads also remains in force.

## Verification

`phase3a_logs/reciprocity-post-repair-20260902.csv` holds all 54 scored pairs with both
magnitudes, the error and the sign-flip flag, sorted worst first. The capture conditions are in
Context above; re-running them should reproduce the distribution, and the transconductance fit
is the check that the instrument was healthy when it was taken.

This ADR records a negative result and an eliminated hypothesis, so what would falsify it is a
mechanism that explains the error and, once corrected, brings reciprocity into agreement. The
dummy-load sweep is the next measurement that could do that.
