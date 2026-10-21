# Weekly Status Report — 2026-W36 (31 August – 6 September 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

The first full bench session on the living palm. It found and fixed the most serious
hardware fault to date: the Howland pump's current-sense feedback was wired to the wrong
node, so the instrument had been a voltage source since it was built. After the repair,
current tracks the DAC code linearly. The ADR practice (architecture decision records)
started this week, with ADR-0001 to ADR-0019 written.

## 2. Circuit construction

- **E5 contact repaired** (ADR-0009): E5 delivered 84 µA against a 677 µA median.
  Re-seating it raised it to 738–754 µA. The cause was the electrode–tissue contact, not
  the multiplexer.
- **Current-sense miswire repaired** (ADR-0014): OPA2134 pin 5 was wired to pin 1, before
  the sense resistor Rs, instead of after it. Continuity checks had missed it because Rs is
  only 10 Ω. After moving the wire, current tracks the DAC at 1.531 µA/code (designed
  1.580). **Every capture before this repair was taken with a voltage source.**
- MCP4725 DAC answers at 0x60 on this board, not the documented 0x61; both are accepted now
  (ADR-0007).

## 3. Testing and verification

- **Self-test suite** added (`tree_ert/selftest.py`): per-component checks that run on
  recorded evidence and report SKIP, not FAIL, without a board.
- **Firmware compile test** added (ADR-0016): the active sketch now builds in the test
  suite.
- Current guards derived from the fitted Rs; a new `I_SAT` flag; minimum-current floor
  raised to 10 µA after a null frame with the amplifier unpowered read up to 2.55 µA
  (ADR-0011, ADR-0012).
- `HOLD` command and `dummy_load_sweep.py` added to measure the source's output impedance
  (ADR-0015).
- **Reciprocity** (swap the drive and sense pairs; a passive medium should read the same):
  the metric was fixed so it no longer saturates at 200 % (ADR-0008). Reciprocity error
  stayed at about 57 % after the repair, and six hypotheses (DAC, settle, discharge,
  autorange, leakage, pairing convention) were ruled out (ADR-0017, ADR-0018). The cause
  was found in W39.

## 4. Scans

- Post-repair baseline and control: max drift 0.32 %, correlation 1.000; all 108 pairs
  valid on 20 frames. **Detection floor: changes under about 0.5 % cannot be told from
  drift.**
- Evidence logs committed to `phase3a_logs/` because ADRs cite them.

## 5. Difference imaging

- Untrusted rows are now dropped from the solver instead of being replaced with baseline
  values (ADR-0002).
- Optional pinned colour scale (ADR-0004).
- **Target run on the palm was a null result:** the target changed the data by 0.212 %
  against 0.172 % for the control. The drilled void did not change between captures, so
  difference imaging could not see it (ADR-0019).

## 6. Absolute imaging

Blocked: with 57 % reciprocity error, the forward model does not match the instrument
(ADR-0018).

## 7. Saline tank

No change.

## 8. Resistor ring

Proposed as a resistor phantom to separate instrument faults from electrode faults
(ADR-0018); deferred pending materials.

## 9. Wood discs

No change.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| Reciprocity error ~57 % | Cause unknown; blocks absolute imaging |
| Pre-repair data | All captures before ADR-0014 used a voltage source; current-injection claims for them withdrawn |
| Source stopped delivering current late on 2026-09-02 | Shunt read only noise; supply or DAC path suspected |

## 12. Plan for next week

Restore drive current; build a phantom to bisect the reciprocity fault.

*Next: week W37 covers refitting the case.*
