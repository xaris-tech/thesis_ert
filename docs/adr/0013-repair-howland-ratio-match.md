# ADR-0013: Repair the Howland ratio match rather than designing around low output impedance

- **Status:** Superseded by [ADR-0014](0014-current-sense-feedback-tapped-before-rs.md)
- **Date:** 2026-09-02
- **Affects:** the OPA2134 current source, `docs/planned-improvements.md` 1.1, every capture
  taken on this rig to date, and the thesis claim that the instrument injects a controlled
  current
- **Related:** [ADR-0011](0011-current-guard-derives-from-fitted-rs.md),
  [ADR-0012](0012-current-floor-from-measured-noise.md),
  `docs/planned-improvements.md` 1.1, `docs/first-working-prototype/03-howland-current-source.md`

> **Superseded 2026-09-02.** This ADR names the 10.7 percent ratio mismatch as the primary
> fault. It is not. The current-sense feedback is tapped on the wrong side of Rs, so the loop
> never sensed current at all - see [ADR-0014](0014-current-sense-feedback-tapped-before-rs.md).
> The mismatch measured here is real and the arithmetic below is sound, but it is a second-order
> accuracy limitation, not the cause of the voltage-source behaviour.

## Context

`docs/planned-improvements.md` 1.1 recorded, from a 2026-08-27 dummy-load sweep, that the
current pump behaves as a voltage source: `Rout + Ron(mux) ~= 430 ohm` against 4.7-10 kohm
loads, with mismatch `e` estimated at 2-3 percent. It concluded:

> The resistors are soldered and cannot practically be reworked or trimmed, so this is now a
> fixed property of the rig to design around rather than a defect to repair.

The 2026-09-02 session measured the individual resistors in circuit for the first time and
falsifies the premise of that conclusion:

| Part | Position | Measured | Specified |
|---|---|---:|---:|
| R1 | pin 2 to ground | **4.498 kohm** | 5.00 kohm, 0.1% |
| R2 | pin 1 to pin 2 | 98 ohm | 100 ohm, 0.1% |
| R3 | VOUT to pin 3 | **5.022 kohm** | 5.00 kohm, 0.1% |
| R4 | pin 3 to pin 7 | 98.85 ohm | 100 ohm, 0.1% |
| Rs | pin 1 to I_SRC_OUT | 10.0 ohm | HIGH range |

```text
R2/R1 = 0.021787      R4/R3 = 0.019683      e = +10.69%
|Rout| ~ Rs/e = 94 ohm
```

Solving the closed loop with these measured values rather than the nominal ones gives the
operating envelope directly:

```text
pin1 = 0.019724*VDAC + 1.002063*V_load
I    = 0.019724*VDAC / (Rs - 0.002063*R_load)
```

The denominator reaches zero at **R_load = 4846 ohm**. Below roughly 2 kohm the pump is close
enough to well behaved despite the 10.7 percent mismatch; above 4846 ohm the positive feedback
loop gain exceeds unity and the amplifier latches to a rail instead of regulating. An open
circuit is infinitely above that pole, so **powering this amplifier with no load connected
latches it every time, by construction.**

The mismatch is 10.7 percent, not 2-3, and `Rout` is 94 ohm, not 430. R2 and R4 are matched to
each other within 0.9 percent; **R1 and R3 are 10.4 percent apart from each other** despite
being the same nominal 5.00 kohm part. One pair of 5 percent resistors landed at opposite ends
of its tolerance band, and that single pairing accounts for essentially the whole defect.

The consequences observed on the bench are no longer confined to inaccuracy. Every frame
captured on 2026-09-02 was taken with the electrodes open to air - no phantom, no specimen, no
dummy load - which is the latch condition above. The shunt channel railed
(`Q,I_SAT`, the reported 2613.636 uA being the ADS1115 full scale on `GAIN_SIXTEEN`) and did
**not change when the DAC code was dropped from 100 to 7**, a 14x reduction in command. That
insensitivity to the command is the signature of a latched amplifier: the output is at a rail
regardless of its input.

Because the amplifier's output then exceeds the CD4067's 3.3 V supply, the mux input protection
diodes conduct. That clamps both sense inputs to the same potential and produced `V,0.000` on
essentially every pair, and it risks CMOS latch-up in the muxes themselves. The magnitude of
the current in that state is not a measurement of anything and no load resistance should be
inferred from it.

## Decision

The ratio match is repaired rather than designed around. R1 and R3 are replaced with a pair
measured and matched to each other, and the residual mismatch is trimmed at R4 and verified by
dummy-load sweep. `planned-improvements.md` 1.1's "fixed property of the rig" stance is
withdrawn.

