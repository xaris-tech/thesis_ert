# Session handoff, 2026-10-07/08: contacts, settle time and gel on cut discs

Read this before the next bench session. It follows
`session-2026-10-06-absolute-disc-series.md` and corrects one of its open
questions (disc-01's "low region at E10").

All data is in commit `0924091` (`scans/runs/20261007-*`, `scans/runs/20261008-*`).
Every disc here is a **cut disc**. No standing tree was scanned.

## TL;DR

- **The electronics are sound.** The resistor ring read 0.1 % median and 0.3 % max reciprocity, with noise of 0.17 % (`20261007-162403-sanity`).
- **Contact faults follow the wood, not the channel.** disc-02 was rotated three positions (`174535` against `180226`), and the low-current, high-error electrodes moved three positions with it.
- **Settle 30 ms, not 100 ms.** On disc-01 with unchanged contacts, reciprocity was:

  | Settle | Reciprocity | Run |
  |---|---|---|
  | 100 ms | 13.9 % | `225021` |
  | 30 ms | 6.5 % | `230738` |
  | 10 ms | 7.3 % | `231630` |

  Per-electrode current agreed within 2 % across the three runs, so the contacts were the same. The likely cause is DC polarisation building up during the longer dwell. The default is already 30 ms (`tree_ert/settings.py`), but the recalibration ladder climbs to 200 ms (ADR-0042), so it moves the wrong way on wood.
- **Dry screws in solid wood beat gel; this is not yet a controlled test.**
  - Gel rescued open or uneven contacts: disc-02 went from 34 % to 14 %, and disc-07 from 38 % to 25 %.
  - No gel disc got below 12.6 %, and their misfits were 44-96 %.
  - The best dry results are disc-01 at 6.5 % and disc-06 at 6.9-8.7 %. disc-06 passed the absolute gates twice: misfit 12.5 and 12.9 %, sigma0 1.90 and 1.91 mS, peak at 140° both times.
- **Absolute peaks land on the worst contacts.** See ADR-0057. Until that is ruled out, an absolute PASS does not locate a defect.
- **A difference image can be a false positive just over the gate.** disc-06 against itself, untouched (`003801` against `002746`), scored 2.2× noise. ADR-0027's 2.0 cut-off is too close for a hole claim.
- **E2 and E3 are intermittent.**
  - E2 was open at `172054` (disc-02) and `192733` (disc-03).
  - E3 was dead for all of `234918` (disc-05), then alive at `000315`, a run chained automatically by Recalibrate.
  - The E2 lead itself can be good: it read 2-3 % on disc-01.

## Per-disc best result (DAC 620, adjacent)

| Disc | Gel | Best run | Reciprocity | Absolute | Worst electrodes |
|---|---|---|---|---|---|
| disc-01 (holes near E4-E7) | no | `230738` (30 ms) | 6.5 % | misfit 21 %, peak 316° | E10, E11 (16-21 %) |
| disc-02 | yes | `190651` | 14.2 % | misfit 80-88 % | E2, E3 |
| disc-03 | yes | `205903` | 17.2 % | misfit 69 % | E1, E2 |
| disc-04 | yes | `220201` | 12.6 % | misfit 90 % | spread |
| disc-05 | yes | `001637` | 18.5 % | misfit 51 % | E1, E2 (36-44 %) |
| disc-06 | no | `003801` | 6.9 % | **PASS ×2**, peak 140° | E2, E3 (25-31 %) |
| disc-07 | no, then gel | `011637` | 25.0 % | misfit 80 % | spread |
| disc-08 (hole near E10) | no | `012754` | 14.4 % | misfit 29 %, peak 12° | E1, E2, E9 |

**Gel records.** The `notes` field said "with gel" on disc-06 and disc-08, and was empty on the disc-01 runs, but **no gel was used on discs 01, 06 and 08**, per the operator. These 9 runs carry `conditions.extra["correction_2026-10-08"]`; see ADR-0056.

The gel status of disc-07 `011637` ("with gel") is **unconfirmed**.

## Electrode angles in the reconstruction mesh

These come from `ssim.electrode_unit_vectors` on the `create_solver` mesh. Use them to translate "peak at N deg":

| E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | E9 | E10 | E11 | E12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 180 | 150 | 120 | 90 | 60 | 30 | 0 | 330 | 300 | 270 | 240 | 210 |

## Findings from the git history that change the plan

- **`b059058` (2026-09-29).** A same-disc drill test already exists: holes near E7-E9 gave a difference peak at E7, at 3.6× noise. Wetting the disc surface made the data unusable (signal 0.8 mV, noise 11-22 %).
- **`a83f52c` (2026-10-02).** A cross-specimen baseline **cannot** discriminate a hole. Intact discs scored 0.10-0.85 against the reference, and holed discs 0.56-0.74. So the survey (ADR-0035/0038) on its own will not classify a disc as solid or holed.
- **The 10-06 disc-02 run (8.8 %) is not comparable to tonight's 14 %.** It had only 36/54 pairs and 9.9 % noise. There is no evidence that disc drying raised the error.

## How runs were reviewed

1. Grep `scans/session.log` from the last reviewed time.
2. For each new run, call `survey.load_frames`, then `capture_view.session_summary` and `capture_view.electrode_reciprocity`.
3. Also take the median `current_ua` per electrode from `frames.csv`.

Per-electrode current is the best contact diagnostic. If it is identical across two runs, nothing was physically changed between them.

## Next session protocol

### Settings, every run unless a step says otherwise

| Setting | Value |
|---|---|
| DAC | 620 |
| Settle | **30 ms** |
| Samples | **32** |
| Warmup / frames | 5 / 10 |
| Recalibrate | **off** |
| Notes | "no gel" or "with gel", typed fresh every run |
| Medium | cut disc |
| Specimen ID | filled in |
| Grounding | floating, unless deliberately grounded |
| Changes | record in notes, e.g. "E3 moved" |

### 1. Rig check, about 15 minutes

1. **Ring.** It should read about 0.1 %. If not, stop: the problem is hardware.
2. **E2 and E3 lead continuity.** With the board unplugged, measure from the board terminal to the clip while flexing the lead and pressing the perfboard joints. Resolder anything that jumps.
3. **Current.** Put a meter in series with one lead, hold one pair with the firmware `d` command, and compare against the reported current. This settles the still-unconfirmed current-sense miswiring.

### 2. Contacts or wood? disc-06, about an hour (tests ADR-0057)

1. Mount disc-06 dry and scan it as `disc-06-pos0`. Expect about 7 %, PASS, peak 140°.
2. Move E2 and E3 into fresh, solid wood, dry, and scan as `disc-06-e23-fixed`.

| Result | Meaning |
|---|---|
| The peak leaves 140° and E2/E3 fall to about 5 % | ADR-0057 holds |
| The peak stays at 140° with good contacts | It is something in the wood: photograph E2-E3 |

### 3. Gel, controlled, about 30 minutes

1. Take the last dry disc-06 scan.
2. Gel all 12 threads, at the same depth, and wipe the faces.
3. Wait 5 minutes and scan as `disc-06-gel`.

If reciprocity and misfit both get worse, stop using gel and write an ADR.

### 4. Locating a hole on disc-08, about an hour

The hole is near E10, at 270°.

1. Fix every electrode above 10 %.
2. Scan `disc-08-a` and `disc-08-b`. Both should PASS with the same peak.
3. Rotate the disc three positions (note the direction) and scan `disc-08-rot90` twice.

| Result | Meaning |
|---|---|
| The peak is near E10, then moves three positions | The absolute image locates the hole |
| The peak stays on the same electrode | It is still contacts |
| The peak moves somewhere unrelated | The image is not repeatable after remounting |

If disc-08 succeeds, repeat on disc-01 (fix E10/E11 first).

### 5. Only after step 4: intact discs for comparison

Scan intact discs dry, with every electrode under about 10 %. Record thickness, diameter and weight.

### Acceptance for a usable disc scan

- 216/216 OK, with no `I_LOW`
- per-electrode current within ±15 %
- median reciprocity under 10 %, with no electrode above 15 %
- noise under about 2 %
- absolute: misfit under 15 % and PASS
- difference: treat significance under about 3× as no change

### Do not

- spray or wet the disc faces
- use 100 ms settle, or Recalibrate, on discs
- touch screws or leads during a run, or between two scans that will be compared
- classify a disc by comparing it with other discs
- write "standing tree"

## Open paperwork

- **Recalibration ladder.** After the disc-06 test, write an ADR on whether the ladder should stop climbing settle above 30 ms for wood (ADR-0042). The default settle is already 30 ms.
- **ADR-0057.** Accept or reject it from the disc-06 and disc-08 results.
- **Significance margin.** The 2.2× self-difference result argues for a higher bar on hole claims.
- **Still pending from 2026-10-06:**
  - the 6 % reciprocity gate for absolute images
  - the "standing tree" correction ADR and the Coconut preset notes
  - `absolute_session.py` should treat naming problems as warnings, per ADR-0044
