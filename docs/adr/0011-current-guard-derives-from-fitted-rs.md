# ADR-0011: Derive the over-current guard from the fitted Rs, and flag a saturated current channel

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** `firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino`,
  `tests/test_phase3a_unified_firmware.py`, the `STATUS,2` record, the `Q,` quality vocabulary,
  and any thesis claim that a `Q,OK` measurement was taken within the validated drive envelope
- **Related:** `docs/planned-improvements.md` 1.1 (low output impedance, `Rs = 10.2 ohm` measured),
  `docs/first-working-prototype/03-howland-current-source.md` (range table and `Iload` equation),
  [ADR-0007](0007-accept-either-mcp4725-address.md) (same pattern: verify the binding, do not
  trust the assumed configuration)

## Context

A 2026-09-02 bench session opened the debug UI against the board and every measurement in every
frame came back identical:

```text
M,P,FWD,I+,E12,I-,E1,V+,E7,V-,E8,V,0.000,I,2613.636,Q,I_HIGH
```

`2613.636 uA x 97.9 ohm = 255.87 mV`, which is 99.95 percent of the ADS1115's 256.00 mV full
scale on `GAIN_SIXTEEN` - the fixed range `readCurrentUa()` uses. The reading was not a
measurement, it was the ADC rail. `readVoltageMv()` already detects its own clip and falls back
to a wider range; `readCurrentUa()` had no equivalent, so it divided a railed count by
`shuntOhms` and emitted a three-decimal figure indistinguishable from a real over-current.

Multimeter follow-up established the current was genuinely out of range, and why:

| Measurement | Value | Expected |
|---|---:|---:|
| Across the shunt (A2-A3) | 0.400 V, railed | 157 uA at the boot defaults |
| Shunt low side to ground | 0 V | 0 V (correct) |
| Rs, in circuit | **10.2 ohm** | 68 ohm - firmware believed `RANGE_LOW` |
| OPA2134 pin 1 to ground | 3.9 V | a few tens of mV |
| MCP4725 VOUT | 0.080 V | 80.6 mV at code 100 (correct) |

The fitted resistor complement was then inventoried as 2 x 5k, 3 x 100 ohm, and 1 x 10 ohm,
which is exactly the specified BOM: R1 and R3 at 5.00 kohm, R2 and R4 at 100 ohm, the 100 ohm
return shunt, and a single Rs at 10 ohm. Note that only one Rs is fitted - the 22 ohm and
68 ohm parts backing the MEDIUM and LOW ranges do not physically exist on this board, so two
of the three ranges the firmware offers cannot be selected in hardware at all.

Two independent defects surfaced.

**The guard was looser than the hardware.** `MAX_CURRENT_UA` was a single flat `1200.0f`. From
`Iload = VDAC * 0.02 / Rs` with a 3.3 V DAC, the range table's maxima are 100 uA (LOW),
500 uA (MEDIUM), and 1000 uA (HIGH). The flat ceiling therefore sat *above the entire design's
maximum*: on LOW it could not flag an over-current until the reading was 12x the validated
figure. It was not a guard, it was a formality.

**The firmware's belief about Rs was never checked.** `currentRange` defaults to `RANGE_LOW`
at every boot and there is no persistence, but Rs is a physical jumper the firmware cannot read
back. The fitted resistor measured 10.2 ohm - the HIGH jumper - and `planned-improvements.md`
1.1 records the same `Rs = 10.2 ohm` from 2026-08-27, so the board has been on HIGH the whole
time while the firmware enforced LOW's code-420 ceiling. At the real Rs that ceiling permits
about 663 uA against LOW's 100 uA design limit: the DAC clamp was 6.6x too permissive, silently,
from power-on. This is why the failure presents as "it does this the first time I open it" -
the mismatch is re-established on every reset.

The root cause of the railed current itself is a separate hardware fault still open at the time of
writing, and not covered by this ADR. The gain implied by the measurements is
`I*Rs/VDAC = 0.521` against a design 0.02, which corresponds to no resistor actually fitted -
so it is not a wrong-value error but a loop that is not regulating, with the load setting the
current. `I_SRC_OUT` consequently sits at 3.86 V against the CD4067 mux supply of 3.3 V, so
mux input protection diodes are conducting; that is both a damage risk and a plausible
explanation for the accompanying `V,0.000` on every sense pair. This ADR is about the fact
that firmware reported `Q,I_HIGH` with a precise-looking number instead of saying the channel
was railed and its own assumptions were unverified.

## Decision

