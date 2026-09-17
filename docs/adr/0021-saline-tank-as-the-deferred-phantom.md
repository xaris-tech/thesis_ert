# ADR-0021: The saline tank is the deferred phantom; the reciprocity bisect resumes

- **Status:** Accepted
- **Date:** 2026-09-11
- **Affects:** the reciprocity investigation, the prerequisite for absolute reconstruction, what
  the next capture sessions do, `docs/current-setup-validation-runbook.md`
- **Related:** resumes [ADR-0018](0018-bisect-reciprocity-with-a-resistor-phantom.md), whose
  phantom step [ADR-0019](0019-image-the-void-by-inserting-a-target.md) deferred;
  [ADR-0017](0017-reciprocity-survives-the-current-source-repair.md),
  [ADR-0003](0003-reciprocity-as-report-not-gate.md);
  depends on [ADR-0020](0020-electrode-insertion-depth-convention.md) and
  [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md)
- **Evidence:** `phase3a_logs/reciprocity-condition-sweep-20260902.csv`, the tank built
  2026-09-11 (twelve stainless nails, circular bucket)

## Context

ADR-0017 established a 57.5 percent median reciprocity error on a repaired instrument. ADR-0018
then eliminated six further hypotheses by varying one instrument parameter at a time on the tree,
and found the error **invariant** — 55.2 to 59.5 percent across a 4x change in drive current, a
20x change in settle time, a 50 ms discharge, and a fourfold change in ADC input impedance — with
the same 30 of 54 pairs flipping sign in every condition.

Having exhausted what parameter variation on a tree can resolve, ADR-0018 decided the next
measurement would be taken against a **phantom**: a linear, passive medium with no wood-metal
interface, which satisfies reciprocity by construction. The remaining hypotheses divide cleanly:

- **Instrument-side** — CMRR against the common-mode swing the drive produces across mux `Ron`,
  crosstalk in the shared ground return, or an unmodelled interaction in the analog path.
- **Specimen-side** — nonlinear or rectifying metal-to-wood contacts, or a property of the trunk
  that breaks the reciprocity theorem's assumptions.

A phantom separates those two families in one measurement. ADR-0018 named a saline tank as the
right eventual phantom.

ADR-0019 then deferred it, on two operator constraints: the resistor phantom would not be built,
and the specimen could not be wetted.

**Both constraints were about the trunk, and neither applies to a separate tank.** A saline tank
built as its own apparatus wets nothing belonging to the specimen and requires no resistor
network. The tank now exists: a circular bucket with twelve stainless nails through the wall.

## Decision

The saline tank is adopted as ADR-0018's phantom, and the reciprocity bisect resumes against it.

The tank's first purpose is diagnostic, not pictorial. Reconstruction images from it are a later
step, taken only after the instrument checks below have been read.

Four analyses are run against a homogeneous tank, all from the same captured frames:

- **Reciprocity** — must collapse toward a few percent. Physics guarantees it in a linear passive
  medium. This is the bisect.
- **Symmetry under rotation** — a homogeneous tank with symmetric electrodes must look the same
  from every drive position, differing only by rotation. Deviation is a per-electrode fault map.
- **Monotonic decay** — measured voltage must fall with distance from the drive pair. Violation
  indicates crosstalk or an electrode-ordering error.
- **Noise and drift** — frame-to-frame spread over a held condition, establishing the detection
  floor.

Capture is **adjacent pattern only** (the dipole-dipole configuration in geophysical naming),
matching the pattern the thesis uses.

## Rationale

**Why the tank answers what the tree could not.** A tree never provides a known correct answer,
which is why six hypotheses died inconclusively: each measurement could only be compared against
another measurement. Homogeneous saline is linear, passive, isotropic and free of any
electrochemical junction, so it has predicted behaviour that can be checked absolutely. Symmetry
and monotonic decay are checks of that kind and are not available in any heterogeneous medium.

**Why reciprocity is the headline.** It is a single scalar that splits the entire problem in two.
Clean into saline, the fault lies at the electrode-specimen interface and the instrument is
sound. Still ~57 percent into saline, the fault is inside the instrument and the whole
specimen-side family is eliminated. Either result is decisive, and the investigation has not had
a decisive result since ADR-0017.

**Why reciprocity alone is not enough.** It is a self-consistency check: an instrument with a
symmetric fault could satisfy it while still being wrong. Symmetry and decay are absolute checks
against known physics, and they are what would localise a fault to a specific electrode or mux
channel once reciprocity has said which half of the problem to look in.

**Why adjacent only.** The operator's choice, and it matches the pattern the thesis reports.
Capturing all four patterns was considered — in a tank it costs only scan time and would yield a
pattern-comparison result — and rejected to keep the titration loop short. The consequence is
that the choice of adjacent remains an assertion rather than a measured result, which is a
foreseeable question from a thesis panel.

**Why the symmetry and decay checks are analysed by hand for now.** They do not exist in
`tree_ert/selftest.py` because they are meaningless in a heterogeneous medium and there was never
a reason to write them. Writing them now would mean choosing thresholds before seeing what a
healthy tank looks like on this instrument. The first session's data sets those thresholds; the
checks are codified afterwards.

## Consequences

**Easier.** The reciprocity investigation has a next step again, after being blocked since
2026-09-02. Every future instrument change gains a known-truth medium to be validated against —
this is reusable apparatus, not a one-off. Absolute reconstruction gains a path: it is blocked on
reciprocity, and reciprocity is now testable.

**Harder.** The tank is a second apparatus to maintain, and it evaporates, warms and drifts during
a session. Its geometry matches PyEIT's circular mesh far better than a trunk does, so a
reconstruction that looks good in the tank says less about tree performance than it appears to.

**Committed to.** Tank and tree must keep the same electrode convention (ADR-0020) or the tank
stops being a valid stand-in. Tank results now gate what the tree work may claim: if reciprocity
is clean in saline, tree data taken under the violation must be read as interface-limited.

**Will bite later.** A *clean* tank result is the awkward one. It would localise the fault to the
wood-metal interface without saying what to do about it, and every tree measurement taken so far
would be under suspicion. It is also the outcome that makes absolute reconstruction on a tree
hardest, because the fault would sit in the part of the system least amenable to instrument
engineering. Secondly, homogeneous saline is an easy medium: passing every check in it does not
demonstrate the instrument works on a trunk, only that it is not broken in ways saline can reveal.

## Verification

- Reciprocity is already implemented and exported: `reciprocity_scores()` in
  `phase3a_unified_reconstruct.py`, written to CSV (see
  `phase3a_logs/20260906-232050-reciprocity.csv` for the existing tree run at 98–99 percent error
  on the worst pairs).
- The comparison that settles this ADR: median reciprocity error, tree versus tank, captured at
  the same pattern and comparable current. The tree figure is 57.5 percent (ADR-0017).
- Symmetry and decay have **no** automated check yet. Stated plainly rather than engineered
  around, per the same reasoning as ADR-0005.
- Falsifiable: if tank reciprocity lands between roughly 20 and 50 percent — neither clean nor
  matching the tree — the bisect has failed to separate the two families and the phantom argument
  in ADR-0018 needs revisiting rather than extending.
