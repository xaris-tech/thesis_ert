# ADR-0035: The intact-disc survey measures between-specimen spread before any cross-specimen claim

- **Status:** Accepted
- **Date:** 2026-09-23
- **Affects:** the cut-trunk pilot protocol, what may be claimed by comparing two specimens,
  the settings profile for a cohort, and the offline analysis the survey requires
- **Related:** the imaging half of the same pilot is
  [ADR-0034](0034-living-tree-images-illustrate-the-cut-trunk-pilot-proves.md); geometry recording
  is [ADR-0033](0033-record-specimen-geometry-with-every-run.md); significance convention from
  [ADR-0027](0027-control-image-makes-a-null-visible.md); recording rules from
  [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md)

## Context

ADR-0034 routes the imaging claim through the cut-trunk pilot. A second question rides on the same
specimens and is cheaper to answer than anyone expected: **how far do specimens of the same
material differ when none of them carries a defect?**

That number decides whether any comparison between different trees is possible at all. ADR-0028
listed "normative population" among the options and marked it blocked. It is not blocked by
instrumentation — it is blocked by an unmeasured quantity, and roughly ten cut coconut discs are
available on the bench to measure it with. The equivalent experiment cannot be run on standing
trees within the thesis scope, which is a three-tree comparison.

The physics permits cross-specimen comparison in principle. For a roughly circular specimen with
twelve electrodes, transfer resistance is `R = (rho / d) * g`, where `g` depends only on the
angular arrangement. Dividing a scan's transfer resistances by their own mean cancels `rho` and
`d` exactly, leaving geometry. Whether ten real discs actually agree in that normalised space is
an empirical question, and nothing in the repository answers it.

Three constraints shape how it can be measured. The nails stay permanently in each disc, so
placement variation cannot be controlled by re-placing and rescanning. The solver assumes a
circular boundary with equal spacing that real discs do not have, though the normalised comparison
is solver-free and does not inherit this. And `reconstruction.MEASUREMENT_SETTINGS` gates
differencing on instrument settings only, so a solver-free comparison across runs has no gate at
all — vectors captured at different DAC or current-range settings would compare silently and
wrongly.

## Decision

Before any disc is drilled, all available discs are scanned **intact** under one locked settings
profile, and the resulting spread is measured in normalised-measurement-vector space. The
comparison quantity is the **normalised measurement vector**, with **within-specimen contrast
metrics** computed alongside. Cross-specimen comparison is licensed only if

```
S_defect / S_between  >=  3
```

where `S_noise` is the same disc rescanned untouched, `S_between` is the intact discs against each
other, and `S_defect` is one disc before and after drilling. The three spreads are always reported
individually, never collapsed into a verdict, together with each disc's distance from the cohort
centre and each measurement pair's contribution to the spread.

## Rationale

**Why the normalised vector and not the image.** Comparing images across specimens is the
cross-specimen difference `CONTEXT.md` already lists under `_Avoid_`. The normalised vector cancels
resistivity and diameter analytically, uses all 108 measurements, and needs no solver — so it does
not inherit the circular-mesh assumption.

**Why contrast metrics alongside.** The maximum-to-minimum ratio and the max-minus-min difference
compare a specimen only with itself, so specimen size and moisture never enter. They are also what
the published palm work used: diseased palms showed ratios 7 to 25 times higher than healthy ones,
and a max-minus-min of 100+ ohms against 50-70 for healthy. They give a number comparable to the
literature and a fallback that survives if `S_between` turns out large.

**Why 3 and not the existing 2.0.** ADR-0027 sets significance at 2.0, but that is a same-specimen
comparison where nearly every nuisance term cancels. Cross-specimen comparison has strictly more
nuisance variation — diameter, ovality, nail placement, dryness — so the bar rises. Below 3, a
claimed detection could have been produced by a different disc simply being a different disc. The
number is a judgement call and is recorded here so it cannot be chosen after seeing the data.

