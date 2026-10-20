# Photos

Top-down photographs of the tank with the block in place, one per target run.
These are the ground truth for where the block actually was.

## Naming

`<run_id>.jpg`, matching the run's `conditions.json` and its folder under
`runs/`. All 18 files were renamed to this scheme on 2026-10-05; they arrived
named by electrode (`6.jpg`, `6&12.jpg`, `center.jpg`).

Each rename was verified against the run's recorded `target_description`, not
inferred from the filename. All 18 matched.

## Index

`PHOTO-INDEX.csv` — one row per photo, joined to the run's recorded target, its
UI angle figures, and its SSIM scores.

`SSIM-REFERENCE.csv` — the same runs with two reference scores added, because
the measured scores are not interpretable on their own:

| column | meaning |
|---|---|
| `ssim_raw_measured` | the published `ssim_raw` for this run |
| `ssim_raw_empty_tank` | the same metric against an all-zero image — **an empty tank scores 0.90–0.96** |
| `ssim_blurred_empty_tank` | the same for `ssim_blurred` — an empty tank scores 0.49–0.75 |
| `ssim_raw_perfect_placement` | 1.0000 by construction; the ceiling |

**All 19 scored runs score below an empty tank.** The mask is 16–42 px of a
3228 px disc (0.5–1.3 %), so in the background both rasters are near zero and
the luminance term carries SSIM to ≈1 regardless of content. This is a property
of averaging over the whole disc, not of the instrument. See the SSIM summary
in the parent `README.md`.

## Coverage

18 of the 19 scored runs have a photo. Missing:

| run | blocks | why |
|---|---|---|
| `20261002-173951` | E3+E9 or E3+E10 | **not photographed — the E3+E9/E3+E10 question stays open.** The `3.jpg`, `9.jpg` and `10.jpg` singles are from runs 153824 / 140411 / 141259, captured two to three hours earlier, so they are not ground truth for it. |

Not photographed, and not needing to be: the five baselines (`135739`,
`143242`, `151045`, `153056`, `164714`, `170541`), the superseded E2 run
`164016`, and the excluded run `173123`.

## What these photos can and cannot settle

They **can** settle block *angle*, which is what `angle_error_deg` measures.

They **cannot** settle block *radius*. No ruler is in frame in any of them, so
`true_radius = 0.80` is not a measurement — it is the hard-coded
`NEAR_RADIUS_MM / TANK_RADIUS_MM = 128/160` in `tree_ert/ssim.py`, applied
unchanged to all 19 runs. Since the radial pull is the series' headline
limitation, note that its ground truth is an assumption.

The `E1 = marked nail` reference is also not visible. What can be seen is the
yellow tape numbering on the alligator clips, which establishes the ring
*ordering*; the absolute angle origin rests on the formula in the parent
`README.md`, unverified by any photograph.

## Quality notes

- `20261002-180403` is distinctly oblique — the tank reads as an ellipse and a
  mirror is in frame. Unusable for radial measurement even with a ruler.
- `20261002-171321`, `20261002-144109` and `20261002-144734` are acceptably
  top-down.
- In `20261002-180403` the two blocks do not look like the same object: one has
  a pale grey-white mass on its top face, the other a dark greenish one, and
  neither matches the plain wet top face in the single-block photos. If that
  pair really used two different objects it is not a clean two-identical-blocks
  test, and its SSIM is not comparable with the other pairs. **Unresolved.**