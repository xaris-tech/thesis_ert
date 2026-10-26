# Weekly Status Report — 2026-W40 (28 September – 4 October 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

Disc work began: cut trunk discs were scanned wet, dry, intact and drilled, and an
intact-disc survey measured how much discs differ from one another. The survey showed that
using a different disc as the baseline cannot reveal a hole. In the saline tank, a
localisation series covering all 12 electrode positions, the centre and six opposite pairs
was captured and scored.

## 2. Circuit construction

- **Belt E10–E11 short repaired** (2026-09-29): ring reads 17.66–18.49 Ω afterwards,
  reciprocity 0.08 % median.

## 3. Testing and verification

- Specimen naming check (medium from a fixed list, specimen IDs like `disc-03`) — first a
  refusal (ADR-0037), relaxed to a warning on 2026-10-01 (ADR-0044); editable run label.
- Coconut preset fixed at adjacent / DAC 620 / 30 ms / 32 samples (ADR-0039).

## 4. Scans

- 2026-09-29: 20 runs (belt repair, cut disc wet/dry, drill test).
- 2026-10-01: 26 runs (belt check, intact-disc survey, adjacent and opposite).
- 2026-10-02: 44 runs (cross-specimen baseline test, saline series).

## 5. Difference imaging

- **Load a recorded run as the baseline** (ADR-0046): any earlier run can be the baseline,
  remembered at startup; images against another specimen are stamped CROSS-SPECIMEN
  BASELINE.
- **Cross-specimen test:** against a disc-06 baseline, a rescan of disc-06 peaked at 0.018,
  but intact discs 2–5 peaked at 0.10–0.85 and the holed discs 8 and 1 at 0.56–0.74. The
  holed discs sit inside the intact range, so **a cross-specimen baseline cannot detect a
  hole**. Same-specimen rescans give 0.02–0.05.
- An unchanged-disc rescan scored 3.6× the split-half noise: drift between runs is not
  captured by the current control image.

## 6. Absolute imaging

No change.

## 7. Saline tank

- **2026-10-02 localisation series:** fresh baseline every 2–4 targets (ADR-0047). Centre,
  single blocks and six opposite pairs captured.
- First scoring: angle error ≤12° on 22 of 24 placements. SSIM scoring added (ADR-0048) and
  revised the following week.

## 8. Resistor ring

Belt checks 2026-09-29 and 2026-10-01 reproduce the gold result (17.7–18.5 Ω, reciprocity
0.1 %).

## 9. Wood discs

- **Wet surface:** signal 0.8 mV, noise 11–22 %. Unusable.
- **Dry and intact:** noise 0.41–0.50 %.
- **Drilled near E7–E9:** peak at E7, 3.6× noise.
- **Intact-disc survey** (ADR-0035, ADR-0038; `disc_survey.py`): discs 2–6 usable; disc 7
  excluded (offset near E2–E3), disc 8 excluded (22–70 µA everywhere). On disc 4, opposite
  drive gave 5.7× the signal of adjacent and lower noise (6.4 % against 34 %), but opposite
  has no reciprocal pairs.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34; fit checked after the board rework in W37.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| Cross-specimen baselines | Cannot discriminate a hole; same-specimen before/after needed |
| Contacts on wood | E8 lost contact mid-series; several runs excluded for contact faults |
| Specimen labelling errors | Some runs carry the wrong ID; corrected in survey manifests |

## 12. Plan for next week

Score the saline series properly; implement absolute reconstruction now that reciprocity
can pass.
