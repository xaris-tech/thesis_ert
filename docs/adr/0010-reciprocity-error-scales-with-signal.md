# ADR-0010: Treat reciprocity as uncalibrated until dummy loads settle its amplitude dependence

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `phase3a_unified_reconstruct.py` (`reciprocity_scores`), the Reciprocity tab in
  `tree_ert/ui.py`, rung 7 of `docs/current-setup-validation-runbook.md`, and any thesis claim
  that cites reciprocity as evidence of measurement quality
- **Related:** [ADR-0003](0003-reciprocity-as-report-not-gate.md),
  [ADR-0008](0008-reciprocity-metric-must-not-saturate.md),
  [ADR-0009](0009-fix-e5-contact-before-further-capture.md),
  `docs/validity-audit.md` L-02, L-03

## Context

Once ADR-0008 made reciprocity scores rankable, two questions could finally be asked of them.
Both were answered on 2026-09-01, and both answers were unexpected.

**Reciprocity does not track electrode contact quality.** E5 was repaired mid-session: its
drive current went from ~88 uA to ~746 uA, and control drift improved from 1.14% median to
0.26% worst-frame, moving E5 from first to fifth in the per-electrode drift ranking. Across the
same repair, reciprocity did not move at all:

| | Before repair | After repair, settled |
|---|---|---|
| E5 rows, median error | 70.9% | 71.1% |
| non-E5 rows, median error | 35.5% | 35.4% |
| worst-third top electrode | E5 x10 | E5 x10 |

Two runs whose physical contact state differed by 8x in delivered current produced reciprocity
distributions identical to within noise.

**Reciprocity error rises with signal strength.** Correlating per-pair error against per-pair
transfer-resistance magnitude over the settled post-repair run (54 pairs):

```
correlation error% vs log10(amplitude):  r = +0.791

by amplitude quartile (weakest first):
  Q1  0.0023-0.0064 kOhm   median error   4.9%
  Q2  0.0072-0.0145 kOhm   median error  37.5%
  Q3  0.0171-0.0325 kOhm   median error  63.0%
  Q4  0.0330-0.3832 kOhm   median error  88.1%
```

The weakest pairs are nearly perfectly reciprocal; the strongest are the worst. This is the
reverse of what offset domination predicts, and it falsifies the reading recorded earlier in
this session that low-amplitude distant pairs were the unreliable ones. They are the reliable
ones. The pairs carrying the most information are the ones that disagree.

Reciprocity is a theorem for a passive medium. A pair such as `I=E6-E7 V=E4-E5` measuring
0.276 kOhm against a reciprocal near 0.02 kOhm is an order-of-magnitude violation, which cannot
happen physically. Either the instrument violates reciprocity — `L-02`, current-source output
impedance comparable to the load, and `L-03`, V and I not sampled simultaneously, both bite
hardest where load impedance differs most between the two reciprocal configurations — or there
is a pairing, sign, or normalisation defect in how a reciprocal is matched, in the same family
as the D-02 convention issue.

Tree data cannot separate those, because the true transfer impedances are unknown there.

Two secondary observations. Sign flips are amplitude-independent (7/13, 6/13, 7/13, 10/15
across quartiles), so they are a distinct phenomenon from magnitude error. And E5 retains an
effect beyond amplitude: controlling for signal strength, within the weak-signal half E5 pairs
run 59.2% against 6.5% for non-E5 pairs, after the contact repair.

## Decision

Reciprocity is not used as evidence of hardware health, electrode quality, or measurement
validity until rung 4 dummy loads establish what this instrument achieves against known
resistances. The Reciprocity tab and CSV stay, labelled as uncalibrated diagnostic output.

## Rationale

The metric has now been shown not to measure the thing rung 7 uses it for. The runbook
instructs the operator to read the worst rows as naming bad hardware; on this rig that
instruction pointed at E5 both before and after E5 was repaired. Acting on it would mean
re-seating a healthy electrode.

Dummy loads are the only way to break the tie between the two candidate causes, because they
are the only condition where the correct answer is known in advance. Rung 4 was skipped this
session because the rig was already in the tree; it is now the highest-value measurement
available.

Alternatives rejected:

- **Remove reciprocity from the UI and CLI.** The metric is not wrong, it is uninterpreted —
  and the amplitude correlation it revealed is itself a significant finding about the
  instrument. Deleting the instrument that found it would be perverse.
- **Assume L-02 and start redesigning the current source.** Plausible, unproven, and expensive.
  A pairing or normalisation defect would produce the same signature for no hardware cost.
- **Keep citing reciprocity as a quality check with a caveat.** A caveat does not stop a number
  in a thesis from being read as evidence. Withdrawing it until calibrated is honest; footnoting
  it is not.

## Consequences

Easier: nobody spends a session chasing an electrode that reciprocity fingered and drift
exonerated. The amplitude relationship is now a named phenomenon that can be designed against.

Harder: rung 7 has no verdict until rung 4 is run, so the validation ladder has a gap where the
runbook currently implies a pass/fail. The 10% threshold from ADR-0003 remains uncalibrated and
now has a second reason to stay that way.

This commits the project to running rung 4 on dummy loads before any reconstruction from this
instrument is presented as quantitative, because if the strong-coupling pairs really do violate
reciprocity by 10x, difference imaging inherits that error wherever it matters most.

## Verification

The amplitude correlation is reproducible from
`phase3a_logs/phase3a-v2-adjacent-20260901-180216.csv` by scoring each pair with
`reciprocity_scores` and correlating `error_percent` against `max(|a|, |b|)`. Falsified if a
repeat run on the same rig returns `r` near zero, or if the quartile medians stop increasing
with amplitude.

The contact-independence claim is verified by comparing the pre-repair
(`...-175559-reciprocity.csv`) and post-repair settled (`...-180216-reciprocity.csv`) reports:
the E5 and non-E5 medians must remain within ~1 percentage point across an 8x change in
delivered current. Falsified if a future contact repair does move them.

The cause is **not** verified and this ADR does not claim one. Rung 4 on 1k / 4.7k / 10k
resistors, scoring reciprocity against known transfer impedances, is what would settle it: an
instrument that is reciprocal on dummy loads points at the tree or the protocol, while one that
is not points at L-02/L-03 in the analog path.
