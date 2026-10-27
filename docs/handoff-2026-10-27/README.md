# Handoff 2026-10-27: board faults found and half fixed; next, check other discs for the E2 fault

Read `CLAUDE.md`, `AGENTS.md`, `docs/handoff-2026-10-20/README.md` first. This covers 2026-10-26/27.

## 1. Where the hardware stands

| Item | State | Evidence |
|---|---|---|
| **E11 (was mux C10)** | **Fixed.** C10 leaked to its neighbours (E10-E11 140 ohm, later 140 kohm; E11-E12 360 kohm; healthy pairs ~7 Mohm). The operator rewired: **E11 on C11, E12 on C12, C10 unused.** Firmware maps electrode to channel through `ELECTRODE_CHANNEL` (ADR-0079, table corrected by ADR-0080). Open-circuit after the fix: E10/E11 drives 0 uA (was ~435 uA). | `exports/open-circuit-2026-10-27/after-e11-c12.log` |
| **Open-circuit bursts** | Two of twelve frames still spiked to ~225 uA on the E9-E11 drives for one frame each. Not found. | same log |
| **E2 on the V- mux (C1)** | **Intermittent, not fixed.** Only E2's path through the **V- sense mux** goes wrong; drive (I+/I-) and V+ through E2 are fine. When it fails, dropping the records where E2 is V- takes adjacent misfit from 63-86 % to 10-19 %. No leak (E2 reads Mohm to neighbours), continuity looks fine, pressing the board did not trigger it. It switches state between runs on its own: ok 18:41-18:48, faulty for all of 18:54. | `exports/e2-vn-check-20261027/` |
| E9 contact on disc-08 | Weak in adjacent drive (41 % -> 9 % without E9). A disc-side contact, seen before on this disc. | `20261027-180426-disc-08-c2-adjacent` |

Firmware tags, oldest first: `firmware-e11-on-c10` (original), `firmware-e11-on-c12` (ADR-0079 table, did not match the wiring), **`firmware-e11-c11-e12-c12` (current, correct)**. Flash with
`arduino-cli compile --upload -p COM7 --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc <sketch>`; without
`CDCOnBoot=cdc` the board runs but is silent on USB.

## 2. Results worth keeping

- **disc-08 drill test (sham-controlled).** New 4 cm through-hole at E5: difference image finds it at
  68-69 deg in 4 of 6 runs, 7-12x the sham; the joint before/after comparison of absolute maps finds it
  at 68 deg, 3.3x the rest (ADR-0078). Photo: hole at about 70 deg, r about 0.37. No single absolute
  image shows it: its effect on the measurements (~5 % RMS) is below the model misfit (11-15 %).
- **disc-08 old hole near E10.** Absolute trough at 270 deg persists after the C10 leak was removed
  (C2 opposite, 15.1 %), and the photo puts the hole at about 272 deg, r about 0.40. The solver places
  it at the rim rather than at r 0.4.
- **disc-05 with E2 working (B3 opposite, `20261027-184835`).** All 12 electrodes, misfit 6.2 %,
  every leave-one-out 2-7 %, trough at **182 deg on the hole near E1**. This is the first standalone
  absolute image that locates a hole with no exclusion and no reference scan.
- Composite figures for disc-08 are in `exports/disc-08-drill-20261027/`; the composite is two
  measurements merged and must be captioned as such.

## 3. Next session: check other discs before rewiring E2

The decision on moving E2 from C1 to a spare channel (C13; avoid C10) depends on how often the E2 V-
fault appears. Do this first:

1. Open-circuit check, leads off (`exports/open-circuit-2026-10-20/open_circuit_check.py 2`).
2. For each available disc (disc-01, disc-02, disc-06, disc-08, disc-05): clip, then run
   `exports/e2-vn-check-20261027/e2_vn_watch.py 6` (about 5 minutes, adjacent). Each line prints
   misfit with all records and without E2-as-V-; a gap above 10 points prints `E2 V- FAULTY`.
3. Then one `disc_step.py` scan per disc (opposite + adjacent, about 12 minutes):
   `exports/disc-01-drill-test-20261023/disc_step.py <disc> B1 "<target>"`.
4. Afterwards, solve each run with and without E2-as-V- (see the snippet in the 2026-10-27 session or
   reuse `e2_vn_watch.py` logic) and tabulate how often the fault is present.

Decision rule: if the fault shows on any disc or any run, move E2 to C13 on all four muxes and change
`ELECTRODE_CHANNEL[1]` to 13 (tag first, test, ADR, flash with `CDCOnBoot=cdc`, then repeat step 2).
If it never shows across all discs, leave the wiring and keep the live check as a per-session test.

Also rescan one disc that had the 270 deg trough before (disc-01 or disc-06): if it is gone, the old
trough there was the C10 leak, which strengthens the disc-08 E10 reading.
