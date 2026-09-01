# ADR-0009: Fix E5's contact physically rather than compensating for it in software

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** bench procedure, capture validity for any run before E5 is re-seated;
  `docs/current-setup-validation-runbook.md` rungs 5-9
- **Related:** [ADR-0002](0002-exclude-untrusted-rows-from-solver.md),
  [ADR-0008](0008-reciprocity-metric-must-not-saturate.md), `docs/validity-audit.md` L-01

## Context

The 2026-09-01 bench session walked the validation ladder on the living palm with all twelve
electrodes fitted. Median drive current per pair, from 270 records each:

```
I=E6-E5:    83.6 uA        I=E9-E10:   589.4 uA
I=E5-E6:    84.3 uA        I=E11-E10:  601.1 uA
I=E4-E5:    90.0 uA        I=E6-E7:    790.0 uA
I=E5-E4:    94.5 uA        I=E7-E6:    791.6 uA
```

Every pair involving E5 is down 7-9x. No pair excluding E5 is affected. E6 delivers 790 uA
against E7 and 84 uA against E5, so E6 is sound and only drags when E5 is its partner. The
common factor is E5 alone.

Three independent metrics had already implicated it before current was examined: E5 tied for
most frequent electrode in the worst-20 reciprocity rows; E5 ranked first in per-electrode
drift with E6 second, dragged in through the shared pair; and the `min 40.9 uA` outlier in the
single-frame capture.

Context that matters for reading this: the rest of the rig is healthy. 216/216 records returned
`Q,OK` at a 677 uA median — no `I_LOW`, `I_HIGH`, `I_REVERSED`, or `V_RANGE` — and 20 frames of
undisturbed control drift gave 1.14% median relative RMS at correlation >= 0.9998. The feared
L-01 failure, where palm resistance starves the 3.3 V mux rail below the ~100 uA usable floor,
is not occurring at DAC 100.

## Decision

E5 is treated as a hardware fault to be repaired at the electrode, not accommodated in the
reconstruction pipeline. No target capture (rung 9) is performed until E5 delivers current
comparable to its neighbours.

## Rationale

The measurement is not merely noisy, it is wrong in a way software cannot recover: a 7-9x
current deficit means the injected field for those pairs is not the field the forward model
assumes. Down-weighting or dropping E5's rows would produce a self-consistent image from an
instrument that is not measuring what the mesh says it is.

Capturing a target now is worse than waiting. A difference image is baseline-relative, so a
known-bad electrode gets baked into the baseline, and every subsequent comparison inherits it.
Re-seating E5 afterwards would invalidate the baseline and force a recapture regardless — the
work is not saved, only spent twice.

Alternatives rejected:

- **Drop E5's rows via the ADR-0002 mechanism and proceed.** That mechanism exists for
  measurements that fail mid-run, not for a fault known before capture starts and cheap to fix.
  Using it here would spend a 12-electrode array's worth of coverage to avoid a five-minute
  repair.
- **Compensate by raising DAC for E5-involved pairs.** Changes the injected current between
  rows of one frame, breaking the current normalisation the whole v2 protocol is built on.
- **Accept it and note the limitation in the thesis.** The defect is repairable; documenting it
  instead of fixing it would weaken a capability claim for no reason.

## Consequences

Easier: once E5 is repaired, every downstream number — drift floor, reciprocity distribution,
usable pair count — is measured on a uniform array and can be compared against these figures to
confirm the repair worked.

Harder: the ladder stalls at rung 8 until physical access to the tree is available, and the
rung 5-8 numbers recorded here become baseline-invalid the moment E5 is touched. They are kept
as the pre-repair reference, not as usable baseline data.

This commits the project to re-running rungs 5 through 8 after any electrode is re-seated.

## Verification

Re-run the single-frame capture and compare median drive current for the four E5-involved pairs
against the ~600-790 uA of unaffected pairs. Repaired when E5's pairs are within the spread of
the others; falsified if they remain depressed after re-seating.

The diagnostic that separates the two candidate causes — bad electrode-tissue contact versus a
bad mux channel — is to move E5's lead to a spare mux channel and repeat. If the deficit
follows the lead it is contact; if it stays with the channel it is the mux. This has not been
done.

The self test's per-electrode liveness check should independently flag E5. If it does not, its
threshold is too loose for a 7-9x deficit and needs tightening against these numbers.
