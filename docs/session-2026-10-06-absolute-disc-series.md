# Session handoff, 2026-10-06: absolute reconstruction and the ten-disc series

Read this before scanning again. It covers four things:

- what was built
- what the ten cut coconut discs showed
- which settings to use
- what is open

The code decisions are recorded in ADR-0041, ADR-0042 and ADR-0043.

## TL;DR

- **Absolute reconstruction works on clean data.**
  - disc-01 passed twice: 2.5-2.8 % reciprocity and 7.8-8.6 % misfit.
  - sigma0 was 2.334 and 2.342 mS; the two runs agree to 0.4 %.
  - The two images correlate at 0.998.
- **It does not yet locate defects.** disc-01's lowest region is at E10, not at its known holes near E4-E7. This is unexplained; see open question 2.
- **Nine of ten discs were refused, and the main cause is hardware at E2, not the wood.**
  - E2 is the worst or second-worst electrode on 8 of the 9 failing discs.
  - The mean per-electrode reciprocity across every disc run falls away with distance from E2:

    | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | E9 | E10 | E11 | E12 |
    |---|---|---|---|---|---|---|---|---|---|---|---|
    | 33 | **41** | 28 | 21 | 18 | 17 | 15 | 16 | 19 | 19 | 20 | 16 |

  - The resistor ring read 0.1 % at 10:56, so the fault developed or worsened during the day. A clip or lead loosening with handling fits that.
- **Settings barely matter.** See "Best settings" below.
- **All data is from cut discs.** No standing tree has ever been scanned. The `coconuttree-1` run names, the 2026-09-23 runs, ADR-0039 and the Coconut preset's notes all call those discs a "standing tree", and that is wrong. Do not cite living-tree performance.

## What was built

| Piece | Where | Notes |
|---|---|---|
| Absolute solver | `tree_ert/absolute.py` | Closed-form homogeneous fit, then Gauss-Newton in log-sigma with: a Tikhonov prior toward sigma0 (weight 0.03); a backtracking line search; elements clipped to sigma0 ×/÷ 100. Watch out: pyeit's `compute_jac` returns **-dV/dsigma**, and the solve diverges without the sign flip. |
| Gates | `absolute.gate` | Reciprocity at most 15 %; misfit at most 15 %; significance at least 2.0. Significance is the peak of (sigma - sigma0) over the peak of the split-half absolute noise image. |
| Recalibration ramp | `absolute.recalibration_ladder` | Operator settings first. Then settle 10 / 30 / 50 / 75 / 100 / 150 / 200 ms, varying samples 8-32 (firmware cap), warmup 5-30, frames 10-16 and DAC 100-80 %. Up to about 4 h. |
| Stop rules | `absolute.stop_reason` | Stop after 3 refused attempts in a row that either flag a suspect electrode, or sit above 18 % reciprocity with nothing flagged (the wet-face pattern). |
| Qt UI | `tree_ert/qt/` | Adds an **Absolute** tab and a **Recalibrate until absolute image passes** checkbox. Each attempt is recorded as its own run, with `absolute.png` and `absolute.npz`. |
| CLI | `absolute_session.py` | Same flow, driven by a plan CSV (`plans/coconut-discs-2026-10-06.csv`). |
| Index | `run_record.read_index` | Now reads `scans/index.csv` correctly. Its 26-column header predates 14 later columns, and rows come in 6 layouts. |

## Ten-disc results (best attempt each)

| Disc | Best reciprocity | Worst electrodes (mean) | Outcome |
|---|---|---|---|
| 01 (holes E4-E7) | **2.5 %** | E10 before reseat | **PASS ×2** |
| 02 | 8.8 % | E2 44, E3 34 | refused |
| 03 | 22.0 % | E2 30, E10 26 | refused |
| 04 | 28.8 %; 7.6-8.2 % after re-clipping (leads swapped, so misfit invalid) | E2 67, E1 65 | refused |
| 05 | 30.4 % | E2 78, E1 59 | refused |
| 06 | 15.6 % | E2 49, E1 28; E6-E12 at 6-9 % | refused, contact stop |
| 07 | 44.4 % | E1 66, E2 54; all electrodes bad, 10 sign flips | refused |
| 08 (holes E10) | 19.3 % | E9 open (nail in or by a hole), then E2 35 | refused |
| 09 | 36.2 % | E2 77, E1 76 | refused |
| 10 (lighter, cause unknown) | 12.3 % | E1 33, E2 29 | refused, contact stop |

### Diagnostics that worked

- **Per-electrode reciprocity** (`capture_view.electrode_reciprocity`) located every fault:
  - a single bad nail (disc-01's E10, disc-08's E9)
  - the E2 cluster
  - disc-wide failure