The over-current guard is computed per range as `designMaxUa * CURRENT_GUARD_HEADROOM` from the
`CURRENT_RANGES` table rather than from one flat constant; `readCurrentUa()` records when the
shunt read reaches 99 percent of the `GAIN_SIXTEEN` full scale and `qualityFlag()` returns a new
`I_SAT` flag for that case ahead of every other test; and `STATUS,2` gains `RS_DECLARED`, which
is `0` until the operator selects a range with `el`/`em`/`eh` in the current session, with a
boot-time `[WARN]` stating the assumed Rs.

## Rationale

Deriving the ceiling from the same table that already holds `rsOhms` and `maxDacCode` keeps one
source of truth: the range table now fully describes a range, and a future range cannot be added
with a DAC ceiling but no current ceiling. `CURRENT_GUARD_HEADROOM = 1.25f` (matching the
existing `VOLTAGE_RANGE_HEADROOM`) absorbs tolerance on Rs and the DAC reference so a legitimate
full-scale drive is not flagged, while still catching the order-of-magnitude faults a flat
ceiling missed. It is a judgement call, not a measured figure.

`I_SAT` is separated from `I_HIGH` because they demand different responses. `I_HIGH` means "the
current is real and too large - lower the DAC code." `I_SAT` means "the reported number is
fiction - do not use it for anything," which matters because `paired_transfer_resistance()`
normalises each measurement by its own measured current. The host already treats any non-`OK`
flag as bad, so the new flag needs no host change to be safe, and `MAX_CURRENT_UA` keeps its key
in `STATUS,2` (now carrying the derived value) so `parse_status` at
`phase3a_unified_reconstruct.py:417` continues to work.

Alternatives considered:

- **Just lower `MAX_CURRENT_UA` from 1200 to 1000.** Rejected: still wrong by 10x on LOW, which
  is the range bring-up is required to start on, and leaves the range table half-describing a
  range.
- **Autorange the current channel like the voltage channel.** Rejected for now. It would hide
  the saturation rather than report it, and at 4 mA the fault needed surfacing, not
  accommodating. The shunt range is also fixed by design intent (100 mV at 1 mA sits comfortably
  inside `GAIN_SIXTEEN`); a reading that rails it is a fault, not a signal that needs more range.
- **Refuse to capture until `el`/`em`/`eh` is sent.** Rejected as too blunt: it would break
  every existing script and the demo path for a condition the operator may already have verified
  physically. `RS_DECLARED` reports the uncertainty and lets the host decide.
- **Infer Rs from a measured current at a known DAC code.** Rejected: it assumes the Howland is
  regulating, which is exactly what was false here. A self-check that depends on the thing it is
  checking is worthless.

## Consequences

Captures taken on a range the operator never declared are now identifiable after the fact, but
only from `STATUS` - frames already logged before this change carry no such marker, so **no
existing capture in `phase3a_logs/` can be shown to have run at its assumed Rs.** Given the
10.2 ohm measurement, the safe assumption is that all of them ran on HIGH.

The guard is now roughly 12x tighter on LOW. Real captures that previously passed may now be
flagged `I_HIGH`, and because `validate_record()` raises on any non-`OK` quality
(`planned-improvements.md` 1.4), a whole capture can abort where it previously completed. That
is the intended behaviour - those captures were outside the validated envelope - but it will
look like a regression on first flash and should not be "fixed" by raising the headroom.

`RS_DECLARED` is session state, not a measurement. It records that a human asserted the jumper
position; it does not verify it. Nothing in the firmware or host can catch an operator who sends
`el` with the HIGH jumper fitted, and this ADR does not claim otherwise.

Adding a flag to the `Q,` vocabulary commits the host to treating unknown flags as non-`OK`
rather than erroring. That holds today (`record.quality == "OK"` at
`phase3a_unified_reconstruct.py:197`), and any future flag must keep that property.

## Verification

`tests/test_phase3a_unified_firmware.py` covers all three parts:
`test_over_current_guard_is_derived_per_range_not_a_flat_ceiling` asserts the flat constant is
gone and that each range row carries its design maximum;
`test_saturated_current_channel_is_flagged_not_reported_as_a_value` asserts the clip test and
the `I_SAT` return; `test_status_reports_whether_the_rs_jumper_was_declared` asserts the
`RS_DECLARED` field and that `setCurrentRange` sets it. These are text assertions against the
`.ino` source - per [ADR-0005](0005-firmware-tests-stay-text-assertions.md) they are a
doc/code sync guard, not behavioural proof.

**This has not been flashed or confirmed on hardware.** The board was mid-diagnosis with a
non-regulating current source when this was written. Bench verification means: repair the
current source, declare the range matching the fitted Rs, and confirm on `?` that
`MAX_CURRENT_UA` tracks
the declared range (125.0 / 625.0 / 1250.0) and `RS_DECLARED,1`. The decision is falsified if a
known-good saline capture at the validated DAC code produces `I_HIGH` on the correct range -
that would mean 1.25 headroom is too tight and the figure needs a measured replacement.
