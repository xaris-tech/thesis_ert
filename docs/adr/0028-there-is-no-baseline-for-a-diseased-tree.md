# ADR-0028: A diseased tree has no baseline; the thesis claim requires absolute imaging

- **Status:** Accepted
- **Date:** 2026-09-16
- **Affects:** what the instrument can claim about a real coconut, the thesis's central capability
  statement, the priority order of the remaining work
- **Related:** states the constraint behind
  [ADR-0019](0019-image-the-void-by-inserting-a-target.md),
  [ADR-0018](0018-bisect-reciprocity-with-a-resistor-phantom.md) and
  [ADR-0021](0021-saline-tank-as-the-deferred-phantom.md); reads on the evidence from
  [ADR-0027](0027-control-image-makes-a-null-visible.md)
- **Evidence:** `scans/runs/20260916-*`, `scans/index.csv`

## Context

The instrument produces difference images. A difference image shows what *changed* between two
captures of the same specimen, and it survives the open reciprocity violation only because a
systematic error stable between those two captures subtracts out (ADR-0017).

Applied to the thesis's actual goal — detecting decay in a living coconut — that model has no
baseline to offer. **A diseased tree gives one state.** The decay is present in every capture, so
it subtracts out and is structurally invisible. This is not a limitation of the capture schedule;
no schedule recovers it. It is the same result ADR-0019 recorded for the drilled void, and it
generalises to every permanent feature.

The question "how do we get the baseline for a real coconut" was raised twice in one session,
which is the right instinct: it is the question the thesis turns on, and nothing in the repository
stated the answer.

The published method does not have this problem because it does not use difference imaging. PiCUS
TreeTronic and Al Hagrey's trunk tomography produce **absolute resistivity** maps and read decay
against species-typical values. They image a tree once because they need no before-state. The
standard method requires exactly the capability this rig does not have.

Two measurements from 2026-09-16 bear on how far away that capability is. Both are captures of an
unchanged specimen, scored against their own control image (ADR-0027):

```text
run                                   significance   verdict
20260916-181821-coconut-1-2nd-run         1.74x      indistinguishable from noise
20260916-194731-coconut-3rd-config         0.6x      indistinguishable from noise
```

In both, the control panel — the baseline differenced against itself — was visually
indistinguishable from the reconstruction. The structure in the image is the instrument's own
signature, reproduced whether or not anything changed. Across the same session the delivered
current fell from 362 uA within 3 percent to 152 uA spread across 96-281 uA, and reciprocity sat
at 69-77 percent against the 57.5 percent historical figure.

## Decision

This ADR records the constraint rather than resolving it. Three statements are now project truth:

1. **The thesis's headline capability requires absolute reconstruction**, which is blocked on the
   reciprocity violation. Reciprocity is therefore on the critical path to the thesis, not merely
   to instrument quality.
2. **No single-visit difference image of a diseased tree can show the disease.** Any such image
   must be reported as showing change between two captures, never as showing decay.
3. **The baseline question is downstream of instrument characterisation.** On present evidence the
   instrument's noise signature on the trunk is as large as any image it produces, so no baseline
   strategy can be evaluated until that is fixed.

The options are recorded, with what each needs:

| Approach | Baseline | Blocked by |
|---|---|---|
| **Absolute imaging** | none — resistivity against species norms | reciprocity |
| **Longitudinal** | the same tree months or years earlier | time; images progression, not presence |
| **Spatial self-reference** | a sound plane at another height on the same trunk | nothing structural; inherits contact noise |
| **Normative population** | many known-healthy coconuts averaged | needs absolute or normalised measurement |
| **Stimulus response** | the same tree before and after an induced change | nothing structural; needs a repeatable stimulus |

Work order: **contacts, then reciprocity, then baseline strategy.**

## Rationale

**Why record this rather than pick a strategy now.** Every option except spatial self-reference and
stimulus response is blocked on something else, and both of the unblocked ones inherit the
instrument's current noise. Choosing between them today would be choosing a method for an
instrument whose limits are not yet characterised — and the two null results above show those
limits are currently the binding constraint, not the method.

**Why spatial self-reference is the strongest single-visit candidate.** Two electrode rings at
different heights on one trunk, one through suspected decay and one through sound wood, differenced
against each other. The instrument's systematic errors are common to both planes and largely
subtract, which is the same argument that licenses difference imaging at all. It assumes the
reference plane is sound, and it returns a null if the decay column runs the full height — but the
drilled void at a known height makes it directly testable on the existing specimen.

**Why this is not a reason to abandon difference imaging.** It remains the only class of result the
instrument can produce honestly today, and it is the right tool for the tank, for a rod-in-void
demonstration, and for stimulus-response work. The point is what it cannot be asked to do.

**Known imperfection.** The claim that the instrument is currently noise-limited on the trunk rests
on two captures taken while the electrode contacts were visibly degrading through the session. A
rig with contacts reseated may well clear its own noise comfortably. The statement should be
re-tested, not assumed permanent.

## Consequences

**Easier.** The thesis can state its limitation deliberately rather than meeting it at the defence.
The saline tank's priority is now explicit: it is not validation work, it is what unblocks the
headline claim. Any reconstruction of a real tree now has a required caption — change between two
captures, not decay.

**Harder.** The project's central capability is gated on an unresolved fault that has already
survived eight eliminated hypotheses. There is no route to a single-visit decay image that does not
pass through either absolute reconstruction or an assumption that some part of the tree is healthy.

**Committed to.** No image of a living tree may be presented as showing disease without either
absolute reconstruction or a stated, defended reference state. Reciprocity work takes priority over
new imaging features.

**Will bite later.** Spatial self-reference needs a second electrode ring or a physical move between
captures, and the current UI models only time-against-time within one session — building it is real
work, not a setting. And if reciprocity turns out to be caused by the metal-wood interface rather
than the instrument, absolute imaging on a tree may be unreachable with nail electrodes at all,
which would make this ADR's option table the permanent shape of the problem rather than a
transitional one.

## Verification

Not a code change; nothing to test. It is checkable against the record:

- The structural null is reproduced in ADR-0019 and again in the two 2026-09-16 runs above, whose
  significance scores and control images are in `scans/runs/` and `scans/index.csv`.
- The reciprocity block is ADR-0017 and ADR-0018.
- The published-method contrast is in ADR-0020's sources.

Falsified if an absolute reconstruction is ever produced and validated on this rig, or if a
single-visit difference image of a tree is shown to reveal a permanent feature — either would mean
the reasoning here is wrong and this ADR should be superseded.
