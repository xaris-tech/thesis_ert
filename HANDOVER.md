# ERT Phase 3A Handover

This repo is a student-built DC Electrical Resistance Tomography prototype. The current goal is not polished medical/geophysical-grade imaging yet; it is a defensible first working prototype that can inject current, switch 12 electrodes, measure voltage/current, and produce repeatable difference reconstructions in a saline phantom or tree trunk sample.

## Current Project Reality

The active system is now Phase 3A:

- 12 electrodes, `E1` to `E12`
- ESP32-S3 controller
- MCP4725 DAC
- ADS1115 ADC
- four CD74HC4067 multiplexers
- OPA2134PA Improved Howland Current Pump
- Python reconstruction script using PyEIT-style difference reconstruction

Important: `AGENTS.md` still contains older Phase 2 assumptions in places, especially the old 8-electrode fixed-injection `SCAN:` format. For Phase 3A, prefer this handover plus:

- `docs/first-working-prototype/README.md`
- `docs/first-working-prototype/04-complete-pinout-and-wiring.md`
- `firmware/esp32s3-phase3a-unified-arduino/README.md`
- `firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino`
- `phase3a_unified_reconstruct.py`
- `PHASE_3A_PINOUT_TABLES.md`

## Thesis-Safe Claim

Safe claim:

> A low-cost 12-electrode DC ERT prototype that can acquire adjacent/opposite measurements and produce repeatable difference reconstructions showing approximate anomaly location in saline phantoms and tree trunk samples.

Avoid claiming:

- it diagnoses tree decay reliably
- it produces absolute conductivity maps
- it is already calibrated against true internal tree anatomy
- a single noisy reconstruction image is proof of detection

## Hardware Summary

Main parts:

| Part | Role |
|---|---|
| ESP32-S3 | Controls I2C, mux address pins, serial protocol |
| MCP4725 | Sets the HCP command voltage |
| ADS1115 | Measures electrode voltage and current-shunt voltage |
| OPA2134PA | Op amp used in Improved Howland Current Pump |
| 4x CD74HC4067 | Switch current source, current return, voltage positive, voltage negative |
| 12 electrodes | Screws/nails/alligator clips around phantom or trunk |

## Critical Power And Ground Rule

Use one signal/system ground reference:

- ESP32 GND
- MCP4725 GND
- ADS1115 GND
- all mux GND pins
- HCP/converter output common ground
- current shunt bottom
- ADS1115 A3

Do not connect the negative analog rail `V-` directly to ESP32 ground. `V-` is the op-amp negative supply rail, not system ground.

Current bench setup:

- ESP32-S3 powered by laptop USB
- HCP powered by a dual-output converter from a 12 V router adapter
- logic parts run at 3.3 V
- mux analog signals must stay roughly inside the mux supply range because CD74HC4067 is powered from 3.3 V

If connecting the analog common ground makes MCP4725 or ADS1115 disappear from I2C, stop and debug power/ground before continuing. Suspect converter wiring, noisy shared ground, wrong common point, or accidental rail short.

## I2C Wiring

| Module | Pin | Connects To |
|---|---|---|
| MCP4725 | VDD | ESP32 3V3 |
| MCP4725 | GND | system ground |
| MCP4725 | SDA | ESP32 GPIO8 |
| MCP4725 | SCL | ESP32 GPIO9 |
| MCP4725 | ADDR | GND, address `0x60` |
| MCP4725 | VOUT | HCP command input through HCP resistor network |
| ADS1115 | VDD | ESP32 3V3 |
| ADS1115 | GND | system ground |
| ADS1115 | SDA | ESP32 GPIO8 |
| ADS1115 | SCL | ESP32 GPIO9 |
| ADS1115 | ADDR | GND, address `0x48` |
| ADS1115 | ALRT | no connection for now |

## ADS1115 Analog Inputs

| ADS Pin | Meaning | Connects To |
|---|---|---|
| A0 | voltage sense positive | `MUX_VP` SIG/COM |
| A1 | voltage sense negative | `MUX_VN` SIG/COM |
| A2 | current shunt high side | `MUX_I_RET` SIG/COM and top of shunt |
| A3 | current shunt low side | system ground and bottom of shunt |

The firmware calculates current from A2-A3. The physical shunt value must match the firmware constant. Verify whether the real shunt is `10 ohm` or `100 ohm`; a mismatch makes printed current wrong by 10x.

## Mux Signal Connections

All four muxes should have:

