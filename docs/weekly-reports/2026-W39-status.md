# Weekly Status Report — 2026-W39 (21–27 September 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

A breakthrough week. The resistor ring found the cause of the long-standing reciprocity
fault: a wiring error on the V− multiplexer's address lines. After the fix, reciprocity on
the ring dropped from 66.5 % to 0.1 %, and the first gate-passing difference images
located wooden targets in the saline tank. Coconut-tree capture settings were tuned on a
standing tree.

## 2. Circuit construction

- **V− mux address miswire fixed** (2026-09-22, ADR-0031): the V− mux's S1 pin was wired to
  both GPIO35 and GPIO41, and S2 was unconnected. Every V− measurement on E3–E6, E11 and E12
  sensed the wrong electrode. **Reciprocity data from before this fix is compromised.**
- **E9 belt fault repaired** (2026-09-23): E9 drive had collapsed to 8–9 µA; after
  rewiring, all 108 ring cells read 17.6–18.6 Ω.

## 3. Testing and verification

- **Reciprocity gate set at 15 %** with a per-electrode contact warning (ADR-0032). Healthy
  nails read 8–11 % after the fix.
- Specimen geometry fields (circumference, thickness, diameters, nail positions) added to
  the run record, and presets for the resistor belt, saline tank and coconut (ADR-0033,
  ADR-0036).

## 4. Scans

- 2026-09-22: 32 runs (resistor ring, purified saline, target localisation).
- 2026-09-23: 19 runs (E9 repair, belt check, coconut tuning).
- **Coconut tuning on one standing tree**, one setting at a time: DAC 400 → 500 → 620
  improved signal and noise; 32 samples beat 16. At DAC 620 / 30 ms / 32 samples the
  current was 367 µA median, and reciprocity reached its best so far (median 2.53 %).

## 5. Difference imaging

- **First gate-passing image** (`20260922-164503`): wood at E9, peak at 307°, 20.8× the
  noise.
- Two blocks at E6/E12 resolved; removing them collapses the image — but only when pairs
  touching E2 are excluded. With E2 included, a bad contact produces false blobs.

## 6. Absolute imaging

Still blocked, but its main obstacle (reciprocity) is now fixed on the ring.

## 7. Saline tank

- Diluted saline raised the signal 20× but reciprocity only fell from 95 % to 75 %, which
  showed that offset and polarisation were not the main cause.
- After the mux fix, targets at E8/E9, E4/E5, E11/E12 and E7 were imaged; steel rod,
  two-block and removal runs taken.

## 8. Resistor ring

- **Built and used:** 12 × 220 Ω resistors between neighbouring leads; every adjacent
  measurement should read R/12 = 18.33 Ω.
- Before the fix: reciprocity 66.5 % median, errors confined to six V− channels, which
  pointed straight at the address wiring.
- After the fix: **reciprocity 0.1 % median, 0.3 % max, noise 0.14 %** — the instrument's
  own floor.

## 9. Wood discs

No change.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34; fit checked after the board rework in W37.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| E2 contact in saline | Produces false blobs unless excluded |
| Skip patterns | No reciprocal pairs, so reciprocity cannot be checked on them |

## 12. Plan for next week

Move from the standing tree to cut trunk discs; measure how much intact discs differ from
each other before claiming any defect.
