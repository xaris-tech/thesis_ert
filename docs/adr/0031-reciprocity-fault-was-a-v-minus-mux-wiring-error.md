# ADR-0031: The reciprocity fault was a V- mux address wiring error; pre-fix data is compromised

- **Status:** Accepted
- **Date:** 2026-09-22
- **Affects:** hardware (MUX_VN address wiring), interpretation of every capture before 2026-09-22 14:30, thesis claims resting on those captures
- **Related:** ADR-0017, ADR-0018, ADR-0019, ADR-0021, ADR-0022, ADR-0030

## Context

Reciprocity had failed on every specimen since measurement began: 57.5 % median on the trunk
(ADR-0017), 73–95 % in the saline tank (2026-09-16 to 2026-09-22). ADR-0017 and ADR-0018 eliminated a
series of hypotheses, and ADR-0021 adopted the saline tank to bisect specimen-side from instrument-side.

On 2026-09-22 two measurements isolated the fault:

1. **Diluted saline** (`20260922-120025-purified-saline`) raised the signal 20× (0.27 → 5.4 mV) and cut
   offset/signal from 67× to 3.2×, but reciprocity only fell from 95 % to 75 %. Offset and polarisation were
   not the main cause.
2. **Resistor ring**, 12 × 220 Ω between neighbouring electrode leads, adjacent drive, expected transfer
   resistance R/12 = 18.33 Ω for every measurement (`20260922-133221-resistor-circle`). Offset 0.02 mV,
   noise 0.14 %, yet reciprocity 66.5 % median, 25/54 sign flips. Exactly 54 of 108 values were 18.3 Ω.
   The measured/expected ratio was constant down each **sense** column regardless of drive, and wrong only
   for pairs whose V- electrode was E3, E4, E5, E6, E11 or E12 (channels C2, C3, C4, C5, C10, C11).

Those six channels are exactly the channels whose S1 and S2 address bits differ. On inspection, the
MUX_VN module's S1 pin was wired to both GPIO35 (S1) and GPIO41 (S2), and its S2 pin was unconnected.
The chip therefore saw S2 = S1, and every V- measurement on those six channels sensed a different
electrode from the one addressed.

## Decision

The wiring is corrected: GPIO35 → MUX_VN S1, GPIO41 → MUX_VN S2, per
`docs/first-working-prototype/04-complete-pinout-and-wiring.md`. The reciprocity fault is recorded as
this instrument-side wiring error, **not** a property of the specimen, the electrodes or the analog front
end. Every capture taken before the fix is treated as compromised for any use beyond what is stated below.

## Rationale

- **The fix is verified, not assumed.** The same ring after the fix (`20260922-143652-resistor-circle`):
  reciprocity median 0.1 %, max 0.3 %, 0/54 sign flips, all 108 transfer resistances 17.7–18.8 Ω against
  18.33 Ω expected (spread consistent with 1 % resistor tolerance), 2160/2160 records OK, current
  469–497 µA.
- **The fault accounts for the whole failure mode.** Half the measurement set read the wrong electrode,
  deterministically, which is exactly what broken reciprocity with low noise looks like. It also explains
  why the E6/E7 wood target did not localise (ADR-0027's falsification condition) and why no image
  separated from its control.
- **Why "compromised" rather than "invalid for the six channels only":** the wrong readings enter the
  difference vector and the solver's global scaling term, so every image mixes them in. Correcting old
  data would require knowing, per record, which electrode was actually sensed. That mapping depends on
  a floating input and is not reliably recoverable.
- **Rejected: re-mapping historic records in software.** The ring data did not fit any fixed channel
  mapping (swap, stuck-at, permutation all tested), consistent with S2 being floating and GPIO35/41
  in contention. A recovered dataset could not be shown to be correct.

## Consequences

- **All captures before 2026-09-22 14:30** (the `phase3a_logs/` series and `scans/` runs up to and
  including `20260922-133221-resistor-circle`) have ~half of their measurements from the wrong electrode.
  Their reconstruction images, reciprocity figures and noise floors must not be cited as properties of
  the instrument or the specimen. Frame-to-frame noise figures are still honest as repeatability of a
  *wrong* measurement.
- ADR-0017/0018's eliminated hypotheses were tested against this fault. Their eliminations remain
  plausible but are **not** established; revisit any that a thesis claim relies on.
- The reciprocity gate (ADR-0030) should now pass on a sound specimen. If a real medium still fails it,
  the cause lies at the electrode/medium, measured against a verified instrument.
- The saline tank and trunk results need re-capturing before any imaging claim is made.
- The `conditions.json` of the ring runs records `medium: saline tank`, because the operator did not
  change the field (ADR-0023 limitation). The run ids named here are the authoritative identification.
- GPIO35 and GPIO41 were in output contention for an unknown period. The post-fix ring pass shows both
  now drive correctly.

## Verification

- Re-run the resistor ring (12 × 220 Ω, adjacent, same settings): pass = reciprocity median < 5 %, all
  transfer resistances within ~5 % of 18.33 Ω. Measured 2026-09-22: 0.1 % / 108 of 108.
- Continuity check: GPIO35 ↔ MUX_VN S1 and GPIO41 ↔ MUX_VN S2 beep; GPIO35 ↔ S2 and GPIO41 ↔ S1 do not.
- **Not verified:** the other three muxes' address wiring beyond what the ring exercises (the ring tests
  all four muxes on all 12 channels, so a similar fault elsewhere would have shown), and the saline tank
  and trunk after the fix.