- `C0 = E1`
- `C1 = E2`
- `C2 = E3`
- `C3 = E4`
- `C4 = E5`
- `C5 = E6`
- `C6 = E7`
- `C7 = E8`
- `C8 = E9`
- `C9 = E10`
- `C10 = E11`
- `C11 = E12`
- `C12-C15` unused

Mux common/SIG connections:

| Mux | SIG/COM Connects To |
|---|---|
| `MUX_I_SRC` | HCP current output, `I_SRC_OUT` |
| `MUX_I_RET` | shunt top and ADS1115 A2 |
| `MUX_VP` | ADS1115 A0 |
| `MUX_VN` | ADS1115 A1 |

Current path:

```text
HCP I_OUT
-> MUX_I_SRC SIG
-> selected source electrode
-> sample/trunk/phantom
-> selected return electrode
-> MUX_I_RET channel
-> MUX_I_RET SIG
-> shunt top / ADS A2
-> shunt
-> system ground / ADS A3
```

Voltage path:

```text
selected V+ electrode -> MUX_VP channel -> MUX_VP SIG -> ADS A0
selected V- electrode -> MUX_VN channel -> MUX_VN SIG -> ADS A1
```

## Mux GPIO Map

| Mux | S0 | S1 | S2 | S3 | EN |
|---|---:|---:|---:|---:|---:|
| `MUX_I_SRC` | GPIO4 | GPIO5 | GPIO6 | GPIO7 | GPIO37 |
| `MUX_I_RET` | GPIO10 | GPIO11 | GPIO12 | GPIO13 | GPIO38 |
| `MUX_VP` | GPIO15 | GPIO16 | GPIO17 | GPIO18 | GPIO39 |
| `MUX_VN` | GPIO36 | GPIO35 | GPIO41 | GPIO42 | GPIO40 |

Avoid GPIO0 for mux addressing because it can affect boot mode. Avoid reusing the same GPIO for two mux address pins.

## HCP Notes

The MCP4725 output does not go to an electrode or mux. It drives the HCP command input.

For the OPA2134PA DIP-8:

| OPA2134 Pin | Role |
|---|---|
| pin 3 | non-inverting input for op amp A; receives MCP4725 command through the HCP resistor network |
| pin 2 | inverting input / feedback network |
| pin 1 | op amp A output / HCP output network |
| pin 8 | positive analog rail |
| pin 4 | negative analog rail |

The exact resistor network should follow the current Improved Howland design doc/schematic, not be guessed from pin names.

## Firmware

Active firmware:

```text
firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino
```

Arduino libraries:

- `Adafruit ADS1X15`
- `Adafruit MCP4725`

Useful serial commands:

| Command | Meaning |
|---|---|
| `s` | capture one complete frame |
| `ma` | adjacent drive pattern |
| `mo` | opposite drive pattern |
| `p100` | set DAC code 100 |
| `t10` | set mux settle time to 10 ms |
| `n4` | set ADC sample averaging count to 4 |
| `g` | continuous frames |
| `x` | stop and idle |
| `?` | status |
| `h` | help |

Current Phase 3A serial records look like:

```text
FRAME,2,1,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4
M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,-12.345,I,210.000,Q,OK
M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,12.210,I,208.500,Q,OK
END,1
```

Do not revert to the old Phase 2 `SCAN:` parser unless intentionally working on legacy files.

## Python Workflow

Main script:

```text
phase3a_unified_reconstruct.py
```

Normal adjacent reconstruction run:

```powershell
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --port COM3 --pattern adjacent --dac 100 --diameter-cm 16.5 --settle-ms 50 --samples 16 --log
```

Faster debug run:

```powershell
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --port COM3 --pattern adjacent --dac 200 --diameter-cm 16.5 --settle-ms 10 --samples 4 --warmup-frames 3 --baseline-frames 3 --frames 10 --log
```

Untouched drift/control run:

```powershell
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --port COM3 --pattern adjacent --dac 100 --diameter-cm 16.5 --settle-ms 50 --samples 16 --log --control
```

Notes:

- Normal mode captures baseline, then prompts the user to place the target and press Enter.
- `--control` mode does not prompt because it is meant to measure untouched drift.
- `--diameter-cm` currently labels/tracks the run. It is not yet a fully physical PyEIT mesh scaling implementation.
- Logs and images are saved under `phase3a_logs/`.

If COM port access is denied, close Arduino Serial Monitor or any other serial program using the port.

## Current Known Issues

