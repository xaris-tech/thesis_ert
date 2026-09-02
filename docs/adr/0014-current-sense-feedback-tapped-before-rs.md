# ADR-0014: The current-sense feedback is tapped before Rs, so the rig has never been a current source

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** the OPA2134 current source, every capture in `phase3a_logs/` including the
  2026-09-01 reference runs, `docs/planned-improvements.md` 1.1, ADR-0008 and ADR-0010's
  reciprocity findings, and the thesis claim that the instrument injects a controlled current
- **Related:** supersedes [ADR-0013](0013-repair-howland-ratio-match.md);
  [ADR-0011](0011-current-guard-derives-from-fitted-rs.md),
  [ADR-0012](0012-current-floor-from-measured-noise.md),
  [ADR-0008](0008-reciprocity-metric-must-not-saturate.md),
  [ADR-0010](0010-reciprocity-error-scales-with-signal.md)

> **Numbers corrected 2026-09-02.** The Decision below is unchanged and confirmed. Two figures
> in the supporting analysis were wrong: R1 was re-measured at **4980 ohm**, not 4498, so the
> leg mismatch is **+0.208 percent**, not 10.7 percent, and **no resistor rework is needed**.
> The "not demonstrably sufficient" hedge in Consequences is also withdrawn - the open-air
> `I_SAT` is fully explained by the latched amplifier forward-biasing the CD4067 protection
> diodes, with no second fault required. Full chain of evidence in
> [`docs/i-sat-investigation-2026-09-02.md`](../i-sat-investigation-2026-09-02.md).

## Context

`docs/first-working-prototype/03-howland-current-source.md` specifies that OPA2134 pin 5, the
non-inverting input of the buffer amplifier B, senses `I_SRC_OUT` - the junction **after** Rs.
That is the entire current-sensing mechanism of the Improved Howland topology: the loop
regulates by measuring the drop across Rs.

Measured 2026-09-02 with the board unpowered:

```text
pin 5 -> pin 1        =  0 ohm     (should be 10 ohm, through Rs)
pin 5 -> I_SRC_OUT    = 10 ohm     (should be 0 ohm)
```

**Pin 5 is tied to pin 1, the node before Rs.** There is no voltage difference across the
sense element in the feedback path, so the loop has never sensed current at all.

This was missed by earlier continuity checks because Rs is 10 ohm, below any continuity
beeper's threshold - the test beeps identically whichever side of Rs pin 5 sits on. It requires
resistance mode and reading the actual number.

### What the circuit actually is

With pin 5 on pin 1, the loop solves to a **voltage** source:

```text
V_out = gA * fwd / (1 - gA * fb) * VDAC        gA = 1 + R2/R1 = 1.021787
                                                fb = R3/(R3+R4) = 0.980697
                                                gA * fb = 1.002063
```

Output impedance is then just the series resistance of the path - `Rs` plus two mux `Ron` -
with no active regulation.

This retrodicts the 2026-08-27 dummy-load sweep in `planned-improvements.md` 1.1 exactly.
That sweep found `Rout + Ron(mux) ~= 430 ohm` and `Vth ~= 0.38 V`, with current tracking
`1/R_load`. 430 ohm is simply `Rs` plus two CD4067 channels; there is no mystery output
impedance to explain. 1.1 attributed the behaviour to "leg mismatch in the Improved Howland
network" with `e` around 2-3 percent. **That diagnosis is wrong.** The measured leg mismatch is
10.7 percent (ADR-0013), which would give `Rout` around 94 ohm, not 430; and the mismatch is
not what makes the pump a voltage source. The miswired sense tap is.

### Why 2026-09-01 worked and 2026-09-02 did not

The 2026-09-01 reference run (`phase3a-v2-adjacent-20260901-180216.csv`, DAC code 100) recorded
3672 measurements, all `Q,OK`, median 635.2 uA, min 521.3, max 829.6. Real, varying, plainly
not noise and not the ADC rail.

The voltage-source model reproduces it:

```text
loop = 0.998  ->  V_out = 9.86 * VDAC = 0.789 V at DAC 100
                  into a ~1250 ohm path -> 631 uA        (measured median 635.2 uA)
```

The decisive detail is that `gA * fb` computes to **1.002063**, which is only **+0.206 percent**
from the stability boundary at 1.0. That margin is finer than a DMM can resolve on these
resistors: at +/-0.5 percent on each 5k part the plausible range straddles unity. The circuit
therefore sits *on* the boundary, and which side it falls on is set by temperature, supply,
load, and measurement error rather than by design.

Below unity it is a stable voltage source and produces the usable-looking 2026-09-01 data.
Above unity the loop runs away, the output goes to whatever limits it, and the reading becomes
independent of the DAC code - which is what 2026-09-02 showed when dropping the code from 100
to 7 changed the current by not one LSB.

So the honest answer to "why did it work yesterday" is that it never worked as designed. It
worked as a marginally-stable voltage source, and then stopped being stable.

## Decision

Pin 5 is moved from pin 1 to `I_SRC_OUT`, the far side of Rs, restoring the current-sense
feedback the topology requires. ADR-0013's diagnosis - that the ratio mismatch is the primary
fault and the fix is matched resistors - is superseded.

## Rationale

