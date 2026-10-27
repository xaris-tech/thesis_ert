# ADR-0078: Joint adjacent+opposite absolute solve, before/after comparison of absolute images, and a pattern consensus

- **Status:** Accepted
- **Date:** 2026-10-27
- **Affects:** `tree_ert/absolute.py` (`solve_absolute_joint`, `reconstruct_absolute_joint`, `compare_absolute`, `consensus`; `solve_absolute` now delegates to the joint solve), `exports/disc-08-drill-20261027/compare_absolute.py`
- **Related:** ADR-0041 (absolute gates), ADR-0068 (detection criterion), ADR-0073 (no reciprocity gate for opposite), ADR-0077

## Context

On 2026-10-27 disc-08 was scanned before (B1b/B2b), after an unclip/re-clip sham (S1), and
after drilling a 4 cm through-hole at E5 (60°; D1-D3), each with adjacent and opposite drive.
The difference image found the hole at 68-69° in 4 of 6 runs, 7-12x the sham. No single
absolute image did: every one is dominated by fixed features about 1-2.5 deep in
log(sigma/sigma0) (a trough at 270° seen on every disc, the screw-edge ring, the E2 area),
while the hole changes conductivity by about 0.2-0.3. The operator asked what software can do,
including for standing trees, which have no before-scan.

## Decision

Three additions to `tree_ert/absolute.py`:

1. **`solve_absolute_joint`** fits one conductivity to several drive patterns of one mounting.
   Each pattern keeps its own polarity sign and is weighted by 1 / RMS of its own measurement,
   so misfit stays a percentage and no pattern outvotes another. With one pattern it is exactly
   the old solve, which now delegates to it.
2. **`compare_absolute`** returns per-element log(sigma_after / sigma_before) between two
   solved maps: a before/after comparison in real units.
3. **`consensus`** keeps only what independent solves agree on in sign, taking the weaker
   value; the intent was a reference-free filter for trees.

## Rationale and measured result (disc-08, 2026-10-27)

| Method | New hole at 60° | Verdict |
|---|---|---|
| Single absolute image (any pattern) | never the deepest feature | fails |
| Joint solve, single run | misfit 19.5-20.6 % (between adjacent 23 % and opposite 11 %); trough 136-272° | no better for a standalone image |
| `consensus` of adjacent and opposite | ratio of the E10 feature to the rest 1.01-1.06 | does not separate; the fixed features are common to both patterns |
| Cross-disc mean subtracted (leave-one-out over 4 discs) | not adopted | contacts differ per mounting, so the "instrument fingerprint" does not transfer |
| `compare_absolute` D1 vs S1 | trough **68°** for adjacent, opposite and joint; hole/rest 1.47, 1.30, **3.34** | **works**, joint is clearest on a clean run |

The joint solve is kept because it is the best input to `compare_absolute` on clean runs, and
it is exact for one pattern. `consensus` is kept, documented as not effective on these data, so
the negative result is reproducible rather than re-tried.

## Consequences

- A before/after comparison of absolute images is a second, independent route to the ADR-0068
  difference evidence, in real units (about 20-25 % lower conductivity at the hole). It still
  needs a before-scan, so it is not a standalone absolute detection.
- Disturbed runs spoil it more than the measurement-difference image: D2 opposite and
  D3 adjacent (wiring disturbances mid-run) give hole/rest 0.14-0.46; the joint solve inherits
  the worse run of its pair.
- **No software change tested here makes a single absolute image find the hole.** The
  dominant fixed trough at 270° appears on disc-01, disc-02, disc-06 and disc-08 alike and
  coincides with a measured 138-140 Ω E10-E11 short; it is an instrument fault, to be fixed in
  hardware. For standing trees, the realistic route is the same as here: a reference scan at
  installation and later scans compared against it (ADR-0059), plus the hardware fix.
- A complete-electrode (contact impedance) model was considered and not implemented now: in
  four-electrode measurements the sense electrodes carry no current, so contact impedance does
  not enter in series, and the observed dominant artefact is a wiring fault, not contacts.

## Verification

`tests/test_absolute.py`: joint solve recovers a homogeneous field from two patterns, equals the
single solve for one pattern, and locates an inclusion; `compare_absolute` locates a void added
between two synthetic solves; `consensus` keeps only shared-sign values. Full test module
passes. `exports/disc-08-drill-20261027/compare_absolute.py` reproduces the table above.
