# ADR-0075: The impedance ratio is p90/p10 of one scan's transfer resistances, compared only within one pattern

- **Status:** Accepted
- **Date:** 2026-10-26
- **Affects:** `tree_ert/capture_view.py` (`impedance_ratio`), `erterface-interface` (saved measurements, review screen, CSV export); the farm UI's "impedance ratio" number
- **Related:** CONTEXT.md *Within-specimen contrast metric*, ADR-0072 (farm UI saves runs UNCLASSIFIED), ADR-0073 (opposite drive)

## Context

The farm UI has an "impedance ratio" field from its stub days, saved empty for
real runs (ADR-0072) because nothing defined it. CONTEXT.md already names the
right kind of number: a *within-specimen contrast metric*, "a scalar
summarising how far transfer resistances spread inside a single scan, such as
the maximum-to-minimum ratio". Measured repeatability (same specimen, same
settings, back-to-back runs, frame-averaged |transfer resistance| per pair;
coefficient of variation across the repeats):

| repeat set | max/min | p95/p5 | p90/p10 |
|---|---|---|---|
| saline, adjacent (typical) | 1-130 % | 0.2-85 % | 0-28 %, mostly < 2 % |
| discs, adjacent | 11-140 % | 1-46 % | 1-52 %, mostly < 7 % |
| disc-08 re-clipped, opposite | 4 % | 19 % | 2.4 % |
| disc-01 E3 hole, opposite | 150 % | 10 % | 11 % |

The value also depends strongly on the drive pattern: disc-08 reads ~15
adjacent and ~3-4 opposite.

## Decision

The impedance ratio of a run is the 90th percentile over the 10th percentile of
its frame-averaged |transfer resistance| across all pairs (None below 10
pairs). It is stored with the run's drive pattern and is to be compared only
with the same specimen at the same pattern. It is not a health classification;
saved runs stay UNCLASSIFIED.

## Rationale

- *Max/min* (the glossary's example): set by the single smallest pair, which in
  opposite drive sits near an equipotential and is mostly noise, or by a single
  bad contact (2026-10-26, E1/E2). It varied 30-140 % across repeats.
- *p95/p5*: better, still tail-sensitive (up to 85 %).
- *p90/p10*: the most repeatable of the three on every repeat set measured,
  and still a ratio of the scan's own spread, so size/moisture/temperature
  cancel as the glossary intends.
- *Target over baseline mean*: compares two scans; useful, but a different
  number from the within-scan contrast this field was meant to show.

## Consequences

- The ratio carries no threshold and no meaning across patterns or specimens;
  the UI shows the pattern beside it.
- Measurements saved before this have no ratio; they are not back-filled.
- The 10/90 choice is a judgement from the repeat sets above. A larger set, in
  particular living trees, may move it; it lives in one constant
  (`IMPEDANCE_RATIO_PERCENTILES`).

## Verification

`tests/test_capture_view.py` (`ImpedanceRatioTests`); the repeatability table is
reproducible from `scans/index.csv` and the runs' `frames.csv`.