- **Dropping one electrode's rows and re-solving.** On disc-01, excluding E10 took misfit from 36 % to 8 % and showed the rest of the data was sound. On disc-10, misfit stayed at 43-54 %, so its problem was disc-wide.
- **I_LOW counts by drive pair.** On disc-08, all 36 flagged records involved E9, which pointed straight at it.
- **Lead swap (disc-04).** After re-clipping, reciprocity fell from 28.8 % to 8.2 % on *all* electrodes. Clip-to-nail contact quality is the main variable.

## Best settings

Keep the **Coconut preset**: adjacent, high range, DAC 620, settle 30 ms, 32 samples, 5 warmup frames, 10 frames.

| Settle / samples | Runs | Median reciprocity | Median noise |
|---|---|---|---|
| 10 / 8 | 8 | 18.8 % | 3.09 % |
| 30 / 16 | 4 | 17.6 % | 4.91 % |
| **30 / 32 (preset)** | 16 | 19.3 % | 3.53 % |
| 100 / 32 | 2 | 17.7 % | 4.32 % |

- **Settings did not fix any disc.** Within a disc, changing settings moved reciprocity by a few points in no consistent direction (for example disc-06: 16.8 / 15.6 / 15.9 %). Both disc-01 passes used the preset.
- **10 ms / 8 samples is about 4× faster** (4 min against 16 min). Use it as a **screening scan** to reject a disc quickly. Do not use it for the record: on disc-01 it read 6.1 % against the preset's 2.5-2.8 %.
- **Current is high.** Worst-pair current reached 500-825 µA at DAC 620, against the preset's recorded 486 µA (the firmware's high-range rating is 1000 µA, so nothing was flagged). Lowering the DAC to about 560 is untested.
- **The recalibration ramp is a backstop, not a fix.** It cannot repair a contact or dry a face; the stop rules end it in about 25-30 minutes when it is hopeless.
- **Reciprocity limit for absolute images.** Across about 120 recorded runs there is a gap: runs at 4.9 % or below fit (misfit 4.7-7.5 %), and runs at 8.8 % or above do not (44-100 %). Nothing has been recorded in between. Proposed: a separate **6 %** absolute limit, keeping 15 % for difference images. **Not applied; needs the operator's OK.**

## Bench protocol that worked (disc-01)

1. Scan the resistor ring first. Expect about 0.1 % reciprocity.
2. Clean each nail head and clip jaw, and clip firmly.
3. Blot both faces and the rim dry. **Do not** oven-dry the whole disc.
4. If a single electrode is flagged, reseat that nail in solid wood away from holes and cracks. Moving the nail shifts its angle, so note the new position.
5. Run one preset scan with Recalibrate off, and check the per-electrode reciprocity before committing to a full scan.

## Open questions, in priority order

1. **E2 hardware.** Replace the E2 lead and clip, and check its mux wiring against `PHASE_3A_PINOUT_TABLES.md`. Confirm on the resistor ring. Then rescan discs 02-10.
2. **Why disc-01's absolute image misses its holes.** The lowest conductivity is at E10 (0.10-0.13× at 271°); the E4-E7 sector reads 0.94-1.31×. The image is deterministic, so it is either real structure or an electrode/geometry artifact: point electrodes, no contact impedance, an assumed circle. Run the **saline-tank rod test** (plastic rod at known positions: next to E5, next to E10, centre). If the low spot does not follow the rod, absolute imaging cannot localise defects with this model, and adding contact impedance (the complete electrode model) is the next step.
3. **Thickness, circumference and weight were not recorded** for any disc. Without them, sigma0 (a sheet conductance in mS) cannot be compared across discs or converted to S/m, and disc-10's lightness cannot be explained.
4. **Run `disc_survey.py`** on the passing intact discs once there are enough, to measure between-disc spread (ADR-0035) before claiming disc-01 or disc-08 differ.
5. **Correct the "standing tree" records.** Write a new ADR correcting ADR-0039, and fix the preset notes in `tree_ert/settings.py`. Proposed but not done; waiting on the operator.

## Data

- All of today's runs are in `scans/runs/20261006-*`. Each attempt is its own run with `absolute.png`/`absolute.npz`. The verdicts are in `summary.txt` and in the `absolute_*` columns of `scans/index.csv`.
- **Do not trust run `20261006-171852-disc-04-intact`'s misfit or image.** Leads E1/E2 and E7/E8 were swapped (recorded in Notes), so the electrode positions are wrong in the model. Its reciprocity (8.2 %) is valid.
- Runs with 0 or 1 frames are operator stops. They are kept, and the index marks them `cancelled`.
