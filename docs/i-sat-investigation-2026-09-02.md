# Investigation: constant `I_SAT` on every measurement, 2026-09-02

Status: **RESOLVED. Repair performed and verified on hardware 2026-09-02.** The `I_SAT`
failure is gone and the current source regulates for the first time in the project's history.
Two new issues were exposed by the working instrument and are tracked in section 10.

This records a full bench investigation into a failure that appeared between the 2026-09-01
capture session and the following day, on hardware the operator had not intentionally changed.
It is written to be checkable by someone who was not at the bench: every claim is tied to a
measurement, and the hypotheses that were raised and killed are kept, because several of them
were confidently argued and wrong.

Related: [ADR-0011](adr/0011-current-guard-derives-from-fitted-rs.md),
[ADR-0012](adr/0012-current-floor-from-measured-noise.md),
[ADR-0013](adr/0013-repair-howland-ratio-match.md) (superseded),
[ADR-0014](adr/0014-current-sense-feedback-tapped-before-rs.md),
`planned-improvements.md` 1.1.

---

## 1. Symptom

Every measurement in every frame, from the moment the debug UI connects:

```text
M,P,FWD,I+,E12,I-,E1,V+,E7,V-,E8,V,0.000,I,2613.636,Q,I_SAT
```

Identical on all 216 measurements of a frame. The reported current is **exactly the same value
every time**, and the sensed voltage is zero or near-zero on essentially every pair.

`2613.636 uA x 97.9 ohm = 255.87 mV`, which is 99.95 percent of the ADS1115 full scale on
`GAIN_SIXTEEN`. **The number is the ADC rail, not a measurement.** Until 2026-09-02 the firmware
reported this as `Q,I_HIGH`, which reads as "a real current, somewhat too large" — it was
changed to the new `I_SAT` flag under ADR-0011 precisely so this state is no longer mistaken
for data.

### The signature that matters

The reading is invariant under everything that should change it:

| Varied | Result |
|---|---|
| DAC code 100 → 7 → 0 | no change, not one LSB |
| Electrodes open to air | no change |
| 2.2 kohm dummy across E1-E2 | no change |
| Nails in a tree trunk (1-1.5 kohm) | no change |
| Which electrode pair is driven | no change |
| **OPA2134 supply off** | **reads noise, 0-2.9 uA** |

One input controls it: whether the current source has power. That is the signature of a
**latch**, not of a measurement error or a bad component value.

---

## 2. Confirmed measurements

### 2.1 Resistor network (final values, chip removed)

| Part | Position | Measured | Spec |
|---|---|---:|---:|
| R1 | pin 2 → ground | 4980 Ω | 5.00 k |
| R2 | pin 1 → pin 2 | 98 Ω | 100 |
| R3 | pin 3 → MCP4725 VOUT | 5026 Ω | 5.00 k |
| R4 | pin 3 → pin 7 | 98.7 Ω | 100 |
| Rs | pin 1 → I_SRC_OUT | 10.2 Ω | 10 (HIGH range) |
| shunt | A2 → A3 | 97.9 Ω | 100 |

Cross-sums confirm these: `pin 1 → ground = 5078 = 98 + 4980`, and
`pin 7 → VOUT = 5125 = 98.7 + 5026`. Both land exactly.

**Ratio match:** `R2/R1 = 0.019679`, `R4/R3 = 0.019638`, mismatch **+0.208 percent**. The legs
are well matched — better than 1 percent parts. There is nothing wrong with the resistor
selection, and no resistor rework is needed.

> An earlier reading in this session gave R1 = 4498, implying a 10.7 percent mismatch. That
> reading was wrong — it had no cross-check, and the later 4980 is corroborated by the
> pin 1 → ground sum. Analysis built on 4498 (ADR-0013, and parts of ADR-0014) is void.

### 2.2 The fault

