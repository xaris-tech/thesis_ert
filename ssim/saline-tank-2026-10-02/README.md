# SSIM series — saline tank, 2026-10-02

Purpose: measure how well the instrument localises a known target in a saline
tank, scored by SSIM (structural similarity) between each reconstruction and a
ground-truth mask of where the block actually was. Method: [ADR-0044](../../docs/adr/0044-saline-ssim-series-fresh-baseline-per-target-group.md).

## Layout

```text
ssim/saline-tank-2026-10-02/
    README.md        this file: what was done and what was found
    NEXT-STEPS.md    what still has to be done
    manifest.csv     one row per run: role, target, expected vs reconstructed angle
    photos/          top-down photographs, one per target run, named <run_id>.jpg
                     (photos/README.md, PHOTO-INDEX.csv, SSIM-REFERENCE.csv)
    runs/            copies of the run directories from scans/runs/ (originals stay there)
```

`runs/` is a copy. `scans/runs/` and `scans/index.csv` remain the documented
capture series (ADR-0025); if the two ever disagree, `scans/` wins.

## Setup

| Item | Value |
|---|---|
| Tank | circular bucket, inner radius 128 mm, 12 electrodes |
| Electrode ring | radius 98 mm — the nails are driven ~30 mm into the bucket wall |
| Electrode map | E1 = marked nail, clockwise viewed from above |
| Image angle of Ek | 180° − 30°·(k−1): E1 180°, E4 90°, E7 0°, E10 270° |
| Target | wooden block, 23 × 22 mm footprint, 51 mm tall, standing upright |
| Position | "near Ek" = block centre ≈ 55 mm from tank centre (0.56 of the electrode ring), on the line to Ek |
| Settings | adjacent, high range, DAC 400, settle 30 ms, 16 samples, 10 warmup, 5 frames |
| Not recorded | saline g/L, fill depth, water temperature, grounding |

**Corrected 2026-10-05 (ADR-0049).** This table previously said the tank radius was
160 mm and the block sat 128 mm from the centre, i.e. 0.80 of that tank — level with
the bucket wall, which is not a placement anyone can make by accident. Measured: the
bucket is 128 mm and the nails sit 30 mm inside it. The block is at ≈55 mm, about
0.56 of the electrode ring. **The block radius is a reconstruction from the data, not
a tape measurement, and is the largest remaining uncertainty in this series.**

## What happened

### Morning (11:42–13:53) — excluded

Runs `114218` to `134418` are not part of the series. Each one was imaged against
a baseline that was still drifting, mostly at E2 (150°). Example: wood at E1
(`134418`) against baseline `133531` gave significance 0.92× with the peak at
150°. The baseline differed from *itself* (frames 1–5 vs 6–10) by 0.188, which
is about the size of a block signal. Comparing only the settled end of that
baseline against the target put the peak at 185°, on E1, so the block was there
but was hidden by the drift.

On the way, several wrong explanations were tried and dropped, among them that
E2 is broken and that the tank needs reciprocity ≤ 2%. September's runs
(2026-09-22, `purified-saline-*`) found wood at the right angle with 10–15%
reciprocity, and this afternoon's runs did too. Reciprocity of 10–13% is normal
for this tank and does not stop detection.

The morning runs stay in `scans/runs/` and are listed in `manifest.csv` as
`excluded-unsettled`. They are not copied here.

### Afternoon (13:57–16:54) — the series

Procedure: let the tank settle, capture an empty baseline, check that it does
not differ from itself, then run 2–4 target positions against it. Capture a new
baseline before the next group and always immediately before positions near E1,
E2 or E3.

| Baseline | Self-difference | Drift since previous baseline | Runs against it |
|---|---|---|---|
| `135739` | 0.024 | — | E9, E10, E11, E4 |
| `143242` | 0.009 | 0.221 at 150° | E5, E6, E7, E8 |
| `151045` | 0.017 | 0.103 at 150° | E12, E1 |
| `153056` | 0.014 | 0.024 at 150° | E3, E2 (first) |
| `164714` | — | — | E2 (repeat) |

"Self-difference" is the peak of frames 1–2 differenced against frames 4–5 of
the same baseline. "Drift" is the peak of one baseline differenced against the
previous one. All drift appeared at 150° (E2), and it shrank through the
afternoon.

