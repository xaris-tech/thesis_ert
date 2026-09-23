# ADR-0034: Living-tree images illustrate; the cut-trunk pilot proves

- **Status:** Accepted
- **Date:** 2026-09-23
- **Affects:** what every reconstruction of a living coconut may be captioned, which stage of the
  validation ladder carries the imaging claim, the priority of the cut-trunk pilot, and the
  premise of ADR-0028
- **Related:** supersedes the premise and option table of
  [ADR-0028](0028-there-is-no-baseline-for-a-diseased-tree.md) while keeping its structural
  finding; unblocked by [ADR-0031](0031-reciprocity-fault-was-a-v-minus-mux-wiring-error.md);
  reads on [ADR-0019](0019-image-the-void-by-inserting-a-target.md),
  [ADR-0027](0027-control-image-makes-a-null-visible.md)
- **Evidence:** `scans/runs/20260923-124808-coconut-tree-1`,
  `scans/runs/20260923-125411-coconut-tree-1`; `CONTEXT.md`;
  `docs/chapter-3-methodology-draft.md` section 3.9

## Context

ADR-0028 recorded that a diseased tree presents one state, so the decay is in every capture and
subtracts out. That finding stands and was reproduced again on 2026-09-23: two captures of the
same standing coconut, six minutes apart with nothing touched, reconstructed at **1.44x** the
control image and were correctly reported as indistinguishable from noise.

Two things have changed since ADR-0028 was written on 2026-09-16.

**The reciprocity block is gone.** ADR-0031 found the V- mux wiring error. On 2026-09-23 the
resistor belt read 0.1 percent median reciprocity, 0.3 percent max, with instrument-contributed
offset of 0.012 mV against a 8.49 mV signal. ADR-0028 named reciprocity as what blocked absolute
imaging, and it no longer blocks anything.

**ADR-0028's premise about the published method is wrong.** It states that PiCUS TreeTronic and
comparable instruments "produce absolute resistivity maps and read decay against species-typical
values," and concludes the standard method "requires exactly the capability this rig does not
have." The literature says otherwise. PiCUS interpretation guidance states that the main aspect is
the *distribution* of high and low conductive areas and that "the actual value of the resistance
given in a tomogram is less important and less accurate, due to the ambiguity of the measuring
method." A 2019 review in Frontiers in Plant Science reaches the same place: decay detection rests
on "unexpected high and low ER patches," patterns "remained overall unaffected by temperature"
while absolute values are not, and "the effective resistivity of wood depends on water content and
temperature, making it difficult to use the resistivity of an individual tree for decay
detection."

The industry-standard instrument therefore disclaims its own absolute numbers. Absolute
reconstruction was never the bar.

A third fact came from reading `CONTEXT.md` rather than the literature. The project's own glossary
already defines the output as a **conductivity variation pattern** that "indicates relative
electrical variation inside the scanned trunk band, not a named disease," and its **safe success
claim** promises "category-associated conductivity variation patterns," not images of decay. It
also already forbids drilling a living tree: an **observational living-tree scan** uses
"only minimally invasive nail electrodes and no drilling or hollowing." The methodology's
**cut-trunk pilot** (section 3.9) is where artificial defects are permitted, and its pass criterion
6 is "repeatable conductivity variation appears near the known defect sector."

So the project already had a stage licensed to produce a decay-revealing image, and it has never
been run. `scans/index.csv` holds 95 rows: saline tank and standing coconut only, zero cut trunk.
The ladder is being climbed out of order.

## Decision

A reconstruction of a **standing living coconut** is an **illustrative reconstruction**: it is
presented with its conditions as a conductivity variation pattern and is never cited as showing
decay. The **cut-trunk pilot** produces the project's **evidential reconstructions**, because a
top-drilled defect gives a genuine before-after on coconut material. The imaging claim of the
thesis rests there, and the cut-trunk pilot becomes the next milestone, ahead of further
living-tree scanning.