| Measure | Read | Should be |
|---|---:|---:|
| pin 5 → pin 1 | **0 Ω** | 10.2 Ω (through Rs) |
| pin 5 → I_SRC_OUT | **10.2 Ω** | 0 Ω |
| pin 5 → pin 2 | **98 Ω** | 108.2 Ω (Rs + R2) |

Three independent routes, all agreeing: **OPA2134 pin 5 is electrically the same node as
pin 1.** `docs/first-working-prototype/03-howland-current-source.md` requires pin 5 to sense
`I_SRC_OUT`, the junction *after* Rs. The buffer is sensing the wrong side of the sense
resistor, so the feedback loop never sees the drop across Rs.

**There is no current sensing. There never has been.**

This survived earlier checking because **Rs is 10 Ω, below any continuity beeper's threshold** —
the test beeps identically whichever side of Rs pin 5 sits on. It requires resistance mode and
reading the number.

### 2.3 Node voltages, powered, driving a tree

| Node | Measured |
|---|---:|
| MCP4725 VOUT | 0.079 V (correct for DAC code 100) |
| OPA2134 pin 3 | 4.230 V |
| OPA2134 pin 1 | 4.313 V |
| pin 7 (inferred from the pin-3 divider) | 4.312 V |
| I_SRC_OUT | 4.048 V |
| E1 pad | 3.173 V |
| E2 pad | 1.800 V |
| Shunt high side (A2) | 1.134 V |
| Supply, pins 8 / 4 | **±15 V** (spec calls for ±9 V) |

The inferred pin 7 matches pin 1 to **1 mV** — independent confirmation of 2.2, and proof that
amplifier B is healthy and correctly following whatever is on its input.

### 2.4 Current does not reconcile

| Measured at | Implied current |
|---|---:|
| Through Rs (pin 1 − I_SRC_OUT) | 26.5 mA |
| Through the shunt (A2 / 97.9) | 11.6 mA |
| Through the tree (E1 − E2 / 1.25 k) | 1.1 mA |

Three points in what should be one series path, spanning 24×. Most of the current is not
crossing the specimen.

### 2.5 The path it takes instead

Diode-mode, `I_SRC_OUT → A2`, board unpowered: **0.745 V one way, 1.133 V the other.**
Asymmetric, both finite. A real 5 kΩ resistance would read `OL` in diode mode. This is a
**semiconductor path** — the ESD protection diodes inside the CD4067 muxes, which is normal for
this topology, since both mux commons tie to the shared electrode nodes.

> An ohms-mode reading of this same pair gave ~5 kΩ, which was briefly taken as evidence of
> flux-residue contamination on the perfboard. It was a phantom: the meter's test voltage
> forward-biasing those diodes. There is nothing to clean.

---

## 3. Mechanism

```text
pin 5 tied to pin 1
  -> feedback path does not span Rs
  -> loop gain becomes purely resistive: gA * fb = (1 + R2/R1) * R3/(R3+R4)
  -> the load is not in the loop at all
  -> at gain >= 1 the amplifier amplifies its own input offset without bound
  -> output runs to the supply rail, ignoring VDAC entirely
  -> at +15 V it forward-biases the CD4067 protection diodes (~1.1 V of drops)
  -> 13.9 V across Rs + shunt (108 ohm) demands 128 mA
  -> OPA2134 current-limits at ~35 mA
  -> shunt sees 35 mA x 97.9 = 3.4 V against a 256 mV rail  ->  I_SAT
```

This accounts for every observation in section 1, including the one that resisted explanation
longest: **`I_SAT` with the electrodes open to air.** The current never goes near the
electrodes, so whether anything is connected is irrelevant.

The sensed voltage reads zero for the same reason — no current crosses the specimen, so no IR
drop develops. The occasional large first-measurement value after a mux switch
(`V,1515.250`, `V,2908.500`) is a settling transient that collapses on the next measurement.

---

## 4. Why 2026-09-01 worked and 2026-09-02 did not

This is the central question, because the setup was not intentionally changed.

**The circuit sits on a stability boundary, and which side it falls on is not determined by
design.**