This is a single wire and it is the actual root cause. Every downstream symptom follows from
it: the voltage-source behaviour of 1.1, the latch-ups of 2026-09-02, the insensitivity to DAC
code, the electrode nodes driven past the 3.3 V mux rail, and the `V,0.000` that clamping
produced.

It also removes the marginal-stability problem rather than merely moving along it. With the
sense tap correct, the loop gain is no longer a difference of two near-equal quantities sitting
0.2 percent from unity, so the circuit stops being a coin flip between working and running away.

The 10.7 percent ratio mismatch documented in ADR-0013 is real and remains an accuracy
limitation - it sets `Rout` around 94 ohm once the loop is correct, and a pole at 4846 ohm above
which the corrected loop would still latch. But it is second order, and at the measured tree
impedance of 1-1.5 kohm nail-to-nail (roughly 1950 ohm total path) the corrected circuit is
predicted to deliver about 260 uA at DAC 100, which is usable. Matched resistors remain
desirable and are no longer urgent.

Alternatives considered:

- **Fix the resistors first, per ADR-0013.** Rejected: it treats a secondary effect, requires
  rework the operator has said is not available, and would leave the sense tap defeated - the
  pump would remain a voltage source with better-matched legs.
- **Leave the tap and characterise the rig as a voltage source.** Rejected. It is defensible as
  physics - `paired_transfer_resistance()` normalises by each measurement's own current, which
  is why 2026-09-01 produced usable numbers - but it means the injected current depends on the
  pair being driven, which is precisely the condition that corrupts reciprocity, and it leaves
  the instrument sitting on a stability boundary it can fall off between sessions.

## Consequences

**Every capture in `phase3a_logs/` was taken with a voltage source, not a current source.** The
2026-09-01 runs cited as evidence in ADR-0008, ADR-0009 and ADR-0010 are included. Their current
readings are genuine measurements of what flowed, and difference imaging normalised by measured
current is not automatically invalid - but any statement that the instrument injected a
controlled or constant current is false and must be withdrawn from the thesis.

ADR-0010's finding that reciprocity error scales with signal amplitude needs re-examination
against this. A source with roughly 430 ohm output impedance delivers a current that depends on
the impedance of each drive pair, which is a mechanism for exactly the amplitude-dependent
reciprocity error that ADR was written to describe. That ADR's observation stands; its
interpretation may not.

`planned-improvements.md` 1.1's causal claim is withdrawn. Its *measurements* were correct and
are in fact the strongest retrospective evidence for this ADR - it is the diagnosis layered on
top that was wrong, which is a caution about inferring component-level causes from
terminal-level behaviour.

After the repair the rig becomes a different instrument, and the baselines, drift figures and
reciprocity statistics collected before it do not carry over.

## Verification

After moving the wire, unpowered:

```text
pin 5 -> I_SRC_OUT    must read  0 ohm
pin 5 -> pin 1        must read 10 ohm
```

Then the dummy-load sweep of `docs/current-setup-validation-runbook.md` section 4 at 500, 1000
and 2000 ohm, at a fixed DAC code. **The pass condition is that the measured current is
substantially the same at all three loads.** Before this repair it tracked `1/R_load`; a
current source does not. Predicted currents with the present resistors are 176 / 199 / 269 uA
at DAC code 100 - a 53 percent spread that quantifies the residual ratio mismatch and is the
measurement that decides whether ADR-0013's resistor work is worth doing after all.

Also confirm the current now responds proportionally to DAC code, and that `I_SRC_OUT` stays
below 3.3 V so the mux protection diodes never conduct.

**Performed and passed, 2026-09-02.** The wire was moved from pin 1 to `I_SRC_OUT` and the
instrument was re-measured on the tree at four DAC codes:

| DAC code | Median current |
|---:|---:|
| 0 | 216.4 µA |
| 100 | 361.3 µA |
| 200 | 517.7 µA |
| 400 | 826.6 µA |

```text
fit:    I = 1.531 uA/code x code + 213 uA
design: VDAC * 0.02 / Rs = 1.580 uA/code
slope error: -3.1 percent, every point within 4.4 uA of the fit
```

The current now tracks the command linearly at very close to the designed transconductance.
Before the repair the identical sweep produced no change at all — DAC 100, 7 and 0 all returned
the same railed value. `Q,I_SAT` is gone.

Forward and reverse voltages also invert for the first time (`E2-E3` at DAC 200 reads
`FWD +124.031 mV / REV -158.437 mV`) and scale with drive current, which is an IR drop rather
than the static half-cell offset recorded in `planned-improvements.md` 1.3.

Two caveats on this verification. The dummy-load sweep of section 7.3 has **not** been run, so
output impedance is still unquantified and the "flat across loads" pass condition is untested —
the evidence above shows the loop closes and the transconductance is right, not that `Rout` is
adequate. And a **213 µA offset at zero command** remains open; see
[`docs/i-sat-investigation-2026-09-02.md`](../i-sat-investigation-2026-09-02.md) section 10.4.

One prediction in this ADR was wrong and is corrected for the record: pin 1 measuring 3.9 V at
idle was given as a sign the repair had failed. It is not. `enterSafeIdle()` disables the
muxes, presenting an open load far above the latch pole, so the amplifier latches at idle by
design and regulates as soon as a load is present.