## Rationale

**Why not absolute imaging, now that reciprocity is fixed.** It is no longer blocked, but it is no
longer necessary either. The published method does not use it and explicitly distrusts it. Pursuing
it would be substantial work in service of a bar the field does not set, and it carries a live risk
ADR-0028 already named: if the residual reciprocity error originates at the metal-wood interface
rather than in the electronics, absolute imaging on a trunk may be unreachable with nail electrodes
at all.

**Why not a cross-tree or healthy-population difference.** Considered and rejected. A difference
image cancels what is common to two captures; between two different trees almost nothing is common
— diameter, nail positions, contact impedance at twelve nails, moisture, taper. The decay term
would be small inside a large one. This is not a new conclusion: `CONTEXT.md` already lists
"healthy-tree baseline" and "cross-tree baseline" under `_Avoid_` for **tree-specific baseline**.

**Why not a second electrode ring at another height.** Genuinely viable, and the basal biology of
Ganoderma stem rot suits it — a queen palm with *G. zonatum* has been reported showing uniformly low
resistance from soil line to about 35 cm and higher readings at 120-140 cm. It is rejected for now
on scope, not on merit: it needs 24 nails on a living tree, which strains the "minimally invasive"
commitment and the PCA permission built on it, plus UI work, since the current model is
time-against-time within one session. It remains the strongest single-visit candidate if the
cut-trunk route fails.

**Why this is not a retreat.** The cut-trunk pilot on real coconut material, with a defect at a
known sector and a genuine before-state, is stronger evidence for the instrument than any
uncaptioned living-tree tomogram would be. What is given up is the sentence "this image shows the
rot," which ADR-0028 already committed the project not to say.

**Known imperfection.** The cut-trunk discs available are dry, and a living trunk is not. The pilot
therefore validates the method and the geometry, not the living-tissue regime. This is accepted
rather than fixed; see ADR-0035.

## Consequences

**Easier.** Every living-tree reconstruction now has a settled caption and needs no defence it
cannot give. The 1.44x null of 2026-09-23 stops being a failure and becomes what it is — a correct
report about a specimen that did not change. The cut-trunk pilot's priority is explicit.

**Harder.** The imaging claim now depends entirely on a stage that has never been run, on
specimens whose moisture state is not the field state. If the pilot fails criterion 6, there is no
fallback imaging evidence on coconut material and the two-ring route has to be reopened under time
pressure.

**Committed to.** No reconstruction of a standing living coconut is presented as showing decay. The
terms **evidential reconstruction** and **illustrative reconstruction** are recorded in
`CONTEXT.md` and every figure is one or the other. The cut-trunk pilot runs before further
living-tree capture.

**Will bite later.** A panel may still ask the obvious question — why not simply image the diseased
tree — and the answer is a structural one that takes a paragraph, not a sentence. The methodology
draft also says "cut coconut trunk **section**", implying height, while the available specimens are
thin **discs**; a disc approximates the solver's two-dimensional domain and a standing trunk does
not, so chapter 3 needs correcting or the pilot will appear to claim more transfer to the field
than it has.

## Verification

Not a code change. Checkable against the record:

- The structural null is reproduced in ADR-0019, in the two 2026-09-16 runs cited by ADR-0028, and
  again in `20260923-125411-coconut-tree-1` at 1.44x with its control image alongside.
- The reciprocity unblock is ADR-0031 and the 2026-09-23 belt runs at 0.1 percent median.
- `CONTEXT.md` carries **evidential reconstruction** and **illustrative reconstruction**.
- In force when no figure of a living coconut in the thesis is captioned as showing decay, and
  when `scans/index.csv` shows cut-trunk runs preceding further standing-tree runs.

Falsified if the cut-trunk pilot passes criterion 6 and a subsequent single-visit living-tree
difference image is nonetheless shown to reveal a permanent feature, which would mean the
structural argument inherited from ADR-0028 is wrong and both ADRs should be superseded.