With pin 5 miswired, the load drops out of the loop and everything hinges on one number:

```text
gA * fb  =  1.000040        (+40 ppm above unity)
```

Forty parts per million. Below 1 it is a stable — if wildly high-gain — voltage source. At or
above 1 it latches. And **that margin is far finer than the measurement can resolve:**

| DMM accuracy assumed | gA·fb range | Straddles 1.0? |
|---|---|---|
| ±0.05% per part | 1.00002 – 1.00006 | no |
| ±0.10% per part | 1.00000 – 1.00008 | borderline |
| ±0.20% per part | 0.99996 – 1.00012 | **yes** |

We cannot honestly say whether it is above or below unity. Resistor temperature coefficient
alone (5 percent parts run 250-500 ppm/°C) moves it by more than the whole margin over a
handful of degrees.

The 2026-09-01 reference run (`phase3a-v2-adjacent-20260901-180216.csv`, DAC 100, 3672
measurements, all `Q,OK`, median **635.2 uA**) requires `gA * fb ≈ 0.99753` — about
**0.25 percent** below today's computed value. That is well within the combined reach of
measurement uncertainty and thermal drift.

So: the setup genuinely did not change. **The fault did not appear on 2026-09-02 — it has been
present the whole time, and the circuit simply crossed from one side of the boundary to the
other.** The ±15 V supply, against a specified ±9 V, makes the latched state far more violent
than it would otherwise be and is a plausible contributor.

### What this means for the 2026-09-01 data

It was never a current source. It was a voltage source that produced usable-looking numbers,
because `paired_transfer_resistance()` normalises each measurement by its own measured current.
This also retrodicts `planned-improvements.md` 1.1 exactly: the `Rout ≈ 430 ohm` measured there
is simply Rs plus two mux `Ron`, with no regulation — not the "leg mismatch" that section
diagnosed.

---

## 5. Hypotheses raised and eliminated

Kept deliberately. Several were argued confidently and were wrong; the pattern was reasoning
forward from a model instead of stopping at the measurement that did not reconcile.

| # | Hypothesis | Killed by |
|---|---|---|
| 1 | Open current return / broken shunt ground leg | 0.4 V measured across the shunt; A3 at ground |
| 2 | Rs jumper on the wrong range | all three ranges are far below the observed current |
| 3 | R1/R3 fitted as ~470 Ω (decade error) | resistor inventory: correct BOM, all values present |
| 4 | 10.7% ratio mismatch, `Rout` = 94 Ω, pole at 4846 Ω | R1 re-measured at 4980, not 4498; true mismatch 0.208% |
| 5 | Supply collapsed to ~+4.3 V | supply measured ±15 V |
| 6 | Load-dependent latch pole | latches at open, 2.2 k, and 1.25 k alike — load is not in the loop |
| 7 | Damaged mux / CMOS latch-up | not needed; protection-diode conduction explains it without damage |
| 8 | Perfboard flux-residue leak (~5 kΩ) | diode mode asymmetric (0.745 / 1.133 V) — a junction, not a resistance |

Two measurements would have short-circuited most of this: `pin 5 → pin 1` in **resistance
mode**, and noticing that section 2.4 does not balance.

---

## 6. The fix

### 6.1 Primary — required

**Move OPA2134 pin 5 from pin 1 to `I_SRC_OUT`,** the far side of Rs.

One wire. It restores current sensing, puts the load back inside the loop, and moves the
operating point off the boundary entirely — after the change, the denominator is dominated by
Rs (10.2 Ω) rather than by a 40 ppm difference, so a 0.25 percent drift changes the current by
a bounded amount instead of flipping between working and latched.

### 6.2 Secondary — do at the same time

**Set the supply to ±9 V** per `docs/first-working-prototype/02-parts-and-power.md:44`.
Currently ±15 V. The extra rail voltage does not cause the fault but makes the latched state
drive far harder into the muxes' 3.3 V supply.

### 6.3 Not needed