**Why the decomposition matters more than the threshold.** On 2026-09-23 a dead electrode was
found only after decomposing reciprocity per electrode and then per cell; the run-level median said
1.1 percent and looked healthy while one channel was open. A single cohort number would repeat that
failure. Per-disc distance from the centre identifies an outlier specimen, and per-pair contribution
maps it back to electrodes, which is where contact faults live.

**Why the outcomes are committed to in advance.** A ratio of 3 or more licenses cross-specimen
comparison; 1.5 to 3 is reported as marginal and carries no classifier claim; below 1.5 the approach
is abandoned for within-specimen contrast metrics alone. The last branch is the reason the survey
exists — to fail cheaply on a bench rather than expensively in the field with three trees.

**Why placement variation is measured rather than controlled.** The nails stay in. `S_between`
therefore contains both real specimen differences and nail-placement differences, inseparably.
ADR-0033 records the geometry instead, so an outlier disc can be checked against its own spacing.
This is weaker than a re-placement control and is accepted as such.

**Why settings are locked across the cohort and a disc is excluded rather than retuned.** Changing
the DAC or current range between discs introduces a variable the normalisation does not cancel, and
no gate would catch it. A nine-disc cohort with one documented exclusion is a result; a ten-disc
cohort with one retuned disc is a contaminated dataset that looks clean. Settings are chosen by a
one-frame probe pass across all discs, then fixed for the survey and for the drill test, whose
before and after must also match.

**Why the tuning criterion is relative noise, not a flat control image.** A visually grey control
image is gameable: reducing the drive current lowers absolute noise while measuring less, and an
instrument reading a constant zero produces a perfectly grey difference. The summary line already
prints noise as a percentage of signal, which cannot be gamed that way, and it is tuned subject to
two floors — current comfortably above `MIN_CURRENT_UA` on the worst pair, and quantisation not
binding per `capture_view.quantisation_report` (ADR-0026).

**Why moisture is out of scope.** The discs are scanned as they are, with no re-wetting and no
moisture measurement. Re-wetting would introduce a soaking gradient — wet rim, dry core — that is
itself a radial artefact indistinguishable from structure. Dry but consistent is more
interpretable than damp and uncontrolled. Per ADR-0023, moisture is named in each run's
`not_recorded` list so the omission reads as a choice rather than an oversight.

## Consequences

**Easier.** The question ADR-0028 left open becomes a bench measurement costing one session instead
of a field programme. Whatever the answer, the living-tree strategy is chosen on evidence. The
discs also measure a floor for the field case, since living trees will differ by at least as much.

**Harder.** The survey has no analysis tool yet. Ten `frames.csv` files do not become `S_between`
by themselves, and nothing currently computes a normalised vector, a cohort centre, per-disc
distance or the contrast metrics. That code has to exist before the survey means anything, and it
does not exist today.

**Committed to.** Intact scans precede drilling, because drilling destroys the before-state and
cannot be undone. Settings are locked across the cohort. The three spreads are reported separately.
The sub-1.5 outcome is accepted if it occurs.

**Will bite later.** `S_between` on dry discs may understate the living case, since moisture varies
more between living trees than between discs from one batch — so a pass here is necessary but not
sufficient for the field. A disc with genuine fungal colonisation is not intact and must not count
toward `S_between`; the second disc photographed on 2026-09-23 shows grey-green patches that may be
storage mould or may be colonisation, and nothing currently distinguishes them. And until a
specimen-identity gate exists, the UI will still difference two different discs on request and
print a significance number for the result.

## Verification

- In force when `scans/index.csv` shows the intact runs of every disc under one settings profile,
  with `specimen_id` and geometry populated per ADR-0033, preceding any run whose
  `target_description` names a drilled defect.
- The locked profile is checkable: `pattern`, `current_range`, `dac`, `settle_ms` and `samples`
  identical across every cohort row.
- The threshold is checkable against the reported `S_noise`, `S_between` and `S_defect` once the
  analysis exists; until it does, this ADR is **decided but unverified**, and verification takes
  the offline analysis plus one bench session.
- Falsified if `S_between` turns out uncorrelated with every recorded geometry value and with
  scan order, which would mean the spread comes from something none of this anticipates.
