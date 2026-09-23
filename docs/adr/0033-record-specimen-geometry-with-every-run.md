# ADR-0033: Record specimen geometry with every run

- **Status:** Accepted
- **Date:** 2026-09-23
- **Affects:** `run_record.Conditions`, `INDEX_COLUMNS`, `RunRecorder.index_row`,
  `tree_ert/qt/main_window.ConditionsPanel`, the cut-trunk pilot protocol, and any claim that
  compares one specimen with another
- **Related:** extends [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md);
  needed by the intact-disc survey that [ADR-0028](0028-there-is-no-baseline-for-a-diseased-tree.md)
  leaves open; the circular-mesh assumption it records is not itself decided here

## Context

The conditions sheet (ADR-0023) was written while the saline tank was the only specimen. Every
physical field it names is tank-shaped: saline concentration, fill depth, water temperature,
electrode protrusion. The specimen's own shape is absent, and `diameter_cm` lives in *settings*
rather than conditions, where it has been `None` on all 95 runs recorded to date.

Reconstruction assumes a shape it never checks. `phase3a_reconstruct.create_solver` calls
`mesh.create(n_el=12, h0=0.12)`, which places twelve electrodes **equally spaced on a perfect
circle**. There is no way to pass measured positions. Real specimens depart from both
assumptions: the cut coconut discs photographed on 2026-09-23 are visibly oval, and twelve nails
driven by hand are not at exact 30 degree steps.

The cut-trunk pilot makes this a measurement problem rather than a tidiness problem. The pilot
compares roughly ten discs scanned intact, to find out how far specimens of the same material
differ when none carries a defect. That spread is the number deciding whether any cross-specimen
comparison is viable. It necessarily contains real specimen differences *and* differences in
where the nails ended up, and the two cannot be separated after the fact. Since the nails stay
in the discs permanently, the usual control — remove the nails, replace them, rescan — is not
available.

What remains available is to measure the geometry that exists and record it, so an outlier
specimen can be checked against its own spacing instead of discarded on a hunch.

A second, smaller defect showed up the same day. The two tree runs `20260923-124808` and
`20260923-125411` both record `medium: "saline tank"` under the label `coconut tree #1`, and four
resistor-belt runs carry the label `reistor-belt-sanity-test` with no field naming the specimen.
Nothing in the record identifies *which physical thing* was scanned, and
`reconstruction.MEASUREMENT_SETTINGS` gates differencing on instrument settings only — pattern,
current range, DAC, settle, samples, electrode offset and reversal. Two runs of two different
discs pass that gate and produce a confident image with a significance number.

## Decision

`Conditions` gains five named fields — `specimen_id`, `circumference_mm`, `thickness_mm`,
`major_diameter_mm`, `minor_diameter_mm` — which reach `index.csv` as appended columns. The
twelve per-nail arc positions go in `extra` as `nail_arc_mm`. All are optional and default to
"not measured", and `validate()` continues to return warnings without raising.

## Rationale

**Why named fields rather than `extra` alone.** `extra` would have cost nothing today. But these
are the values the survey sorts, filters and correlates by: the intended check is whether the
specimens furthest from the cohort centre are also the ones with the worst spacing or the most
ovality, and that is a query across runs. Values buried in a per-run JSON blob do not reach
`index.csv`, so the query cannot be written. `INDEX_COLUMNS` is append-only by construction —
unknown keys ignored, missing ones written empty — so appending columns leaves every row already
written readable.

**Why the nail arcs stay in `extra`.** Twelve columns that nothing sorts by would bloat every row
of the index for all specimens, including the tank, which has no nails. A list is also the shape
the offline geometry check wants. This is the boundary the `Conditions` docstring already draws:
prefer a field for a recurring value, `extra` for the rest.

**Why `specimen_id` is separate from `label`.** The label is free text chosen at capture time and
has already proved unreliable: four runs on a resistor belt and two on a coconut tree carry labels
that contradict their own `medium` field. An explicit identity is also the field a future
same-specimen gate would test, which is the cheapest fix for the cross-specimen differencing
footgun described above.

**Why ovality is two fields rather than a computed ratio.** A ratio discards the size, and the
size is needed to check that normalising by the mean actually removed the diameter dependence it
is supposed to remove. Both measurements are recorded; any ratio is derived later.

**Known imperfection.** Recording the geometry does not let the solver use it. The circular,
equally spaced mesh stays exactly as it was, so placement error and ovality remain unmodelled and
still land in the image as artefact. This ADR makes the departure measurable and stated; it does
not make it corrected. Whether to support measured electrode positions is a separate decision
that should be taken on evidence from the survey, not before it.

## Consequences

**Easier.** The intact-disc survey can be interpreted rather than merely computed: an outlier
specimen can be attributed to its geometry or exonerated. The solver's circular assumption becomes
a stated limitation with numbers attached instead of an unexamined default. The thesis can state
how far its specimens depart from the model it inverts them with.

**Harder.** Six more things to measure per specimen, roughly three minutes with a tape, and a
bench session that is already long. Skipping them silently returns the project to exactly the
state this ADR exists to leave, because the fields will read "not measured" and nothing will stop
the run.

**Committed to.** Any run whose purpose is comparison with another specimen records
`specimen_id`. Cut-trunk pilot runs additionally record circumference, thickness, both diameters
and the nail arcs. The tank is unaffected and its runs stay valid with these fields empty.

**Will bite later.** Recording geometry the solver cannot consume invites the reasonable question
of why the image is not corrected for it, and the honest answer for now is that it is not. If the
survey shows placement dominates the spread, supporting measured electrode positions stops being
optional and becomes real work in the mesh layer, which PyEIT does not make easy. Additionally,
`specimen_id` is recorded but not yet enforced: until `MEASUREMENT_SETTINGS` or an equivalent gate
checks it, the UI will still difference two different specimens on request.

## Verification

- `tests/test_run_record.SpecimenGeometryTests` covers the defaults, the negative-value and
  swapped-diameter warnings, that `validate()` still never raises, that the values reach
  `index_row()`, that the index columns are appended rather than reordered, and that `nail_arc_mm`
  survives into both `conditions.json` and `conditions.md`.
- `tests/test_tree_ert_qt.ConditionsPanelGeometryTests` covers the panel's not-measured sentinels,
  the round trip, arc parsing, and that unparseable arc text is kept verbatim rather than dropped.
- In force when a cut-trunk run's `conditions.md` shows a specimen id and non-empty geometry rows,
  and `index.csv` carries the five new columns.
- Falsified if the survey's between-specimen spread turns out to be uncorrelated with every
  recorded geometry value, which would mean these are the wrong six numbers and the real
  confound is elsewhere.