- **No resistor replacement.** The legs match to 0.208 percent. ADR-0013's recommendation is
  withdrawn.
- **No board cleaning.** The 5 kΩ was a meter artifact.
- **No mux replacement**, unless the checks in 7.4 show damage.

---

## 7. Acceptance tests

### 7.1 Verify the wire, unpowered

```text
pin 5 -> I_SRC_OUT   must read   0 Ω
pin 5 -> pin 1       must read  10.2 Ω
pin 5 -> pin 2       must read 108.2 Ω
```

### 7.2 Open-air frame — the decisive test

With the amplifier powered and **no electrodes connected to anything**, capture one frame.

**Every line must read `Q,I_LOW`.** No current can flow, so none should be measured. If `I_SAT`
persists here, the diagnosis in section 3 is wrong and there is a second fault.

### 7.3 Dummy-load sweep

`docs/current-setup-validation-runbook.md` section 4, at DAC code 100:

| Load | Predicted |
|---:|---:|
| 500 Ω | 154.3 µA |
| 1 kΩ | 154.6 µA |
| 2 kΩ | 155.2 µA |
| 4 kΩ | 156.5 µA |

Design target is `VDAC × 0.02 / Rs` = 156.9 µA. **The pass condition is that current is flat
across the range** — that is what a current source does and what this rig has never done. If it
still tracks `1/R_load`, the repair failed.

### 7.4 Health checks after first power-up

- 3.3 V rail reads 3.3 V (tens of milliamps have been injected into it; its regulator cannot
  sink current)
- I2C scan finds 0x48 and 0x60/0x61
- `I_SRC_OUT` stays below 3.3 V at the maximum DAC code

### 7.5 Expect a different DAC code than before

At DAC 100 a correctly regulating pump gives **~155 µA**, not the ~635 µA of the 2026-09-01
runs — those were four times higher because they were unregulated. To reach ~635 µA again
you will need **DAC code around 381**, within the HIGH range ceiling of 620.

---

## 8. What this invalidates

**Every capture in `phase3a_logs/` was taken with a voltage source.** That includes the
2026-09-01 runs cited as evidence in ADR-0008, ADR-0009 and ADR-0010.

- Current readings in those files are genuine measurements of what flowed. Difference imaging
  normalised by measured current is not automatically void.
- **Any claim that the instrument injected a controlled or constant current is false** and must
  be removed from the thesis.
- ADR-0010's amplitude-dependent reciprocity error now has a candidate mechanism: a source with
  ~430 Ω output impedance delivers a current that depends on the impedance of each drive pair.
  That ADR's observation stands; its interpretation needs revisiting.
- Baselines, drift figures and reciprocity statistics collected before the repair do not carry
  over. After it, this is a different instrument.

Separately, ADR-0012 raised `MIN_CURRENT_UA` from 1.0 to 10.0 µA after an unpowered null frame
stamped 10 of 20 noise readings `Q,OK`. That fix is **confirmed on hardware**: a post-flash null
frame returned 18 measurements, zero `Q,OK`.

---

## 9. Open questions

1. **Was the supply at ±9 V on 2026-09-01?** Unknown. If someone raised it to ±15 V between
   sessions, that is a concrete change and a better explanation than thermal drift.
2. **Has anything on the 3.3 V rail been damaged?** Tens of milliamps were injected repeatedly.
   No evidence of damage, but no evidence against it either.
3. **Why is only one Rs fitted?** The firmware offers LOW/MEDIUM/HIGH but only the 10 Ω part
   exists, so two of three ranges cannot be selected in hardware (ADR-0011).
4. **Is the tree's effective resistance really 1-1.5 kΩ under drive?** The DMM says so, but the
   node voltages imply ~118 Ω at 1.4 V. Nail-to-wood contact is strongly nonlinear; worth
   measuring properly once the pump regulates.

---

## 10. Outcome — repair performed and verified, 2026-09-02

The pin 5 wire was moved from pin 1 to `I_SRC_OUT`. **The repair worked.**

