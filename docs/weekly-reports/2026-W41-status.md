# Weekly Status Report — 2026-W41 (5–11 October 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

Two big steps. First, the saline localisation result was scored rigorously, producing the
project's headline figure: **median angle error 3.4°, 21 of 22 placements within 10°**.
Second, absolute (static) reconstruction was implemented with quality gates and automatic
recalibration, and run on all ten cut discs. Absolute images that passed tended to put
their peaks on the worst contacts, so a pass is not yet evidence of a defect.

## 2. Circuit construction

- E2 and E3 contacts intermittent on discs (E2 open in two runs; E3 dead then alive).

## 3. Testing and verification

- **Fidelity metrics** (`docs/thesis-fidelity-metrics.md`, `verify_device.py`): angular
  localisation error, NCC and Dice, each reported as a margin over its own empty-tank
  control. SSIM demoted to a diagnostic (ADR-0050, ADR-0053).
- Bugs found and fixed while scoring:
  - Tank geometry constants were wrong (bucket radius 128 mm, electrode ring 98 mm), so the
    apparent "radial collapse" was a mask error (ADR-0052).
  - The angle estimator was replaced: strongest pixel, then a fixed window, then the
    connected lobe, because window choice alone moved one placement by up to 12°
    (ADR-0054, ADR-0055).
- Validity criteria for claiming a hole (ADR-0058) and standing-tree readiness (ADR-0059)
  drafted.

## 4. Scans

- 2026-10-06: 41 runs (ten-disc absolute series).
- 2026-10-07/08: 51 runs (contact, settle and gel series; disc-05 dry and holed).
- Run conditions can now be corrected afterwards in a dated key, never overwritten
  (ADR-0056).

## 5. Difference imaging

**Saline result** (2026-10-02 series, 22 placements with photographic ground truth):

| Measure | Result |
|---|---|
| Median angle error | 3.4° |
| Within 5° | 16 of 22 |
| Within 10° (⅓ of electrode spacing) | 21 of 22 |
| Worst placement | 11.9° (at E2, drift-affected) |
| NCC beats control | 19 of 19 |
| Dice beats control | 19 of 19 |

NCC and Dice show the pipeline is repeatable; only the angle has independent ground truth
(photos). On discs, disc-06 compared with itself gave 2.2× noise: a false positive above
the 2.0 gate.

## 6. Absolute imaging

- **Implemented** (ADR-0041): homogeneous fit, then damped log-σ Gauss–Newton. Refused
  unless reciprocity ≤15 %, misfit ≤15 % and significance ≥2.0.
- **Recalibration** in the Qt UI: re-acquires with new settings until the gates pass;
  made adaptive on 2026-10-08 (more averaging when noise >3 %, else try settle times in
  10–50 ms, then 90 % DAC; up to 6 attempts; ADR-0060).
- **Ten-disc series:** disc-01 passed twice after re-seating E10 (reciprocity 2.5–2.8 %,
  misfit 7.8–8.6 %). Discs 02–10 refused; E2 worst or second-worst on 8 of 9.
- disc-06 passed twice, but its peak sat at ~140°, on its worst contacts (E2/E3).
  **Absolute peaks may image contacts, not defects** (ADR-0057).

## 7. Saline tank

Scoring and thesis text completed for the 2026-10-02 series (above). Photos verified
against each run's recorded target.

## 8. Resistor ring

Checks on 2026-10-06 and 2026-10-07: reciprocity 0.1 %.

## 9. Wood discs

- Settle 30 ms beat 100 ms on disc-01 (reciprocity 6.5 % against 13.9 %).
- Dry screws did better than gel (13–25 % with gel against 6.5–8.7 % dry), but the
  comparison was not controlled.
- Contact faults followed the wood when disc-02 was rotated.
- disc-08 (hole near E10, 270°): absolute peak at 12°, i.e. the hole was not found.
- disc-05: nine dry runs, reciprocity 20–24 %.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34; fit checked after the board rework in W37.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| E2/E3 contacts | Dominate disc refusals and absolute peaks |
| Gate pass ≠ defect | Absolute peaks land on bad contacts |
| Electrode inset unmodelled | Real electrodes sit inside the boundary; correcting it is not yet adopted |

## 12. Plan for next week

Improve absolute image display; run a saline position series for absolute imaging; scan
disc matrices to find settings that pass.
