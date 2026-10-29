# Saline tank position photos (2026-10-22/23 position series)

Raw top-down photos of the saline tank, one per block placement, used as ground truth
for the position series runs. Photos are unedited; camera rotation, tilt, framing and
white balance vary between shots.

## How the photos were processed

- Nail tips (E1-E12) and block centres were read by hand from gridded copies (automatic
  detection failed on shadows and dirt). An ellipse fitted through the 12 tips removes
  rotation, tilt and scale; positions are in units of the nail-tip ring (ring = 1.0),
  the unit the reconstruction mesh uses. Angle is interpolated between the two
  neighbouring nails. Hand-reading error is about +/-0.04 in radius, +/-3 deg in angle.
- Measured radii are biased outward: the camera sees the raised block top (and the coin
  on pair blocks), not the base.

## Findings

- 17 of 19 photos use one setup whose clip labels match the runs (reconstructions land on
  the labelled electrode). `wood8.jpg` and `wood5&11.jpg` show a different setup (screw-head
  nails) whose labels run mirrored: target = 8 - label (mod 12).
- wood8 matches the 2026-10-14 E8 runs best, not the 2026-10-22 ones; wood5&11 is matched
  to the 2026-10-23 E5+E11 runs (only candidate).
- Scale: the water edge is ~1.55x the nail-tip ring and the nails protrude 25-30 mm, so the
  ring radius is ~50 mm, not the 98 mm in `tree_ert/ssim.py`. Coin size agrees. Not yet
  changed in code.
- E2 was intermittent in this series; leaving E2's measurements out of the difference
  solve lifts E3/E4 from ~0.55 to ~0.76 NCC.

## Files

| file | content |
|---|---|
| `ground_truth.csv`, `ground_truth_map.png` | measured block position per photo |
| `run_map.csv` | photo -> latest three runs |
| `odd_photo_scores.csv` | wood8 / wood5&11 candidate runs scored |
| `ncc_scores.csv`, `ncc_block_size.csv` | NCC vs simulated block, footprint sweep |
| `ncc_best_search*.csv`, `ncc_ring50_search*.csv` | best-NCC search (runs x spot x size x E2 x ring) |
| `contact_sheet.png` | photo, rectified photo, difference, absolute, NCC per position |
| `scripts/` | the scripts that produced the above (written for one-off use; paths are absolute) |

Scores in the contact sheet are best cases over that search, not one fixed recipe.