1. Current can be too low.

   When median current is around `14 uA`, reconstructions become mostly random and baseline stability often fails. The practical current target for this breadboard prototype is roughly `100-500 uA`, with `300 uA` being a useful initial target.

2. Current is not perfectly constant across injection pairs.

   Example observed behavior: one injection pair may report around `110 uA`, another around `160 uA`, another around `200 uA`. This points to electrode contact, mux resistance, HCP compliance/headroom, wiring, breadboard, or shunt-value mismatch.

3. E9/E10 has appeared as an outlier.

   Voltage pair `E9-E10` was often much larger than neighboring pairs. Investigate E9/E10 electrode contact, channel wiring, `MUX_VP`/`MUX_VN` channels `C8/C9`, and alligator clips.

4. Some current paths can read zero or `I_LOW`.

   If `I+,E8 I-,E7` works but `I+,E8 I-,E9` reads zero, suspect the E9 return path:

   ```text
   E9 electrode -> MUX_I_RET C8 -> MUX_I_RET SIG -> shunt -> system ground
   ```

5. `I_REVERSED` near zero is usually noise/current-path failure.

   A line like `I=-2.813 uA` is not evidence of real reversed current. Treat it as a bad/low current reading.

6. Baseline stability can fail for real reasons.

   Do not bypass the baseline stability checks just to get an image. If baseline fails, debug contact/current first.

## Debug Priority Order

Use this order before trusting reconstructions:

1. I2C scan: confirm MCP4725 at `0x60` and ADS1115 at `0x48`.
2. Confirm physical shunt value and firmware shunt constant match.
3. Confirm DAC command changes HCP output/current.
4. With dummy loads, verify current is in the expected range.
5. Test each mux channel electrically from `C0` to `C11`.
6. Test each electrode contact resistance or voltage response.
7. Run `--control` with no target movement.
8. Only after stable control results, insert a known target in saline and check if the average reconstruction moves with the target.

## Validation Plan

Good validation ladder:

1. Dummy resistor/load tests, no tank.
2. Resistor ring or known resistor network, if available.
3. Saline phantom with stable electrodes.
4. Saline phantom with known inserted object.
5. Banana/moringga trunk.
6. Other tree trunk samples.

Minimum useful success condition:

- Control run with no target should be repeatable.
- Inserted object should create an average reconstruction hotspot that moves when the object is moved.
- Localization should be approximate, for example within 1-2 electrode sectors, not exact pixel-perfect imaging.

## Interpretation Rules

The reconstruction is a difference image relative to baseline.

- Gray/near zero means little change from baseline.
- Red means positive relative conductivity change in the reconstruction model.
- Blue means negative relative conductivity change in the reconstruction model.

Do not automatically interpret red as "decay" or blue as "healthy." The color depends on baseline, target material, current pattern, solver sign convention, and measurement stability.

The average reconstruction over 20 frames is more trustworthy than any single frame.

## What The Next Agent Should Not Do

- Do not assume Phase 2 fixed-injection docs are current for Phase 3A.
- Do not change serial format without updating Python parser and tests.
- Do not ignore `Q=I_LOW`, `Q=I_HIGH`, or `Q=I_REVERSED`.
- Do not trust images when current is only around `14 uA`.
- Do not connect op-amp `V-` rail to logic ground.
- Do not claim diagnostic tree imaging from the current prototype without validation data.

## Suggested Next Work

Best next tasks:

1. Verify and document the real shunt value, then sync firmware constant and docs.
2. Add a simple serial/I2C diagnostic firmware command if not already present.
3. Add a per-electrode/per-current-pair health report in Python.
4. Improve logs so every run records DAC, shunt value, current median, diameter label, pattern, and stability summary.
5. Create a validation dataset: control, target near E11/E12, target near E2/E3, target near center.
6. Compare average reconstruction location against known target location.

## Test Commands

Run Python tests after code edits:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Basic import/help checks:

```powershell
.\.venv\Scripts\python.exe -c "import phase3a_unified_reconstruct; print('import ok')"
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --help
```

## Short Version For A New Agent

This is a Phase 3A 12-electrode DC ERT prototype. The hardware can switch source, return, V+, and V- through four CD74HC4067 muxes. The ADS1115 reads electrode voltage on A0-A1 and shunt current on A2-A3. The Python script reconstructs difference images from baseline vs target frames. The biggest current blocker is not the plotting code; it is measurement repeatability: current level, shunt correctness, electrode contact, mux channel health, and grounding. Stabilize those before trusting the image.
