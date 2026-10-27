# ADR-0080: Electrode map corrected to the actual wiring: E11 on C11, E12 on C12, C10 unused

- **Status:** Accepted
- **Date:** 2026-10-27
- **Supersedes:** the channel table in [ADR-0079](0079-e11-moved-from-mux-c10-to-c12.md) (its context and rationale stand)
- **Affects:** `ELECTRODE_CHANNEL` in the unified `.ino`, `tests/test_phase3a_unified_firmware.py`
- **Reversal:** tags `firmware-e11-on-c10` (identity map, E11 on C10) and `firmware-e11-on-c12` (the ADR-0079 table)

## Context

ADR-0079 mapped E11 to C12 and left E12 on C11. The first disc-08 scan after flashing
(20261027-174058 / -174701) fitted far worse than before the change (opposite misfit 36.9 % against
11.2 %, adjacent 56.8 % against 22.7 %), with the change concentrated at E10-E12. The operator then
confirmed the rewiring had actually shifted both wires up one channel: E11 is on C11 and E12 on C12,
and C10 (the leaking channel) is free.

## Decision

`ELECTRODE_CHANNEL = {0..9, 11, 12}`. Nothing else changes.

## Consequences

- Runs `20261027-174058-disc-08-c1-opposite` and `20261027-174701-disc-08-c1-adjacent` were taken with
  E11 and E12 swapped relative to the firmware map and are invalid.
- C12 now sits next to C11 (E11) and C13 (unused); a leak between C11 and C12 would join E11 and E12.

## Verification

The firmware text test asserts the new table; the sketch compiles. On hardware: `?` replies after
flashing with `CDCOnBoot=cdc`, and the next disc-08 scan must return to roughly the misfit of D1.
