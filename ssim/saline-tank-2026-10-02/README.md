# SSIM series — saline tank, 2026-10-02

Purpose: measure how well the instrument localises a known target in a saline
tank, scored by SSIM (structural similarity) between each reconstruction and a
ground-truth mask of where the block actually was. Method: [ADR-0047](../../docs/adr/0047-saline-ssim-series-fresh-baseline-per-target-group.md).

## Layout

```text
ssim/saline-tank-2026-10-02/
    README.md        this file: what was done and what was found
    NEXT-STEPS.md    what still has to be done
    manifest.csv     one row per run: role, target, expected vs reconstructed angle
    photos/          top-down photographs, one per target run (see photos/README.md)
    runs/            copies of the run directories from scans/runs/ (originals stay there)
```

`runs/` is a copy. `scans/runs/` and `scans/index.csv` remain the documented
capture series (ADR-0025); if the two ever disagree, `scans/` wins.

## Setup

| Item | Value |
|---|---|
| Tank | circular, radius ≈ 160 mm, 12 electrodes |
| Electrode map | E1 = marked nail, clockwise viewed from above |
| Image angle of Ek | 180° − 30°·(k−1): E1 180°, E4 90°, E7 0°, E10 270° |
| Target | wooden block, 23 × 22 mm footprint, 51 mm tall, standing upright |
| Position | "near Ek" = block centre ≈ 128 mm from tank centre, on the line to Ek |
| Settings | adjacent, high range, DAC 400, settle 30 ms, 16 samples, 10 warmup, 5 frames |
| Not recorded | saline g/L, fill depth, water temperature, grounding |

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
is inferred partly from the result. **This is unconfirmed until the photo is
checked.** If the photo shows E10, relabel the run and re-score it.

Excluded: `173123`. Its target text was left over from the previous run
("e1 e7"), and its blobs (about 163° and 296°) match no planned pair. It was
superseded by the E2+E8 redo `181205`.

Both blocks of every pair appear as separate blobs. The pairs score lower SSIM
than single blocks, because two blobs pulled toward the centre miss two masks.

### SSIM summary (ADR-0048)

19 scored runs. Raw SSIM: mean 0.438, range 0.28–0.59. Blurred SSIM: mean
0.458. Angle error: |error| ≤ 12° on 22 of 24 angled block placements (the centre run has no angle); the exceptions
are E6 (+18°, single) and E6 in its pair (+15°). Both E6 placements read high,
which is worth checking against the photos. Full table:
`ssim_results.csv`. Images beside their masks: `ssim_contact_sheet.png`.

Angle errors here come from the pixel-grid wedge search. They differ by a few
degrees from the UI's peak angle quoted in the single-block table above.

### Known limitation: radius

Peaks come out at about 0.35–0.5 R although the blocks were at about 0.8 R. A
one-step JAC reconstruction with regularisation pulls targets toward the centre
and blurs them. The angle is reliable; the radius is not. Raw SSIM against a
sharp, correctly placed mask will therefore score low even for a correct
detection. ADR-0047 sets out how this will be reported.

### Record amendments

Some target fields were blank or truncated at capture. They were filled in
afterwards from the operator's account, and each amended run says so in
`notes` (in both `conditions.json` and `conditions.md`). Values such as
`minor_diameter_mm` = 9 or 19 on some runs were typed in by mistake and are not
measurements.