## Rationale

1.1's conclusion followed from an estimate of `e` at 2-3 percent, at which point the pump is
merely inaccurate and difference imaging - which normalises each measurement by its own
measured current - can absorb the error. At the actual 10.7 percent the pump drives the analog
path outside the mux's supply rail, so it is not producing degraded data, it is producing no
data and damaging hardware. That is a defect, and the "cannot practically be reworked" premise
was never tested: it was asserted before the individual resistors were measured.

Matching matters far more than nominal accuracy here, because `Rout` depends only on the
agreement between `R2/R1` and `R4/R3`. Sorting the existing 5 percent stock for a closely
matched 5 kohm pair is therefore worth more than buying nominally-correct 1 percent parts and
fitting them unsorted.

Trimming at R4 is specified because the arithmetic is sharp near the null and R4 is the small
resistor, so a small series addition moves the ratio a long way:

| R4 | e | \\|Rout\\| |
|---|---:|---:|
| 98.85 (as fitted) | +10.69% | 94 ohm |
| +8 ohm | +2.40% | 416 ohm |
| **+10 ohm** | **+0.52%** | **1.9 kohm** |
| +12 ohm | -1.29% | 773 ohm |

A fixed 10 ohm series part is a 20x improvement for one component, but the table shows the null
is passed between +10 and +12 ohm, so a fixed resistor cannot reliably reach the 0.1 percent
(`Rout` = 10 kohm) the design assumes. A trimmer set against a dummy-load sweep can.

Alternatives considered:

- **Keep designing around it, per 1.1.** Rejected: no longer viable now that the fault drives
  the mux past its rail. Difference imaging cannot normalise away a measurement that did not
  happen.
- **Trim only, leave R1/R3 mismatched at 10.4 percent.** Rejected as the sole fix. It works
  arithmetically, but it leaves the whole ratio balanced on one small trim resistor, so
  temperature drift and any Rs change move `Rout` sharply. Matching R1 to R3 first makes the
  trim a small correction rather than the entire compensation.
- **Move to a lower current range so the compliance voltage stays under the mux rail.**
  Rejected: only Rs = 10 ohm is fitted, so LOW and MEDIUM cannot be selected in hardware
  (ADR-0011), and it would treat the symptom.
- **Add clamp diodes at the mux inputs to protect against over-rail drive.** Rejected as a
  substitute, worth doing as belt-and-braces later. It protects the hardware but still yields
  no usable measurement.

## Consequences

Captures cannot resume until the repair is done and verified. Everything already in
`phase3a_logs/` was taken with `Rout` at or below the load impedance, so the injected current
was set by the specimen rather than commanded - which means **transfer resistances from those
runs are not measurements of a controlled-current experiment**, independently of the `Q,OK`
problem in ADR-0012.

The repair commits the project to re-verifying the dummy-load sweep from 1.1 as an acceptance
test, and to re-running any baseline the thesis relies on.

`Rout` will remain finite and load-dependent even after the repair. A living tree is a far
higher impedance than the saline tank, so the ratio between `Rout` and the load - and therefore
the honesty of the phrase "controlled current" - must be restated for the tree case rather than
assumed from a saline result.

Withdrawing a recorded conclusion sets the expectation that findings in
`planned-improvements.md` are provisional until the underlying components have been measured
individually, not inferred from terminal behaviour.

## Verification

Bench, in order:

1. Measure the replacement R1/R3 pair out of circuit and record both values; they should agree
   with each other to better than 1 percent, ideally 0.1 percent.
2. Fit, then re-measure all five positions in circuit and compute `e = (R2/R1 - R4/R3)/(R4/R3)`.
   Target `|e|` below 0.1 percent for `Rout` = 10 kohm.
3. Repeat the 1.1 dummy-load sweep at a fixed DAC code with 4.7 kohm and 10 kohm. **The pass
   condition is that measured current is the same at both loads**, not that it hits a
   particular value. Current still tracking `1/R_load` means the repair failed.
4. Confirm `I_SRC_OUT` stays below 3.3 V at the maximum DAC code for the fitted range, so the
   mux protection diodes never conduct.
5. Run the null frame from `docs/current-setup-validation-runbook.md` section 3b and confirm
   zero `Q,OK`.

This decision is falsified if a matched-pair rebuild still yields `Rout` well below the load,
which would point at the OPA2134 stage itself rather than the ratio network.

**Not yet performed.** The repair was specified, not executed, at the time of writing.
