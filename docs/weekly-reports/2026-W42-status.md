# Weekly Status Report — 2026-W42 (12–18 October 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

The board's E1/E2 channels were found to be faulty: the fault stays with the channel when
nails are swapped. Excluding them makes absolute imaging work in saline (28 of 29 runs pass,
wood located within 2–9°). The dummy-load sweep finally ran and showed the current source's
output impedance is far too low (about 770 Ω). Disc matrices on discs 01, 02, 03, 05, 08 and
10 mostly failed; where images passed, they missed the holes.

## 2. Circuit construction

- **E1/E2 channels faulty:** the contact flag stays on E1/E2 after swapping nails 1↔12 and
  2↔3. Excluding them drops saline misfit from 56–67 % to 10–13 %; dropping a healthy pair
  (E5/E6) changes nothing.
- **Current source depends on the load:** ring alone against ring + 1 kΩ gives
  Rout ≈ 770 Ω and 154 mV output at DAC 0. A 1.4 % resistor ratio mismatch predicts about
  720 Ω. Fix (not fitted yet): about 360 kΩ in parallel with R1, or a trimmer.

## 3. Testing and verification

- Dummy-load sweep (`exports/dummy-load-20261014.csv`).
- Localisation result restated as tiers so the strongest defensible claim is explicit: all
  24 placements (median 3.07°, 23/24 within 10°); 22 photographed (3.40°, 21/22); 21
  without the drift scan (3.13°, 21/21).
- `ssim_eval.py` bug fixed: it was discarding the electrode mapping; results regenerated.

## 4. Scans

- 2026-10-13: 31 runs (resistor belt, disc-01/02/05).
- 2026-10-14: 65 runs (saline position series, disc-01/05 matrices, ring, dummy load, nail
  swap).
- 2026-10-16: 56 runs (disc-02, 03, 08, 10 matrices).
- Matrix design: DAC 400/620 × settle 10/30/50 ms × 16/32 samples, 14 runs per disc. Run by
  a script not yet in the repo (`docs/handoff-2026-10-19/scripts/`).

## 5. Difference imaging

- Saline difference images against the no-wood run: wood found within 2–7°.
- Discs against a disc-02 baseline: disc-01 and disc-05 are dominated by a trough at E10
  (271°), so their holes are not resolved; disc-08 shows a low spot at 323°, 23° outside
  its hole sector — suggestive only.

## 6. Absolute imaging

- Log-scale display, and a **trough** (half-depth connected lobe) reported beside the peak,
  flagged when it touches an electrode (ADR-0061–0063).
- **Faulty channels can be excluded** from the absolute solve (ADR-0064).
- Colours match difference images: blue less conductive, red more (ADR-0065).

## 7. Saline tank

**2026-10-14 position series** (adjacent, nail electrodes, ~50 mm fill, concentration not
measured):
- With E1/E2 excluded: **28 of 29 pass**; wood at E4, E6, E8, E10 found within 2–9°;
  repeats agree within about 1°.
- Best: DAC 620 (or 400), settle 10 ms, 16 samples; shorter settle always better.
- A fixed high spot near E7 and a weak trough at E8 appear even with no wood.

## 8. Resistor ring

Checks on 2026-10-13 and 2026-10-14 pass; the chain is sound on low-resistance loads.

## 9. Wood discs

| Disc | Result |
|---|---|
| disc-01 (holes E4–E7) | 11–12 of 12 pass, but trough at E10 every time: holes missed |
| disc-02 (intact) | 0/14 with all electrodes; 13/14 with E1/E2 excluded; same E10 trough |
| disc-03 (intact) | 0/14; still fails with E1/E2 excluded (too wet) |
| disc-05 (hole E1–E2) | Refused; hole sits in the excluded sector |
| disc-08 (hole E9–E11) | 0/14 on misfit (18–38 %) |
| disc-10 (intact, light) | 0/14; too dry, current only 87–136 µA |

disc-01 and intact disc-02 share the same E10 trough, so **gates passing ≠ a correct
image**.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34; fit checked after the board rework in W37.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| E1/E2 channel fault | Saline only passes with exclusion; E1–E3 sector blind |
| Current-source impedance | Weak current on dry wood |
| Fixed E10 trough on discs | Artefact, cause unknown |

## 12. Plan for next week

Finish disc matrices (04, 06, 07, 09) with all electrodes; check saline without exclusion;
investigate the E10 trough.