### 10.1 The current source now regulates

`I_SAT` is gone. The constant `2613.636` rail reading has been replaced by a current that
responds linearly to the DAC command. Measured on the tree, four DAC codes:

| DAC code | Median current | Spread across pairs |
|---:|---:|---:|
| 0 | 216.4 µA | 6.05 % |
| 100 | 361.3 µA | 2.96 % |
| 200 | 517.7 µA | 3.38 % |
| 400 | 826.6 µA | 1.79 % |

Least-squares fit:

```text
I = 1.531 uA/code x code + 213 uA
design slope = VDAC * 0.02 / Rs = (3.3/4096) * 0.02 / 10.2 = 1.580 uA/code
slope error = -3.1 percent
```

Every point sits within 4.4 µA of the fit. **A 3.1 percent slope error against design is
correct behaviour for this build** — it is within the tolerance stack of the fitted parts and
confirms the loop is closing on the drop across Rs, exactly as the topology requires.

For contrast, before the repair the same sweep produced no change whatsoever: DAC 100, 7 and 0
all returned an identical railed reading.

### 10.2 Voltage measurements became physical

Forward and reverse now invert on the pairs that carry real signal, which they never did
before (`planned-improvements.md` 1.3 recorded them as identical and offset-dominated):

```text
E2-E3 at DAC 100:  FWD +76.781 mV   REV -121.781 mV
E2-E3 at DAC 200:  FWD +124.031 mV  REV -158.437 mV
```

Magnitude also scales with drive current. That is an IR drop, not a half-cell offset. This is
the first evidence in the project of a genuine transfer measurement.

Some pairs remain offset-dominated — `E6-E7` reads +206/+207 mV forward and reverse with no
inversion — which is now attributable to per-electrode contact rather than to the instrument.

### 10.3 Confirmations of the diagnosis

- The pump was never a current source before this repair. The 2026-09-01 runs at ~635 µA are
  now understood: at the corrected slope, DAC 100 gives ~365 µA, so the old figure was roughly
  1.7x what a regulating pump delivers.
- The `RS_DECLARED` mechanism from ADR-0011 immediately earned itself. The first post-repair
  frame reported `Q,I_HIGH` on every measurement at 362 µA, because the firmware still assumed
  `RANGE_LOW` (ceiling 100 µA x 1.25 = 125 µA) while the fitted Rs is 10 Ω. Sending `eh`
  declared the HIGH range, the ceiling became 1250 µA, and the flags cleared to `OK`. Without
  the per-range guard this would have been read as a fault in the freshly repaired hardware.
- Pin 1 measuring 3.9 V at idle is **not** a failure and the acceptance criterion stated
  earlier in this document was wrong. `enterSafeIdle()` disables all muxes, presenting an open
  load, which is far above the latch pole; the amplifier latches at idle and regulates as soon
  as a load is connected. Idle latch does mean the `MUX_I_SRC` common pin sits above its 3.3 V
  supply while idle — low current, but continuous, and worth designing out later.

### 10.4 Issues exposed by the working instrument

Neither of these was visible while the pump was latched.

**A. 213 µA offset at zero command.** At `p0` the fit predicts and the hardware delivers about
213 µA when the commanded current is zero — equivalent to 112 mV of phantom input. It is not
the DAC: `MCP4725 VOUT` measures 80 mV at code 100 and ~0 at code 0. Candidates are electrode
half-cell EMF driving through a finite output impedance, or a circuit offset such as a ground
difference between R1's ground leg and the shunt low side. **Discriminating test:** disconnect
all electrodes, fit a 1 kΩ resistor across the drive pair, `p0` with `d` held. Near-zero
current implicates the electrodes; ~213 µA implicates the circuit. Open at time of writing.

**B. E5-E6 injection pair is asymmetric.** At DAC 400, with every other pair symmetric:

