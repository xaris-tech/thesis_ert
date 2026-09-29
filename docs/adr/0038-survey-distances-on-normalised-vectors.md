# ADR-0038: Survey spreads are RMS distances between mean-magnitude-normalised vectors

- **Status:** Accepted
- **Date:** 2026-09-29
- **Affects:** `tree_ert/survey.py`, `disc_survey.py`, what `S_noise` / `S_between` / `S_defect`
  mean in the thesis, the contrast metrics reported alongside them
- **Related:** decides the arithmetic [ADR-0035](0035-intact-disc-survey-measures-between-specimen-spread.md)
  left open; specimen grouping from [ADR-0037](0037-refuse-a-scan-without-a-named-specimen.md);
  NaN handling from [ADR-0002](0002-exclude-untrusted-rows-from-solver.md); sign convention
  validity-audit D-02

## Context

ADR-0035 decided that the survey compares normalised measurement vectors, reports `S_noise`,
`S_between` and `S_defect` separately, and licenses cross-specimen comparison at
`S_defect / S_between >= 3`. It named the analysis as the open gap and did not fix: how a vector
is normalised, what "distance" and "spread" mean numerically, how several scans of one specimen
combine, how bad cells are handled, and what the max/min contrast metric is computed on.

Those are judgement calls that change the numbers the threshold is applied to, so they are
recorded before the cohort is scanned. The first data exist: one disc on 2026-09-29, scanned
intact three times and drilled near E7-E9.

## Decision

- **Vector.** Per run, each cell's transfer resistance is the forward/reverse-paired value from
  `unified.frame_to_vector` (lenient), averaged over frames. A cell with no valid reading in any
  frame is NaN and is left out of every comparison that involves that run.
- **Normalisation.** Divide by the mean *magnitude* of the vector's finite cells.
- **Distance.** Root-mean-square difference of two normalised vectors over the cells both have,
  expressed in percent of the mean.
- **Specimen reference.** The mean of that specimen's normalised intact vectors, renormalised.
- **`S_noise`** is the median distance over all pairs of intact scans within a specimen.
  **`S_between`** is the median distance over all pairs of specimen references.
  **`S_defect`** is the median distance of each defect run from its specimen's reference, reported
  with the minutes since that specimen's last intact scan.
- **Contrast** is computed on apparent resistivity: each cell divided by a homogeneous circular
  disc's response on the same cell (PyEIT forward model). Reported as max/min (ADR-0035's metric),
  95th/5th percentile, and (max − min)/median.
- **Settings** must be identical across every included scan on every `MEASUREMENT_SETTINGS`
  field, or the survey refuses to run.
- **Exclusion** is recorded in a manifest with a reason, never inferred.

## Rationale

**Mean magnitude, not signed mean.** The physics argument in ADR-0035 is that `R = (rho/d) * g`,
so any scalar computed from the vector cancels `rho/d`. The signed mean would, but on patterns
whose cells change sign it can sit near zero and blow up the normalisation. The mean magnitude
cancels `rho/d` equally well and cannot vanish.

**RMS, in percent of the mean.** It weights every cell equally, is in the same units as the
noise figures the UI already prints, and is what the per-cell contribution decomposition sums
back to. A correlation coefficient was rejected: it is insensitive to exactly the localised
change a hole makes when the other 100 cells are unchanged.

**Medians of pairwise distances, not distance-from-centre, for the three spreads.** All three
are then the same kind of quantity — the distance between two things — so the ratio of any two
is meaningful. Distance from the cohort centre is still reported per specimen, because that is
what identifies an outlier disc, but it is about 1/sqrt(2) of a pairwise distance and would
bias `S_between` low against `S_defect` if used as the spread.

**Cells dropped, not filled (ADR-0002).** Filling a dead cell with a baseline or cohort value
makes it agree by construction and shrinks every spread it touches. Dropping it costs that cell
only.

**Apparent resistivity for contrast.** On a perfectly uniform disc the adjacent pattern's
transfer resistances span 0.22 to 1 of each other by geometry alone, so a raw max/min ratio
measures the pattern, not the specimen. Dividing by the homogeneous response makes a uniform disc
read exactly 1. On 2026-09-29 no cell's measured sign disagreed with the model's, so the division
is well-defined. Cells whose model response falls below 2 % of the largest are excluded as a
guard; on the adjacent pattern that removes none.

**Why the percentile ratio beside max/min.** The first real data show max/min is set by single
cells: three intact scans of the same untouched disc gave 24.7, 18.0 and 21.0, while the 95/5
ratio gave 5.85, 5.66 and 5.72. ADR-0035 named max/min for comparability with the palm
literature, so it stays, but it cannot on this evidence distinguish anything; the percentile
ratio is what should be compared across discs.

**Why a manifest.** Every run before ADR-0037 has no usable specimen ID, and exclusion — wet
surface, lost contact — is an operator decision with a reason that has to be on record. Runs
taken under ADR-0037 can be grouped from their own conditions instead.

## Consequences

**Easier.** `disc_survey.py --manifest m.csv` or `--from-conditions --medium "cut disc"` turns a
set of runs into all three spreads, per-disc outlier distances, per-cell and per-electrode
contributions, and contrast per scan.

**First result (one disc, `exports/survey-20260929-disc/`).** `S_noise` 1.13 % (pairs 0.63-1.31 %),
`S_defect` 2.99 % (2.33 % at 20 min after the last intact scan, 3.65 % at 78 min), so
`S_defect / S_noise` = 2.65. The holes are detectable on the same specimen, modestly. `S_between`
does not exist yet — it needs a second disc — so ADR-0035's verdict cannot be given.

**Will bite later.**
- The 78-minute defect run reads larger than the 20-minute one, and in that run cells on the
  far side of the disc (E1, E2, E12) changed as much as those beside the holes. The disc was
  changing on its own over that time. `S_defect` therefore contains drift in proportion to the
  gap, which is why the gap is printed; drill tests should scan immediately after drilling.
- `S_noise` here spans scans up to 33 minutes apart, so it includes that drift too. It is a
  floor for "rescanned in one session", not for "rescanned instantly".
- Normalisation cancels a uniform change in resistivity only. A disc drying from the rim inward
  is not uniform and will register as a genuine difference.
- Per-electrode shares split each cell equally among its four electrodes. That is a bookkeeping
  choice, not a sensitivity model.

## Verification

- `tests/test_survey.py`: runs written in `RunRecorder`'s on-disk shape round-trip to their
  transfer resistances with the polarisation offset cancelled; scaling a vector leaves distance
  zero; a uniform disc has contrast 1; a dead cell is NaN and excluded; mixed settings raise
  `SettingsMismatch`; a synthetic cohort orders `S_noise < S_between < S_defect`; per-electrode
  shares sum to 100 %; ADR-0035's bands; manifest parsing and conditions-derived manifests; the
  CLI writes both files.
- Reproducible on real data:
  `.venv\Scripts\python.exe disc_survey.py --manifest exports/survey-20260929-disc/manifest.csv`.
- Falsified if two scans of an untouched disc taken minutes apart differ by more than the
  drilled disc differs from its own intact reference.
