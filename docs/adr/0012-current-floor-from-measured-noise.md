# ADR-0012: Set the minimum-current floor from a measured null frame, not a nominal value

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** `firmware/.../esp32s3_phase3a_unified.ino` (`MIN_CURRENT_UA`),
  `phase3a_unified_reconstruct.py` (`MIN_VALID_CURRENT_UA`, `FIRMWARE_MIN_CURRENT_UA`),
  every `Q,OK` stamp in every capture taken before 2026-09-02, and any thesis claim that
  `Q,OK` certifies a real measurement
- **Related:** [ADR-0011](0011-current-guard-derives-from-fitted-rs.md) (same session, the
  other end of the same guard), `docs/planned-improvements.md` 1.3 (offset domination),
  `docs/validity-audit.md`

## Context

During the 2026-09-02 bench session the operator captured a frame with the OPA2134 supply
disconnected - battery off, no rails on the current source. No injected current is physically
possible in that state. The firmware nevertheless produced this, among 20 measurements:

```text
M,P,REV,I+,E12,I-,E11,V+,E9,V-,E10,V,5.062,I,2.554,Q,OK
M,P,REV,I+,E1,I-,E12,V+,E2,V-,E3,V,292.875,I,1.277,Q,OK
M,P,REV,I+,E1,I-,E12,V+,E7,V-,E8,V,185.812,I,2.234,Q,OK
```

**Ten of the twenty measurements in an unpowered frame were stamped `Q,OK`.** The shunt-channel
readings spanned 0.000 to 2.554 uA against a `MIN_CURRENT_UA` of 1.0 uA, so more than half the
pure-noise readings cleared the floor and were certified valid.

The readings are quantised in steps of 0.319 uA, which is 31.2 uV across the 97.9 ohm shunt, or
exactly 4 LSB of the ADS1115 on `GAIN_SIXTEEN`. This is the ADC's own noise at 860 SPS, not a
signal. The accompanying voltages - 185 mV to 443 mV on pairs with no current flowing - are
electrode half-cell potentials, the direct confirmation of the offset domination recorded in
`planned-improvements.md` 1.3.

The host was worse than the firmware: `MIN_VALID_CURRENT_UA` was 0.5 uA, half the firmware
floor, so `is_usable_record()` would have accepted readings the firmware had already judged
marginal.

This is a different defect from ADR-0011 and points the opposite way. ADR-0011 concerns a
ceiling that was too high to catch an over-current; this concerns a floor that was too low to
catch *no current at all*. Together they meant the quality flag constrained nothing at either
end.

## Decision

`MIN_CURRENT_UA` becomes 10.0 uA in firmware, and the host's `MIN_VALID_CURRENT_UA` and
`FIRMWARE_MIN_CURRENT_UA` both become 10.0 uA to match. The value is derived from the measured
null-frame noise peak of 2.554 uA with roughly 4x margin, and is documented in both sources as
a measured figure rather than a nominal one.

## Rationale

A floor below the noise floor is not a check. The specific failure it permits is the worst kind
for this instrument: `paired_transfer_resistance()` normalises each measurement by its own
measured current, so a noise-level current in the denominator produces an arbitrarily large
transfer resistance that then propagates into a reconstruction image as apparent structure. A
`Q,OK` frame captured on a disconnected current source would reconstruct into something that
looks like data.

10.0 uA is 4x the observed noise peak and 1 percent of the design's 1.0 mA maximum on HIGH, so
it discriminates against noise without excluding a legitimately weak measurement on a
high-impedance load. It is a judgement call anchored to one 20-measurement null frame, which is
a small sample - see Verification.

Host and firmware are set to the same number deliberately. The previous split (0.5 host, 1.0
firmware) meant the host silently trusted a band the firmware would have flagged, which makes
`filter_frame_vector_best_effort` behave differently from strict capture for reasons unrelated
to measurement quality.

Alternatives considered:

- **Keep 1.0 uA and rely on the operator noticing.** Rejected: the operator did notice, but
  only because the battery was off and the result was obviously impossible. On a live rig with
  one poorly contacting electrode the same noise-level reading is indistinguishable from a real
  weak measurement, and it would be certified.
- **Derive the floor from the ADC LSB arithmetically.** Rejected as insufficient: the measured
  noise is 4 LSB, not 1, and includes shunt thermal noise and pickup the arithmetic does not
  model. The measurement is the better authority.
- **Reject on voltage rather than current.** Rejected: the null frame shows 185-443 mV of
  half-cell offset on pairs carrying no current at all, so voltage magnitude is not evidence
  that a measurement happened.
- **Make the floor a runtime-tunable serial parameter.** Rejected for now. It is a property of
  the ADC and shunt, not of the experiment, and making it adjustable invites lowering it to make
  a bad capture pass.

## Consequences

**Every capture in `phase3a_logs/` predating this change has `Q,OK` measurements that may be
noise.** The flag did not mean what the thesis will want it to mean. Any run whose minimum
current sat between 1 and 10 uA needs re-examination before it is cited, and `margin_ratio`
values computed against the old 1.0 uA floor overstate health by 10x.

More captures will now fail. `validate_record()` raises on any non-`OK` quality, so a frame with
one weak pair aborts the whole capture (`planned-improvements.md` 1.4). Combined with ADR-0011's
tighter ceiling, the usable drive window is now genuinely narrow - which is an honest
description of the instrument, not a regression to tune away.

The 10.0 uA figure rests on a single unpowered frame. It is provisional and should be replaced
by a characterised value once a proper null run exists.

Two test fixtures used 4.0 uA as a healthy current and were updated to 40.0 uA. That they
existed at all shows the old floor had shaped the project's idea of a normal reading.

## Verification

`tests/test_phase3a_unified_firmware.py` asserts the firmware constant, and the host thresholds
are exercised through `is_usable_record` / `validate_record` in
`tests/test_phase3a_unified_reconstruct.py`. Firmware coverage is text assertion only, per
[ADR-0005](0005-firmware-tests-stay-text-assertions.md).

The bench check that falsifies or confirms this: **repeat the null frame.** Disconnect the
OPA2134 supply, capture one frame, and confirm every measurement now reports `I_LOW` and zero
`Q,OK`. That test was what exposed the defect and it should become a standing item in
`docs/current-setup-validation-runbook.md` before each capture session. If a properly
characterised null run (several frames, both polarities, all 12 electrodes) shows a noise peak
above 2.5 uA, the 10.0 uA floor is too tight a margin and must be raised, not the reverse.

**Confirmed on hardware 2026-09-02.** A null frame captured after flashing, with the OPA2134
supply disconnected and a 2.2 kohm dummy load across E1-E2, returned 18 measurements of which
**zero were `Q,OK`** - every one reported `I_LOW`, as required. Under the previous 1.0 uA floor
7 of those same 18 readings would have been certified valid.

That frame also re-measured the noise floor: readings spanned -2.234 to +2.873 uA, a peak of
2.873 uA against the 2.554 uA seen in the frame that motivated this ADR. The 10.0 uA floor is
therefore a **3.5x** margin over measured noise, not the 4x stated in the Rationale. That is
still adequate, but it is thinner than intended and it moves in the wrong direction as more
null frames are collected. Treat 10.0 uA as a floor to raise if further nulls exceed 2.9 uA,
never one to lower. Note also that the noise changed sign between the two frames (predominantly
positive in the first, predominantly negative in the second), which is the expected behaviour
of a zero-mean noise process and further evidence these readings carry no signal.