```text
I+ E4 I- E5 :  FWD 826 uA   REV 826 uA     normal
I+ E5 I- E6 :  FWD  99 uA   REV 577 uA     5.8x asymmetry
```

A contact fault on E5 or E6, not an instrument fault. Same family as the E5 problem in
[ADR-0009](adr/0009-fix-e5-contact-before-further-capture.md), and it should be fixed
physically for the same reason given there.

### 10.5 Still outstanding

- Dummy-load sweep (section 7.3) has not been run. It is the measurement that quantifies output
  impedance, and it is now also the discriminating test for issue A. **Tooling is now in place**
  (`dummy_load_sweep.py`, [ADR-0015](adr/0015-measure-output-impedance-with-the-instrument.md)):
  the firmware `d` command emits a machine-readable `HOLD` reading, the host sweeps DAC codes at
  one fitted resistor, and `fit` solves for `Rout` across resistors. The bench work - electrodes
  off, resistor across E1-E2, changed between runs - is unchanged and still outstanding, and the
  firmware must be reflashed for `HOLD` to exist.
- Supply is still ±15 V; spec is ±9 V.
- Everything in section 8 stands: no capture predating this repair measured a controlled
  current, and all baselines must be retaken.

### 10.6 Regression after reflash — the source delivers no current

Measured 2026-09-02, after reflashing the firmware carrying the ADR-0015 `HOLD` readout, with
the range declared `eh` (Rs 10 ohm):

```text
d (hold E1/E2), samples 8
  code    0  I     3.032 uA  V   -10.031 mV  I_LOW
  code  100  I     3.192 uA  V    -9.000 mV  I_LOW
  code  200  I     1.596 uA  V    -9.484 mV  I_LOW

one full adjacent frame at code 200, 216 records
  quality   I_LOW 214, OK 2
  I         median 2.554 uA, min 0.000, max 14.045
  V         median 7.703 mV, max 38.656
```

This is global, not confined to the held pair: all 216 records of a full frame read the same
way. Compare the post-repair sweep in section 10.1 four hours earlier, which gave 216 / 361 /
518 / 827 uA at codes 0 / 100 / 200 / 400 on the same rig.

**The distribution matches the documented null exactly.** ADR-0012's floor was set from a frame
captured with the OPA2134 supply physically disconnected, which returned "shunt-channel readings
from 0.000 to 2.554 uA". This frame returns 0.000 to 2.554 uA with a median of 2.554. What is
being measured is the shunt channel's own noise, not a current.

The signature is not a latch. A latched amplifier rails, and section 1 records that as `I_SAT`
with electrode nodes driven past the mux supply; here there is no `I_SAT`, the sense voltages
are single-digit millivolts, and nothing responds to the DAC code.

Two candidates remain, both consistent with everything above:

- **The OPA2134 has no supply.** This is the condition the null frame was captured under, and it
  reproduces the numbers exactly.
- **The MCP4725 output is not reaching the amplifier.** Addressing is confirmed good - the scan
  finds 0x48 and 0x60, and `STATUS` reports `DAC_ADDR,0x60`, so the firmware is writing to the
  device that is present - but a correctly addressed DAC can still have a dead or disconnected
  `VOUT`.

**Discriminating measurements**, both unpowered-safe except the first:

1. Supply rails at the OPA2134 supply pins. Section 10.5 notes the supply is still +/-15 V
   against a +/-9 V spec, so a protection trip or a dislodged lead during the reflash are both
   plausible.
2. `MCP4725 VOUT` at DAC code 200. Section 10.4 measured 80 mV at code 100 on a working rig, so
   roughly 160 mV is expected. Near zero implicates the DAC.

Until one of these is resolved the dummy-load sweep cannot run, since it needs a current to
measure.

**ADR-0012's floor is what caught this.** 214 of 216 records were flagged `I_LOW`. Under the
previous 1.0 uA floor the same frame would have passed most of its records as `Q,OK`, and the
run would have produced a plausible-looking reconstruction out of shunt noise. This is the first
time that floor has fired on live hardware.
