# OPA2134PA Improved Howland Current Source

## Design Basis

Use the `OPA2134PA` in DIP-8 and follow TI Improved Howland Current Pump
Design 2. The final schematic must preserve the resistor ratios from the TI
design rather than combining values from unrelated Howland variants.

Primary reference:

- [TI SBOA437A: How to Design a Simple, Voltage-Controlled, Bidirectional Current Source](https://www.ti.com/lit/an/sboa437a/sboa437a.pdf)

## OPA2134PA Pinout

| Pin | Function |
|---:|---|
| 1 | output A |
| 2 | inverting input A |
| 3 | non-inverting input A |
| 4 | negative supply, approximately -9 V |
| 5 | non-inverting input B |
| 6 | inverting input B |
| 7 | output B |
| 8 | positive supply, approximately +9 V |

The second amplifier is used as required by the selected TI Design 2 circuit;
do not automatically tie it off as an unused amplifier if the TI schematic
uses it to buffer the load/output node.

## Verified Design 2 Wiring and Values

Use these starting values from the ratio demonstrated in TI Design 2:

| Part | Value | Connection on OPA2134PA |
|---|---:|---|
| R1 | 5.00 kohm, 0.1% | ground (`Vn`) to pin 2 |
| R2 | 100 ohm, 0.1% | pin 1 to pin 2 |
| R3 | 5.00 kohm, 0.1% | MCP4725 VOUT (`Vp`) to pin 3 |
| R4 | 100 ohm, 0.1% | pin 7 buffered output to pin 3 |
| Rs | selectable; table below | pin 1 to `I_SRC_OUT` |

Buffer wiring:

- pin 5 senses `I_SRC_OUT`, the junction after Rs;
- pin 6 connects to pin 7, making amplifier B a voltage follower; and
- pin 7 drives R4 but does not connect directly to the electrode mux.

For this balanced network, TI Equation 3 reduces to:

```text
Iload = (Vp - Vn) * (R2 / R1) / Rs
Iload = VDAC * 0.02 / Rs       when Vn = 0 V
```

Do not modify R4 by subtracting Rs. TI explicitly states that the buffered
Design 2 no longer uses that Design 1 correction.

## Selectable Prototype Ranges

The following limits assume a 3.3 V MCP4725 and are rounded conservatively:

| Range label | Rs | Maximum DAC code | Approximate maximum current |
|---|---:|---:|---:|
| LOW | 68 ohm, 0.1% | 420 | 100 uA |
| MEDIUM | 22 ohm, 0.1% | 680 | 500 uA |
| HIGH | 10 ohm, 0.1% | 620 | 1.0 mA |

Begin with LOW. The HIGH range is not enabled until dummy-load compliance,
mux-voltage, current-monitor, and thermal tests pass. Firmware and the app
must enforce the maximum DAC code associated with the physically selected
jumper. Measure the actual MCP4725 output because its full-scale voltage
follows the measured 3.3 V supply.

## Resistor Policy

- Use 0.1% through-hole metal-film parts for ratio-setting resistors.
- If only 1% parts are available, measure and pair them with the multimeter;
  do not treat that version as the calibrated build.
- Use a break-before-make jumper or power off before changing Rs.
- Never leave Rs bypassed or shorted.
- Confirm each installed value with the multimeter before applying power.

## Current Monitor

Route the selected current return through a 100 ohm, 0.1% shunt before ground:

```text
selected return electrode --> MUX_I_RET common --> shunt --> system ground
                                            |       |
                                           A2      A3
```

At 100 uA the expected shunt voltage is about 10 mV; at 1 mA it is about
100 mV. Confirm both A2 and A3 remain within the ADS1115 supply rails.

## Isolated Bring-Up

Test the current source before connecting a mux:

1. Set the lowest current range and minimum useful DAC command.
2. Connect a known dummy load from current output to return/shunt.
3. Calculate current using both load voltage and shunt voltage.
4. Repeat with several loads across the expected operating range.
5. Run a five-minute stability test.
6. Check OPA output voltage; reject any range that approaches saturation.
7. Increase current only after the lower range passes.

Use 470 ohm, 1 kohm, 2.2 kohm, 4.7 kohm, and 10 kohm loads initially. The
validated load range, not an assumed tree resistance, defines the usable
current settings.
