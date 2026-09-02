# ADR-0018: Stop black-box hypothesis testing on the tree; bisect reciprocity with a resistor phantom

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** how the reciprocity investigation proceeds, the prerequisite for any absolute
  reconstruction, `docs/current-setup-validation-runbook.md`
- **Related:** extends [ADR-0017](0017-reciprocity-survives-the-current-source-repair.md);
  [ADR-0015](0015-measure-output-impedance-with-the-instrument.md),
  [ADR-0010](0010-reciprocity-error-scales-with-signal.md),
  [ADR-0003](0003-reciprocity-as-report-not-gate.md), `docs/validity-audit.md` L-02, L-03
- **Evidence:** `phase3a_logs/reciprocity-condition-sweep-20260902.csv`,
  `phase3a_logs/reciprocity-post-repair-20260902.csv`

## Context

ADR-0017 established that reciprocity is violated at 57.5 percent median error on a healthy,
repaired instrument, and eliminated two causes. The goal of resolving it is now explicit: it is
the prerequisite for absolute reconstruction, which is the only way to image a permanent feature
such as the drilled void in the trunk specimen, since difference imaging cannot see a target
that is present in both states.

A further six hypotheses were tested on the tree, 2026-09-02, by varying one instrument
parameter at a time and re-scoring reciprocity over 3 averaged frames per condition:

```text
condition       median err%   flips    median I
dac100                 58.0   30/54      361.6 uA
dac200                 57.7   30/54      515.7 uA
dac400                 58.3   30/54      823.1 uA
settle50               57.8   30/54      515.0 uA
settle200              59.5   30/54      514.7 uA
discharge50            57.7   30/54      516.2 uA
adjacent autorange on  58.3   30/54      (DAC 400)
adjacent autorange off 55.2   30/54      (DAC 400)
```

**The error is invariant, and the same 30 of 54 pairs flip sign in every condition.** This rules
out, in turn:

- **Leakage tied to the 213 uA zero-command offset**, the hypothesis ADR-0017 favoured. That
  offset is 59 percent of the drive current at code 100 and 26 percent at code 400. If it were
  the mechanism, the error would fall substantially with code. It does not move.
- **Settling**, including the L-03 concern that voltage and current are not sampled
  simultaneously. A 20x increase in settle time changes nothing.
- **Electrode polarisation recovery.** A 50 ms discharge between measurements changes nothing.
- **ADC input loading.** Forcing the PGA to the widest range raises the ADS1115 differential
  input impedance roughly fourfold and moves the error by 3 points, from 58.3 to 55.2 percent -
  real, in the predicted direction, and far too small to be the cause.

A relative electrode-mapping error was also tested offline, on the reasoning that if the sense
muxes are not wired to the same channel order as the drive muxes, then "reciprocal" pairs are
not reciprocal at all. All 24 rigid mappings of the sense indices against the drive indices
(12 rotations x 2 directions) were scored. The best, a 6-position rotation, gives 33.3 percent
against identity's 57.8 percent - an improvement, but nowhere near the collapse to a few percent
that a genuine wiring mismatch would produce, and it is the best of 24 hypotheses, which is a
weak standard of evidence. **No mapping restores reciprocity.**

## Decision

Black-box parameter variation on the tree stops here. The next reciprocity measurement is taken
against a **resistor phantom**: a fixed network of resistors standing in for the specimen, with
the electrodes disconnected from it entirely.

## Rationale

Every hypothesis tested so far has been eliminated without identifying the cause, and the
remaining candidates are not separable by varying instrument parameters on a tree. They divide
cleanly into two groups, and a phantom bisects them in one measurement:

- **Instrument-side:** common-mode rejection against the large common-mode swing the drive
  produces across the mux `Ron`, crosstalk in the shared ground return, or an unmodelled
  interaction in the analog path. Notably a CMRR-limited error would be **invariant with drive
  current**, since both the signal and the common-mode scale together and the fractional error
  stays fixed - which is exactly the invariance observed, so this family is not eliminated by
  anything above.
- **Specimen-side:** nonlinear or rectifying metal-to-wood contacts, and any property of the
  trunk that breaks the assumptions of the reciprocity theorem.

A resistor network is linear, passive, has no electrode interface, and satisfies reciprocity by
construction. If reciprocity is clean into a phantom, the fault is at the electrodes or in the
specimen and the instrument is sound. If it is still violated, the fault is in the instrument
and the specimen is exonerated. No amount of further work on the tree can make that distinction.

This also supersedes the guess-and-check approach as a matter of method. Six hypotheses were
tested and six were eliminated, which is progress, but the cost per hypothesis is a bench
session and the supply of plausible mechanisms is not close to exhausted.

Alternatives considered:

- **Keep testing hypotheses on the tree.** Rejected: the two remaining families produce
  identical signatures under every parameter the firmware can vary.
- **Go to absolute reconstruction anyway.** Rejected, and this is the decision that matters for
  the thesis. Absolute reconstruction rests on the forward model matching the instrument.
  Reciprocity failing at 57 percent means it does not, so an absolute image would be
  reconstructing a systematic error as if it were anatomy. Difference imaging survives this
  because a stable error subtracts out; absolute imaging has no such protection.
- **Build a saline tank first.** Rejected as the *next* step, though it remains the right
  eventual phantom. A tank reintroduces an electrode-electrolyte interface, so it cannot
  separate the two families as cleanly as resistors, and it is a larger build.

## Consequences

The reciprocity question stays open, and with it absolute reconstruction. **The drilled void in
the trunk specimen cannot be imaged by this project's current pipeline**, since difference
imaging cannot see a static feature and absolute imaging is not licensed. Imaging that void
requires either a state change induced in it - filling it, which difference imaging handles
today - or a resolved reciprocity problem.

The phantom is a build, not an afternoon: twelve nodes wired to the electrode leads through
known resistors. It does not need to model a trunk, only to be linear and connected, so a mesh
or star of equal resistors is sufficient to test reciprocity.

If the phantom exonerates the instrument, the electrode interface becomes the prime suspect and
the fix is contact quality, which this project already has experience with (ADR-0009). If it
implicates the instrument, the analog front end needs measurement against common-mode rather
than differential test signals, which is a class of bench work not yet done here.

ADR-0003's report-not-gate decision holds throughout, for a third reason: the threshold cannot
be calibrated while the mechanism is unknown.

## Verification

The condition sweep is recorded in `phase3a_logs/reciprocity-condition-sweep-20260902.csv`, one
row per condition with pair count, median error, sign-flip count and median current. Re-running
any condition should reproduce its row; the invariance is the finding, so a condition that moves
the error substantially would falsify the elimination it belongs to.

The phantom measurement itself is the verification of this decision: reciprocity scored into a
resistor network, by the same `reciprocity_scores()` path used on the tree, with the electrodes
disconnected. A clean result is single-digit median error. Anything resembling the 57 percent
seen on the tree localises the fault to the instrument.
