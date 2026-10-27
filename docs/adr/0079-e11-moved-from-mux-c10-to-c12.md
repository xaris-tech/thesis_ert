# ADR-0079: Electrode E11 moved from mux channel C10 to spare channel C12

- **Status:** Accepted
- **Date:** 2026-10-27
- **Affects:** `firmware/esp32s3-phase3a-unified-arduino/.../esp32s3_phase3a_unified.ino` (`ELECTRODE_CHANNEL`, `configureDriveAndSense`), the board's E11 wiring on all four muxes, every run from this change on
- **Related:** ADR-0064, ADR-0067 (E1/E2 suspected inside the mux), ADR-0066 (open-circuit leak gate), ADR-0078
- **Reversal:** git tag `firmware-e11-on-c10` is the last commit with the identity map; reverting needs the E11 wires moved back to C10 as well.

## Context

Open-circuit checks on 2026-10-26 showed about 435 uA on every drive using E11 with nothing
attached (limit 20 uA). With the board unpowered the operator measured E10-E11 at 138-140 ohm,
then after cleaning 140 kohm, and E11-E12 at 360 kohm, against about 7 Mohm for a healthy pair
(E7-E8). On the CD74HC4067, C10 (E11) sits between C9 (E10) and C11 (E12), so leakage from
C10 to both neighbours is what was measured. The operator traced it to the muxes themselves,
and the absolute images of every disc (disc-01, -02, -06, -08) carried a trough at E10/E11
(about 270 deg). C12-C15 were unused and measured in the megaohms.

## Decision

The operator moved the E11 wire from C10 to C12 on all four muxes (current source, current
return, V+, V-). The firmware maps electrode index to mux channel through one table,
`ELECTRODE_CHANNEL = {0..9, 12, 11}`, used for all four `writeMuxAddress` calls in
`configureDriveAndSense`; electrode numbering, the FRAME protocol and the host are unchanged.

## Rationale

- **Moving to a spare channel** avoids the leaking pin without reworking the chip; cleaning
  improved it from 140 ohm to 140 kohm but not to megaohms.
- **One table, applied in one function,** keeps the electrode-to-channel mapping in a single
  place, so a future move of another electrode is a one-number change.
- **Rejected: replacing the mux chip.** More rework, and which of the four chips leaks was not
  isolated.
- **Rejected: excluding E11 from solves.** It costs a quarter of the measurements next to E10
  and does not remove the leak from the other electrodes' drives.

## Consequences

- Firmware and wiring must match: this firmware on C10 wiring, or the old firmware on C12
  wiring, reads an unconnected channel for E11.
- Runs before 2026-10-27 15:xx used C10 and carry the E10/E11 leak; the conditions of the first
  runs after the change record "E11 on C12". Absolute features at about 270 deg in earlier runs
  should be read as possibly instrumental.
- C12 (pin 19) is next to C11 (pin 20, E12); residue spreading there would bring the leak back
  between E11 and E12.

- Flashing from `arduino-cli` needs `--fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc`. The plain
  `esp32:esp32:esp32s3` default routes `Serial` to UART0, so the board runs but stays silent on
  USB (seen on 2026-10-27 until reflashed with CDC on boot).

## Verification

`tests/test_phase3a_unified_firmware.py::test_e11_is_wired_to_c12_and_every_mux_write_goes_through_the_map`
checks the table and that all four mux writes go through it; `tests/test_firmware_compiles.py`
builds the sketch. On hardware: the open-circuit check after flashing must show E10 and E11
drives at a few uA (ADR-0066), and the next disc scans should lose the common 270 deg trough.
