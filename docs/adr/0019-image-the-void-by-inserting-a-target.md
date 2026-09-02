# ADR-0019: Image the drilled void by inserting a target into it; the resistor phantom is unavailable

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** what the next capture session does, what a resulting reconstruction image is
  allowed to claim, the near-term status of ADR-0018's phantom step
- **Related:** defers the next step of
  [ADR-0018](0018-bisect-reciprocity-with-a-resistor-phantom.md);
  [ADR-0017](0017-reciprocity-survives-the-current-source-repair.md),
  [ADR-0012](0012-current-floor-from-measured-noise.md),
  [ADR-0004](0004-opt-in-pinned-colorbar.md),
  [ADR-0003](0003-reciprocity-as-report-not-gate.md)
- **Evidence:** `phase3a_logs/post-repair-baseline-20260902.npz`,
  `phase3a_logs/exports/20260902-target-run-null.png`,
  `docs/i-sat-investigation-2026-09-02.md` section 10.7

## Context

The specimen is a cut-down coconut trunk with a hole drilled through it between electrodes E4
and E5. This was not understood when the 2026-09-02 target run was planned, and that run was a
clean null:

```text
control run   mean pair RMS drift 0.172 %      max single-pair change 0.00138 kohm
target run    mean pair RMS drift 0.212 %      max single-pair change 0.00108 kohm
pairs exceeding 3x the control band            0 of 108
```

The null was structurally guaranteed rather than informative. **The void is present in the
baseline, in the control and in the target alike, and difference imaging subtracts out anything
that does not change between the two states.** No capture schedule can recover a static feature.
That is what motivated ADR-0018's push toward absolute reconstruction, which in turn is blocked
on the 57.5 percent reciprocity violation.

Two constraints have since been placed on the specimen by the operator, and they close the paths
ADR-0018 and its successors assumed were open:

- **The resistor phantom will not be built.** ADR-0018's decision — bisect the reciprocity fault
  by measuring into a linear passive network with the electrodes disconnected — has no route to
  execution right now.
- **The specimen may not be wetted.** This rules out the saline tank ADR-0018 named as the right
  eventual phantom, and it rules out filling the void with saline, which was the one state change
  that difference imaging could have imaged directly.

What remains available is the void itself as a receptacle: something can be put into it and taken
back out, which is a genuine state change between two captures.

## Decision

The next capture inserts a **dry conductive target — a metal rod — into the existing void**, kept
physically clear of the E4 and E5 nails, and images it against the existing dry-void baseline. If
no suitable metal is available, the fallback is a **wooden plug soaked in salt water**, soaking the
plug and not the trunk. The two are not combined.

Reciprocity remains open, absolute reconstruction remains unlicensed, and ADR-0018's phantom is
deferred pending materials rather than cancelled.

## Rationale

A difference image is licensed today even though reciprocity is violated, because a systematic
error that is stable between baseline and target subtracts out. That is the same argument
ADR-0017 makes, and it is the reason difference imaging survives a fault that kills absolute
imaging. It is also why this step is worth taking while the reciprocity question stays open: it
is the only class of result this instrument can currently produce honestly.

Metal is preferred over every wet option on three independent grounds, not merely because of the
constraint. It is a near-perfect conductor, so it is the largest perturbation available and gives
the best chance of clearing the control-drift floor. It is fully reversible, so the run can be
repeated as many times as needed. And a metal-rod target is standard practice in EIT phantom
work, so the result is comparable with published method.

Alternatives considered:

- **Pour saline into the void.** Rejected. It violates the wetting constraint, it is the least
  reversible option, and it does not buy contrast over metal.
- **Saline-soaked plug plus a metal rod together.** Rejected. Two changes at once with no way to
  attribute the result, and the metal dominates the field so the saline contributes nothing
  separable.
- **Return the drilled-out wood core to the hole.** Retained as the most conservative option, and
  it is a real state change, but wood-against-air is a far weaker contrast than metal-against-air
  and is the most likely to land inside the control band and produce a second uninformative null.
- **Do nothing until reciprocity is resolved.** Rejected. The phantom is blocked, the tree-side
  hypothesis space is exhausted (ADR-0018), and refusing a licensed difference image because an
  unrelated unlicensed technique is blocked would leave the project with no result at all.

**The knowingly imperfect part.** ADR-0017 measured the reciprocity residual as spatially
non-uniform — per-electrode median error runs 13-25 percent at E7-E9 against 58-70 percent at
E3-E6 and E10-E12. The void sits between E4 and E5, which is inside the *worse* region. The
assumption that the error is stable between baseline and target is therefore being leaned on
hardest exactly where the target is. This does not invalidate the run, but it means a weak or
marginal result must not be argued up into a detection.

## Consequences

**A positive result is evidence that the pipeline detects a conductivity perturbation at a known
location. It is not evidence that the void is imaged.** The reconstruction locates the rod, not
the hole; the hole is what makes room for the rod. Any thesis text drawn from this run has to say
so, or it claims a capability the instrument does not have.

Physical constraints carried into the bench session:

- The insert must not touch the E4 or E5 nails. Contact shorts a drive pair rather than perturbing
  the field, and produces a `V_RANGE` or an out-of-family reading instead of an image.
- The insert is seated before capture begins and left undisturbed. The five warmup frames exist
  because re-energising after handling restarts the electrode double layer.
- `phase3a_logs/post-repair-baseline-20260902.npz` stays valid only while the rig stays on the
  specimen and no electrode is re-seated. Any electrode disturbance — including any later attempt
  at the phantom, which requires the rig to come off the tree (ADR-0015) — invalidates it and
  costs a fresh baseline.

The saline-soaked-plug fallback is only partly reversible: moisture transfers to the hole wall and
wicks into the surrounding wood, so it changes the specimen for every subsequent run. It is a
one-way door and is chosen only if no metal is at hand.

Reciprocity and absolute reconstruction stay blocked, and with them any image of the void itself.
ADR-0018's phantom remains the correct next instrument-side measurement whenever materials allow.

## Verification

The detection floor this run must clear is the measured control drift of
`docs/i-sat-investigation-2026-09-02.md` section 10.7 — control median 0.28 percent, max
0.43 percent relative pair RMS, over a run where nothing was changed. The criterion is unchanged
from the null run above: pairs changing by more than 3x the control band, and a reconstruction
peak that localises to the E4-E5 arc rather than wandering.

Two outcomes falsify the reasoning here rather than the instrument. A null against a metal rod —
the strongest perturbation obtainable — would mean the specimen is not coupling to the electrode
array at all, which is a contact problem and not a reconstruction problem. A strong response that
localises somewhere other than the E4-E5 arc would mean the spatial residual of ADR-0017 dominates
the signal, and would retire difference imaging on this rig until reciprocity is resolved.

Read the image under ADR-0004: the colorbar auto-scales, so a null and a detection look alike
until the scale is checked.