### Results: near-electrode ring (12/12 detected)

| Electrode | Expected | Peak | Error | Significance | Run |
|---|---|---|---|---|---|
| E1 | 180° | 184° | +4° | 12.4× | `152426` |
| E2 | 150° | 138° | −12° | 6.5× | `165444` (repeat, fresh baseline) |
| E3 | 120° | 112° | −8° | 17.8× | `153824` |
| E4 | 90° | 87° | −3° | 12.8× | `142601` |
| E5 | 60° | 69° | +9° | 35.5× | `144109` |
| E6 | 30° | 39° | +9° | 34.4× | `144734` |
| E7 | 0° | 0° | 0° | 32.9× | `145332` |
| E8 | 330° | 323° | −7° | 34.1× | `150425` |
| E9 | 300° | 305° | +5° | 9.4× | `140411` |
| E10 | 270° | 274° | +4° | 11.0× | `141259` |
| E11 | 240° | 236° | −4° | 11.0× | `141918` |
| E12 | 210° | 211° | +1° | 13.2× | `151731` |

Mean absolute angle error: 5.5°. Every peak is negative, meaning more resistive,
which is what wood in saline should give.

The first E2 run (`164016`, 147°, 19.5×, peak −0.248) was imaged against a
baseline 70 minutes old. Because E2 is where the drift appears, that peak cannot
be separated from drift. It is superseded by the repeat `165444` (−0.153).

### Results: centre and opposite pairs (7/7 located)

All are against baseline `170541` (17:05). The plan called for a fresh baseline
before the E2 pair; none was taken, and the E2+E8 redo came 66 minutes after it.

| Run | Blocks | Angle error per block | Raw SSIM | Blurred SSIM |
|---|---|---|---|---|
| `171321` | centre | peak 0.13 R from the centre | 0.53 | 0.70 |
| `172321` | E1 + E7 | −1.5°, +2.1° | 0.35 | 0.37 |
| `173951` | E3 + E9 † | +1.4°, −4.4° | 0.39 | 0.41 |
| `174738` | E4 + E10 | −1.7°, +2.7° | 0.38 | 0.37 |
| `175516` | E5 + E11 | −4.2°, −9.0° | 0.31 | 0.31 |
| `180403` | E6 + E12 | +15.0°, −8.5° | 0.32 | 0.34 |
| `181205` | E2 + E8 | −0.4°, +2.5° | 0.38 | 0.47 |

† Typed as "e3 e10". The plan for that slot was E3+E9, and the image fits
E9 (−4°), not E10 (+26°). I relabelled the run to the plan, so the ground truth
is inferred partly from the result. **This is unconfirmed: no photograph of this
setup was taken** (see `photos/README.md`). The single-block photos `3.jpg`,
`9.jpg` and `10.jpg` — now `20261002-153824`, `-140411` and `-141259` — are from
two to three hours earlier and are not ground truth for it.

Excluded: `173123`. Its target text was left over from the previous run
("e1 e7"), and its blobs (about 163° and 296°) match no planned pair. It was
superseded by the E2+E8 redo `181205`.

Both blocks of every pair appear as separate blobs. The pairs score lower SSIM
than single blocks, because two blobs pulled toward the centre miss two masks.

### SSIM summary (ADR-0045) — and why the SSIM numbers must not be quoted

19 scored runs. **After the region fix** (ADR-0046; the mean now runs over a dilated
neighbourhood of the mask instead of the whole disc), re-measured against each run's
own empty-tank control, comparing against a simulated block of the recorded
23 × 22 mm footprint pushed through the same solver (ADR-0047):

| metric | min | max | mean | empty tank | beats its control |
|---|---|---|---|---|---|
| significance | 5.80 | 35.49 | 14.94 | 1.0 by definition | — |
| angle error (deg) | 0.96 | 18.18 | 5.81 | — | — |
| **NCC** | −0.155 | 0.873 | **0.569** | −0.011 | **17 / 19** |
| Dice | 0.000 | 1.000 | 0.588 | 0.085 | 15 / 19 |
| SSIM | −0.061 | 0.272 | 0.130 | 0.023 | 16 / 19 |

