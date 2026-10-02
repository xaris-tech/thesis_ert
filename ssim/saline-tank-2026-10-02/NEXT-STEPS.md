# Next steps

## 1. Photos

Put one top-down photo per target run in `photos/`, named by run ID (see
`photos/README.md`). Without photos the true block position is only the
operator's word, and the E5/E6 errors (+9°) cannot be told apart from placement.

## 2. Remaining captures (18 of 30)

Same settings and procedure as the afternoon: settle, empty baseline, 2–3
targets, new baseline. Write the full target text and check it before pressing
Start. Distances are from tank centre to block centre: near = 128 mm,
halfway = 80 mm, centre = 0.

| # | Block A | Block B |
|---|---|---|
| 13 | centre | — |
| 14 | near E1 | near E7 |
| 15 | near E2 | near E8 |
| 16 | near E3 | near E9 |
| 17 | near E4 | near E10 |
| 18 | near E5 | near E11 |
| 19 | near E6 | near E12 |
| 20 | halfway E1 | — |
| 21 | halfway E4 | — |
| 22 | halfway E7 | — |
| 23 | halfway E10 | — |
| 24 | halfway E1 | halfway E7 |
| 25 | halfway E4 | halfway E10 |
| 26 | centre | near E1 |
| 27 | centre | near E7 |
| 28 | near E1 + near E2, side by side | — |
| 29 | repeat near E7 | — |
| 30 | repeat centre | — |

Expect the centre and halfway runs to be weaker. The block covers about 0.6% of
the tank, and sensitivity is lowest at the centre. A result under 2× there is a
finding, not a failure.

Every ~10 runs, capture one control: a baseline followed by a second empty
capture. It should come out under 2×.

Record salinity (g/L), fill depth and water temperature once for the session.

## 3. SSIM script (to be written)

Planned, per ADR-0044:

1. Read `manifest.csv` and each run's target text, and turn it into block
   positions.
2. Rasterise a ground-truth mask (23 × 22 mm footprint per block) on the
   reconstruction grid.
3. Reconstruct each target against its own baseline, using the same code path
   as the UI (`tree_ert.reconstruction.reconstruct`).
4. Report three numbers per run: raw SSIM, SSIM against the mask blurred to
   the system's point-spread width, and angle error. Angle error is the
   headline; raw SSIM is reported but not used to judge detection.
5. Write `ssim_results.csv` and a contact sheet of image vs mask.
