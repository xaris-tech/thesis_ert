# ADR-0049: The tank geometry constants were wrong; the "radial collapse" was a units error

- **Status:** Accepted
- **Date:** 2026-10-05
- **Affects:** `tree_ert/ssim.py` geometry constants and the two divisions that used them; the ground-truth radius of every mask; `ssim/saline-tank-2026-10-02/` results and README. Supersedes the *conclusion* of [ADR-0046](0046-reconstruction-settings-cannot-be-validated-yet.md), which correctly diagnosed a disagreement and misidentified its cause.
- **Related:** ADR-0045, ADR-0046, ADR-0047, ADR-0048

## Context

ADR-0046 recorded that the recorded 2026-10-02 series reconstructed blocks at
0.27–0.61 R when the series README placed them at 0.80 R, that the forward model did
not reproduce the collapse, and that `jac_normalized=True` fixed the real data while
making simulated accuracy worse. It froze the reconstruction settings and named
non-uniform drive current as the leading suspect.

The cause was neither. Two geometry constants in `tree_ert/ssim.py` were wrong:

```python
TANK_RADIUS_MM = 160.0     # actually 128.0  -- the bucket
NEAR_RADIUS_MM = 128.0     # actually ~55.0   -- the block
```

Measured on 2026-10-05: **the bucket's inner radius is 128 mm, and the nails are
driven at least 30 mm into it**, so the electrode ring sits at 98 mm. Two consequences
had never been noticed:

1. `128.0 / 160.0 = 0.80` placed the block level with the bucket wall. A block centred
   on the wall is not a placement anyone can make by accident, which is the first sign
   the figure was never measured.
2. **Every normalised length in the module was divided by the bucket radius when the
   mesh normalises to the electrode ring.** PyEIT puts the electrodes at radius 1.0, so
   the correct denominator is 98 mm, not 128 mm. Every radius, and the block's
   half-widths with them, was **1.31x too large**.

So the masks were drawn at 0.80 R with the wrong size, against images whose blobs sit
at ~0.51 of the electrode ring — and the "collapse" was the mask being wrong, not the
reconstruction.

## Decision

- `TANK_RADIUS_MM = 128.0`, new `ELECTRODE_INSET_MM = 30.0`,
  `ELECTRODE_RING_RADIUS_MM = 98.0`, and every length normalised by the electrode ring.
- `NEAR_RADIUS_MM = 55.0`, i.e. 0.561 of the ring. **Approximate** — see Consequences.
- `jac_normalized` stays `False`. ADR-0046 was right to freeze it and wrong about why.

## Rationale

Corrected, the forward model and the recorded data agree without any tuning. Placing a
simulated block at a known radius and reconstructing gives:

| block placed at (fraction of ring) | recovered centroid |
|---|---|
| 0.40 | 0.390 |
| 0.50 | 0.472 |
| 0.60 | 0.555 |
| 0.70 | 0.673 |
| 0.80 | 0.721 |

Near-linear, with no collapse. The recorded series' measured centroid is 0.483, which
inverts to a placed radius of **0.51**, matching the operator's independent recollection
of "0.56 or something". There was never a collapse to explain.

Effect on the scored series, same runs, same solver, only the geometry corrected:

| metric | with 160 mm / 0.80 R | with 128 mm / 0.56 R |
|---|---|---|
| NCC mean | 0.569 | **0.721** |
| NCC min | −0.155 | **0.461** |
| NCC beats its empty-tank control | 17/19 | **19/19** |
| Dice mean | 0.588 | **0.929** |
| Dice beats its empty-tank control | 15/19 | **19/19** |

Every run now clears its own control. The worst case moved from *negative* to 0.461.

Alternatives rejected:

- **`jac_normalized=True`.** ADR-0046 measured it as making simulated accuracy worse,
  and with the geometry corrected that remains true. Its apparent benefit was fitting
  a mask error. Rejected.
- **A mesh with the electrodes inset from the boundary.** This is the geometry the
  hardware actually has, and it builds cleanly with electrode angles preserved exactly
  (E1 180°, E4 90°, E7 0°, E10 270°). It is *not* adopted here because it made agreement
  with the recorded data worse, not better, and the simulated blocks in that mesh did
  not produce usable centroids. It is the obvious next thing to try, and it needs the
  block radius settled first — see below.
- **Weight as a cause.** The block was held down by something that does not touch the
  water. Current only flows through the saline, so a dry object is electrically
  invisible and cannot have contributed. Ruled out on physics, not tested.

## Consequences

- **`ssim_results.csv` is wrong, not merely stale.** Every `true_radius`, `peak_radius`
  and score in it was computed against a mask at the wrong radius and the wrong size.
  It must be regenerated, and the earlier figures should not be quoted.
- **`NEAR_RADIUS_MM = 55.0` is a reconstruction, not a measurement.** It comes from
  inverting the forward model against the recorded data, cross-checked against the
  operator's recollection of "0.56 or something". Neither is a tape measure. Every mask
  radius inherits this uncertainty, and it is now the largest single uncertainty in the
  scoring. **One measurement — block centre to tank centre, in mm — would settle it.**
- **The electrode inset is still unmodelled.** The mesh places electrodes on the domain
  boundary; the hardware has them ~23% of the radius further in. That is a real
  model/hardware mismatch, now documented rather than accidentally assumed away.
- The series README's "known limitation: radius" section is void and must be rewritten.
- **A caution worth carrying forward:** three separate wrong assumptions survived for the
  life of the series because each was internally consistent — the solver with a bad flag
  looked self-consistent, the mask looked self-consistent, and the scores looked
  self-consistent. Only a directly measured dimension broke the chain. Constants derived
  from other constants deserve a tape measure.

## Verification

Re-score the series and compare against the table above; the NCC and Dice columns
should reproduce to three decimals. `tests/test_ssim.py` now derives the block radius
from `NEAR_RADIUS_MM / ELECTRODE_RING_RADIUS_MM` rather than hard-coding 0.8, so a
future geometry correction cannot leave the geometry tests quietly stale — which is
exactly how this survived.