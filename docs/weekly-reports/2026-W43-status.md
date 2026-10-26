# Weekly Status Report — 2026-W43 (19–25 October 2026, reported to 20 October)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

The last four disc matrices were scanned with all electrodes. Only disc-06 passed. An
open-circuit check found a new leak of about 156 µA with nothing connected (0.8 µA a month
earlier), which is now the prime suspect for the fixed troughs near E9/E10. Re-solving the
saline series with all electrodes gave 0 of 30 passes, so the saline result depends on
excluding E1/E2. A handoff document sets out the repair order and the decisive next
experiment.

### Status to date

| Area | Status |
|---|---|
| Circuit construction | Working; E1/E2 channel fault and open-circuit leak blocking |
| Testing | Self-test, dummy-load sweep, resistor ring routine; leak check to become routine |
| Scans | All runs since 2026-09-17 recorded with conditions |
| Difference imaging | **Validated in saline:** median 3.4°, 21/22 within 10° |
| Absolute imaging | Gated and working with exclusion; not trusted on wood |
| Saline tank | 28/29 pass with E1/E2 excluded, 0/30 with all electrodes |
| Resistor ring | Passing (18.1 Ω, reciprocity 0.07 %) |
| Wood discs | No hole reliably localised yet |
| 3D-printed case | Printed and fitted (W28–W34, W37) |

## 2. Circuit construction

- **Open-circuit leak** (2026-10-19): with nothing connected but the harness still
  attached, 156 µA at DAC 620 and 49 µA at DAC 100, every record marked OK. Highest when
  driving E9–E11 (198–203 µA). Not yet known whether it is in the harness or on the board.
- E1/E2 channel fault and current-source impedance (~770 Ω) still open.

## 3. Testing and verification

- Open-circuit check found the leak; it should be run at the start of every session and
  added to the self-test.

## 4. Scans

- 2026-10-19: 56 runs (disc-04, 06, 07, 09 matrices, all electrodes; open-circuit check).

## 5. Difference imaging

No new results. Same-specimen before/after drilling is now the planned test, since
cross-specimen baselines confound specimen differences with defects.

## 6. Absolute imaging

- With all electrodes, the saline series fails everywhere (misfit 38–64 %), with a trough
  fixed at E1 (~180°) even in the empty tank.
- Troughs that touch an electrode usually come from contacts, the leak or a channel fault,
  not from the wood.

## 7. Saline tank

Re-solved offline with all electrodes: **0 of 30 pass**. The thesis must state that the
saline absolute result depends on the E1/E2 exclusion. A 63-run series with all electrodes
is planned after the board is fixed.

## 8. Resistor ring

2026-10-19: 831 µA at DAC 400, 18.1 Ω, median reciprocity 0.07 % — unchanged. The ring's
low resistance cannot show the leak.

## 9. Wood discs

| Disc | Result |
|---|---|
| disc-06 (intact) | **6/6 pass at DAC 400** (misfit ~4 %, reciprocity ~1 %). After a DAC 620 run, current halved and runs 8–14 failed: contacts changed |
| disc-04 (intact outside) | 0/14; reciprocity 40–77 %, unstable contacts |
| disc-07 (interior unknown) | 0/14; misfit 84–92 %, possible internal defect |
| disc-09 (fungal growth) | 0/14; reciprocity 29–57 %, decay |

Overall: discs behave best at σ0 of about 2–6 mS with stable contacts; long DAC 620 runs
degraded two discs; prefer DAC 400 on wood.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34; fit checked after the board rework in W37.

When filling this in, note anything that bears on the current faults: a closed case can trap
moisture and worsen leakage, the harness needs strain relief, and the mux pins should stay
reachable for cleaning until the leak is fixed.

## 11. Risks and blockers

| Risk | Impact | Mitigation |
|---|---|---|
| Open-circuit leak | Biases high-impedance loads; likely cause of E9/E10 troughs | Unplug harness to locate; clean with IPA; suspect mux damage if it persists |
| E1/E2 channel fault | E1–E3 sector blind; saline fails with all electrodes | Clean/inspect mux; repeat nail swap; rescan saline with all electrodes |
| Current-source impedance | Weak signal on dry wood | ~360 kΩ across R1 or trimmer; re-run dummy-load sweep |
| Contacts and moisture | Most disc runs fail | Gel every screw; condition discs to equal moisture; record treatment |

## 12. Plan for next week

1. Locate and fix the leak (target ≲1 µA open-circuit).
2. Fix E1/E2; rescan saline with all electrodes (pass: misfit ≤15 %).
3. Fit the current-source trim; verify with `dummy_load_sweep.py`.
4. **Same-disc before/after drilling** on disc-06: 3 runs intact, drill in the E5–E7 sector
   without unclipping leads, 3 runs, same-specimen difference image. Pass: trough in the
   drilled sector, significance ≥2, repeats agree.
5. Add the open-circuit check to the self-test; move the matrix script into the repo.

Full detail: `docs/handoff-2026-10-19/README.md`.
