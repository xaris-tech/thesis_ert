# ADR-0020: Electrodes are short bare tips in both tank and tree

- **Status:** Accepted
- **Date:** 2026-09-11
- **Affects:** physical electrode installation on the saline tank and the trunk specimen, how
  much of any reconstruction error is attributable to the instrument, the methods section
- **Related:** prerequisite for [ADR-0021](0021-saline-tank-as-the-deferred-phantom.md);
  `docs/validity-audit.md` L-01 (point-electrode assumption)
- **Evidence:** literature survey, 2026-09-11 (see Sources)

## Context

PyEIT's `mesh.create(n_el=12)` models **point electrodes on the boundary** of a flat
two-dimensional circle. The forward model has no representation of an electrode with physical
extent, and none of a conductor reaching into the interior of the domain.

The tank as first built has twelve stainless nails driven through the wall, each protruding
roughly two to three centimetres into the interior — a radius that is a substantial fraction of
the tank's own. Metal is a near-perfect conductor relative to saline, so such a nail is not a
boundary point: it drags the boundary potential deep into the medium and short-circuits the
region around it. The measured voltage profile near a drive pair flattens against what the model
predicts.

The same question applies to the trunk, and applies there first, because the tank is only useful
as a phantom if it stands in for the tree. A bare nail driven deep into a trunk contacts wood
along its entire shaft, spanning bark, cambium, sapwood and — if driven far enough — heartwood,
which have materially different conductivities. Such an electrode measures a weighted mixture of
all of them with no way to separate the layers, which is a problem for a technique whose target
is a heartwood feature.

Left unresolved, this is a model-versus-reality error present in every reconstruction, of unknown
size, indistinguishable from instrument error — and the instrument is precisely what the tank
session exists to test.

## Decision

Electrodes are **short and bare** in both media: approximately 3–5 mm of metal in contact with
the medium, and no insulation on the shaft.

In the tank, nails are backed out or sleeved so only the tip is wetted. On the trunk, nails are
driven only until firm contact with the outer sapwood is established, matching the published
convention, and not deeper.

The insertion depth and protrusion are recorded per run in `Conditions.electrode_protrusion_mm`
(ADR-0023), so a run taken under a different convention is identifiable as such.

## Rationale

**Why short.** A short electrode approximates the point the forward model assumes. It is the
cheapest available reduction in model-versus-reality error, and it removes a confound from the
one experiment that is supposed to isolate the instrument.

**Why bare, and not an insulated shaft with an exposed tip.** This was the initially preferred
option and it was rejected on evidence. Insulating the shaft is standard practice in borehole
and soil geophysics, but a survey of the tree-ERT literature found no instance of it: the
established method drives bare stainless nails or screws through the bark and stops at the outer
sapwood. Insertion depths quoted range from roughly 0.2 cm for nail probes to about 2 cm for
needle-type electrodes in xylem. The field's answer to the rod-electrode problem is a *short*
electrode, not an insulated one.

Adopting insulation would therefore put this work off-method for no citation benefit, and would
make its results harder to compare against published tree ERT — the comparison the thesis
depends on. Short bare electrodes achieve nearly the same electrical result and stay on-method.

**Why not keep long electrodes and fix the model instead.** Rejected as out of scope, not as
wrong. The physically correct treatment is the Complete Electrode Model, which represents finite
electrode size and contact impedance explicitly, and is standard in EIT phantom work where flush
plate electrodes are used. Implementing it against PyEIT is a significant piece of work, and the
result would be heavier to solve — a real concern given the Raspberry Pi deployment target. It
remains the right answer if electrode geometry later proves to be a dominant error term.

**Why not keep long electrodes in the tank to match a long-electrode tree.** This was considered
once it became clear that a bare tree nail contacts wood along its whole shaft. Rejected because
it makes the *tank* faithful to a *tree installation that is itself off-method*. The correct move
is to bring both media to the published convention, not to propagate a deviation for the sake of
internal consistency.

**Known imperfection.** 3–5 mm is a judgement call, chosen as the smallest protrusion that
reliably keeps metal wetted while remaining small against the tank radius. It is not derived from
a sensitivity calculation, and no measurement in this project yet establishes how much residual
error it leaves.

## Consequences

**Easier.** The tank becomes a valid stand-in for the tree, because both use the same electrode
convention. Residual reconstruction error is more confidently attributable to the instrument,
which is what the session is for. The work stays comparable with published tree ERT.

**Harder.** Contact resistance rises as wetted area falls, so measured currents drop and the
signal moves closer to the noise floor — the regime that already produced the voltage-quantisation
failure recorded in `docs/validity-audit.md`. The titration target in ADR-0022 has to account for
this, and the current range may need revisiting.

**Committed to.** Any future electrode change is a methodology change requiring a superseding ADR
and, strictly, a re-baseline: data taken at one protrusion is not directly comparable with data
taken at another.

**Will bite later.** Nails backed out of existing holes may leak or shift between sessions, and a
shifted electrode silently changes the geometry the reconstruction assumes. The per-run photograph
required by ADR-0023 is the only check on this. Separately, a short trunk electrode contacting
only outer sapwood may couple poorly to heartwood, which is the target — that tension is inherent
to the published method and is not resolved here.

## Verification

Not verifiable in software; this is a physical convention. Checks available:

- `Conditions.electrode_protrusion_mm` is recorded per run and appears in `conditions.md`, so a
  run taken at a different protrusion is identifiable after the fact.
- The per-run top-down photograph shows the actual installation.
- Falsifiable on the bench: capture the identical adjacent protocol at long and short protrusion
  in the same tank at the same concentration. If the voltage profiles near the drive pair do not
  differ, the flattening argument above is wrong and the convention is unnecessary.

That comparison has **not** been run. The decision rests on the forward-model argument and the
literature convention, not on a measurement taken with this instrument.

## Sources

- Noninvasive Analysis of Tree Stems by Electrical Resistivity Tomography: Unraveling the Effects
  of Temperature, Water Status, and Electrode Installation — Frontiers in Plant Science, 2019.
  <https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2019.01455/full>
  (also <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6865845/>)