**NCC is the recommended score** (ADR-0047). It is scale-invariant, so it does not
punish the dim-but-correct lobe that sinks SSIM, and it is position-sensitive, so a
blob in the wrong place scores near zero. It is not SSIM and is not "SSIM-like" — it
measures linear agreement of the intensity pattern, and two blobs of different size
sharing a bright centre correlate highly. The empty-tank column is part of the result,
not decoration.

The three runs that fail to beat their own control: E2 (`165444`, the documented
drift electrode), and the pairs `174738` and `175516`, both marginal.

**The published values in `ssim_results.csv` are stale** — 0.284–0.591, mean 0.438,
from before the region fix, and SSIM-only. `ssim_eval.py` does not yet emit the NCC and
Dice columns, so that CSV needs the tool changed before it can be regenerated
(ADR-0047).

**Even after the fix, the SSIM column must not be quoted as published.** Before it,
`tree_ert/ssim.py` averaged SSIM over the whole disc while the block mask is
16–42 px of a 3228 px disc. In the remaining 99 % both rasters sit near zero, so the
luminance term carried the ratio to ≈1 whatever the image contained — an empty tank
scored 0.904–0.957 and **all 19 runs scored below it**. A mean of 0.438 therefore did
not mean "moderate structural agreement".

That defect is fixed. **And the second apparent defect — a radius mismatch — was also a
units error, not a reconstruction failure (ADR-0049).** `TANK_RADIUS_MM` was 160 mm
when the bucket is 128 mm, and every normalised length was divided by the bucket radius
where the mesh normalises to the 98 mm electrode ring, making every mask radius and the
block's half-widths 1.31× too large. With that corrected:

| metric | before | after | empty tank | beats control |
|---|---|---|---|---|
| NCC | 0.569 mean, −0.155 min | **0.721 mean, 0.461 min** | 0.031 | **19 / 19** |
| Dice | 0.588 mean | **0.929 mean** | 0.204 | **19 / 19** |
| SSIM | 0.130 mean | 0.155 mean | −0.004 | 19 / 19 |

Every run now clears its own empty-tank control; the worst case moved from negative to
0.461. `ssim_results.csv` is **wrong**, not merely stale — it was scored against masks
at the wrong radius and size, and must be regenerated.

The result: **angle error median 3.4°, max 9.9° (ADR-0048), and NCC 0.72 mean against a
0.03 control with 19 of 19 runs clearing it.**

Full table: `ssim_results.csv` (**needs regenerating**). Images beside their masks:
`ssim_contact_sheet.png` (**also stale** — same masks).

Angle errors come from the pixel-grid wedge search. They differ by a few degrees from
the UI's peak angle quoted in the single-block table above.

### Known limitation: radius

This section described a defect that did not exist. Corrected 2026-10-05; the original
text is in the git history and in ADR-0049.

**There is no radial collapse.** Once `TANK_RADIUS_MM` was corrected to the measured
128 mm and lengths were normalised against the 98 mm electrode ring, the forward model
reproduces the recorded series without any tuning:

| block placed at (fraction of the electrode ring) | recovered centroid |
|---|---|
| 0.40 | 0.390 |
| 0.50 | 0.472 |
| 0.60 | 0.555 |
| 0.70 | 0.673 |
| 0.80 | 0.721 |

Near-linear, no systematic inward bias. The series measured centroid of 0.483 inverts
to a placed radius of 0.51, consistent with the block at about 0.56 of the ring.

What replaces it as the open question: **the block radius is inferred, not measured.**
0.56 of the ring comes from inverting the forward model against this data, corroborated
only by recollection. One tape measurement - block centre to tank centre, in mm - would
close it, and every mask radius in this series depends on it.

Also still open: the electrode inset itself is unmodelled. The mesh places electrodes on
the domain boundary; the hardware has them 30 mm further in, which is 23% of the radius.
Correcting it made agreement worse rather than better on the first attempt, so it was not
adopted - but it is a genuine model/hardware mismatch, not an approximation.
### Record amendments

Some target fields were blank or truncated at capture. They were filled in
afterwards from the operator's account, and each amended run says so in
`notes` (in both `conditions.json` and `conditions.md`). Values such as
`minor_diameter_mm` = 9 or 19 on some runs were typed in by mistake and are not
measurements.