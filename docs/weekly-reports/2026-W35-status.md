# Weekly Status Report — 2026-W35 (24–30 August 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

Work resumed after a seven-week gap. An independent validity audit of the code was
completed on 2026-08-27, drift-tuning presets were finalised, and soldering QA checklists
were written for the hand-built perfboard.

## 2. Circuit construction

- Soldering checklist and QA sheet written (`docs/SOLDERING_CHECKLIST.md`,
  `docs/soldering_qa_checklist.html`).
- The board is hand-soldered perfboard, so solder bridges and flux leakage are likely
  faults to check for.

## 3. Testing and verification

- **Validity audit** (`docs/validity-audit.md`): 5 defects reproduced and fixed with tests
  (D-01 to D-05), including wrong reconstruction sign/angle conventions and untrusted rows
  being substituted rather than dropped. 3 architectural limits recorded as open (L-01 to
  L-03).
- A forward-model test now pushes a target of known angle and sign through the pipeline and
  checks both.
- A dummy-load sweep gave an output impedance of about 430 Ω. In W36 this turned out to
  mean the "current source" was acting as a voltage source.

## 4. Scans

Bench captures to the legacy `phase3a_logs/` folder (no conditions recorded).

## 5. Difference imaging

Reconstruction conventions corrected by the audit fixes (D-01, D-02).

## 6. Absolute imaging

No change.

## 7. Saline tank

No change.

## 8. Resistor ring

No change.

## 9. Wood discs

No change.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| Firmware tests are text matches only | They cannot fail on behaviour (audit item X-03) |
| Open limits L-01 to L-03 | Current starvation, analogue-path accuracy and settling |

## 12. Plan for next week

Walk the full validation ladder on hardware on the living palm.
