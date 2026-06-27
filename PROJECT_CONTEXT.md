# ERT Project Context

## Current Goal

Build an Electrical Resistance Tomography / Electrical Impedance Tomography prototype in phases:

- `Phase 1`: prove live sensing works with a simple 4-electrode setup
- `Phase 2`: scale to an 8-electrode scanner with real multi-electrode data acquisition
- later: move toward true `PyEIT`-style reconstruction with more complete switching hardware

## Repo Status

Current important files:

- [ert.py](C:/Users/Vidad/Documents/ERT/ert.py)
- [tests/test_ert.py](C:/Users/Vidad/Documents/ERT/tests/test_ert.py)
- [firmware/esp32s3-phase2-arduino/esp32s3_phase2.ino](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2-arduino/esp32s3_phase2.ino)
- [firmware/esp32s3-phase2-arduino/README.md](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2-arduino/README.md)
- [firmware/esp32s3-phase2/platformio.ini](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2/platformio.ini)
- [firmware/esp32s3-phase2/src/main.cpp](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2/src/main.cpp)

Support docs created during this session:

- [docs/superpowers/specs/2026-05-27-live-ert-acquisition-design.md](C:/Users/Vidad/Documents/ERT/docs/superpowers/specs/2026-05-27-live-ert-acquisition-design.md)
- [docs/superpowers/plans/2026-05-27-live-ert-acquisition.md](C:/Users/Vidad/Documents/ERT/docs/superpowers/plans/2026-05-27-live-ert-acquisition.md)
- [docs/superpowers/specs/2026-05-27-esp32s3-phase2-firmware-design.md](C:/Users/Vidad/Documents/ERT/docs/superpowers/specs/2026-05-27-esp32s3-phase2-firmware-design.md)
- [docs/superpowers/plans/2026-05-27-esp32s3-phase2-firmware.md](C:/Users/Vidad/Documents/ERT/docs/superpowers/plans/2026-05-27-esp32s3-phase2-firmware.md)

## Phase 1 Summary

The original Python script was a simple live serial reader for a 4-electrode setup. It captured:

- a baseline scan
- later scans
- voltage deltas from baseline

The newer [ert.py](C:/Users/Vidad/Documents/ERT/ert.py) now supports:

- structured scan parsing
- baseline/session management
- real-time plotting
- CSV export
- NumPy `.npz` export

It is designed as a live acquisition tool, not a fake tomography reconstruction.

## Hardware In Use

Current known parts:

- `ESP32-S3`
- `MCP4725`
- `ADS1115`
- `LM358`
- `CD74HC4067`
- electrodes
- breadboard / wiring / resistor `Rs`

## Phase 1 Wiring Context

Original 4-electrode setup concept:

- `ESP32 3V3` -> `MCP4725 VDD`, `ADS1115 VDD`
- `ESP32 GND` -> common ground
- `ESP32 VIN/5V` -> `LM358 pin 8`
- `GPIO8` -> I2C `SDA`
- `GPIO9` -> I2C `SCL`

Current drive:

- `MCP4725 VOUT` -> `LM358 pin 3`
- `LM358 pin 1` -> resistor `Rs`
- other side of `Rs` -> `LM358 pin 2`
- same `Rs / pin 2` node -> injection electrode

## Phase 2 Direction

Phase 2 uses:

- `8 electrodes`
- `CD74HC4067` to scan sensed voltages
- fixed current injection pair in hardware

Important constraint:

- with only one `CD74HC4067`, the system can switch the measured voltage electrode
- it cannot yet fully switch current-pair and voltage-pair combinations required for full automatic tomography

So the current Phase 2 design is an `8-electrode scanner`, not yet full automated tomography hardware.

## Phase 2 GPIO Map

Current GPIO assignments:

- `GPIO8` -> `MCP4725 SDA` + `ADS1115 SDA`
- `GPIO9` -> `MCP4725 SCL` + `ADS1115 SCL`
- `GPIO4` -> `CD74HC4067 S0`
- `GPIO5` -> `CD74HC4067 S1`
- `GPIO6` -> `CD74HC4067 S2`
- `GPIO7` -> `CD74HC4067 S3`
- `GPIO15` -> `CD74HC4067 EN`

## Phase 2 Full Connection Table

### Power

- `ESP32 3V3` -> `MCP4725 VDD`
- `ESP32 3V3` -> `ADS1115 VDD`
- `ESP32 3V3` -> `CD74HC4067 VCC`
- `ESP32 GND` -> `MCP4725 GND`
- `ESP32 GND` -> `ADS1115 GND`
- `ESP32 GND` -> `CD74HC4067 GND`
- `ESP32 GND` -> `LM358 pin 4`
- `ESP32 VIN / 5V` -> `LM358 pin 8`

### I2C

- `GPIO8` -> `MCP4725 SDA`
- `GPIO8` -> `ADS1115 SDA`
- `GPIO9` -> `MCP4725 SCL`
- `GPIO9` -> `ADS1115 SCL`
- `MCP4725 ADDR` -> `GND`
- `ADS1115 ADDR` -> `GND`

### Mux Control

- `GPIO4` -> `CD74HC4067 S0`
- `GPIO5` -> `CD74HC4067 S1`
- `GPIO6` -> `CD74HC4067 S2`
- `GPIO7` -> `CD74HC4067 S3`
- `GPIO15` -> `CD74HC4067 EN`

### LM358 Current Injection

- `MCP4725 VOUT` -> `LM358 pin 3`
- `LM358 pin 1` -> one side of `Rs`
- other side of `Rs` -> `LM358 pin 2`
- same `Rs / pin 2` node -> `E1`

Fixed return:

- `E5` -> `GND`

### ADS1115

- `CD74HC4067 SIG` -> `ADS1115 A0`
- `ADS1115 A1` -> `E5`

### Electrode to Mux

- `E1` -> `CD74HC4067 C0`
- `E2` -> `CD74HC4067 C1`
- `E3` -> `CD74HC4067 C2`
- `E4` -> `CD74HC4067 C3`
- `E5` -> `CD74HC4067 C4`
- `E6` -> `CD74HC4067 C5`
- `E7` -> `CD74HC4067 C6`
- `E8` -> `CD74HC4067 C7`

## Important Electrical Interpretation

- `E1` is both the fixed injection electrode and also connected to mux channel `C0`
- this is allowed because `C0` is only a sense tap when selected
- the injection current path should not be routed through the mux common
- the mux is only used to choose which electrode voltage is measured

## Current Firmware Status

Two firmware versions were created:

### Arduino IDE

- [firmware/esp32s3-phase2-arduino/esp32s3_phase2.ino](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2-arduino/esp32s3_phase2.ino)

### PlatformIO

- [firmware/esp32s3-phase2/src/main.cpp](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2/src/main.cpp)

Both firmware versions are meant to:

- initialize `MCP4725`
- initialize `ADS1115`
- control the `CD74HC4067`
- read `ADS1115 A0-A1`
- scan all `8` electrodes
- emit serial frames compatible with the Python parser

Expected frame format:

```text
SCAN:
0,E1,123.456
1,E2,120.987
2,E3,118.200
3,E4,119.600
4,E5,0.000
5,E6,126.400
6,E7,129.800
7,E8,131.100
END
```

Supported firmware serial commands:

- `s` single scan
- `g` enable continuous scanning
- `x` disable continuous scanning
- `p<number>` set DAC raw value `0..4095`
- `t<number>` set mux settle time in ms
- `r<number>` set continuous scan period in ms
- `h` print help

## Python Tool Status

[ert.py](C:/Users/Vidad/Documents/ERT/ert.py) currently:

- reads serial scan frames
- stores baseline and later measurements
- plots baseline/current/delta
- exports captured data

It was originally built around 2-channel scans, but the parser and export flow are structured enough to evolve to the 8-electrode firmware output.

## What Has Been Verified

Verified locally in this workspace:

- Python tests pass for parsing/export/session behavior
- `ert.py --help` works
- `import ert` works
- firmware files exist
- firmware contains the `SCAN:` frame marker
- Arduino README contains library and serial instructions
- PlatformIO README contains upload instructions

Not verified locally:

- actual ESP32 compile
- actual flash/upload
- actual live 8-electrode scan on hardware

Reason:

- this workspace does not have PlatformIO / embedded toolchain installed
- hardware is not directly available to the assistant

## Recommended Hardware Test Procedure

Use this as the first live Phase 2 test:

1. Arrange `8 electrodes` evenly around a container.
2. Fill the container with lightly salted water.
3. Confirm wiring matches the Phase 2 table above.
4. Upload the Arduino IDE firmware.
5. Open Serial Monitor at `115200`.
6. Send `h`.
7. Send `p300`.
8. Send `s`.
9. Confirm a full `8`-line `SCAN:` frame is printed.
10. Repeat `s` several times with nothing changing.
11. Introduce an object and repeat scans.
12. Observe whether the per-electrode pattern changes.

## Current Limitations

- current injection pair is fixed in hardware: `E1 -> E5`
- only one mux is used
- not yet full switched tomography
- not yet true `PyEIT`-ready measurement completeness for a proper inverse solve

This phase is still useful because it validates:

- multi-electrode scanning
- analog stability
- firmware protocol
- Python integration path

## Next Likely Steps

Most useful next tasks:

1. update [ert.py](C:/Users/Vidad/Documents/ERT/ert.py) to treat the new firmware as a full 8-electrode scan and visualize all 8 channels cleanly
2. bench test the Arduino IDE firmware on the actual ESP32-S3
3. tune DAC level, mux settle time, and scan period for stability
4. decide whether to expand hardware for real switched tomography
5. if true tomography is required, add more switching paths for `I+`, `I-`, `V+`, and `V-`

## Short Summary

Current project state:

- Phase 1 live acquisition works in Python
- Phase 2 8-electrode scanner hardware plan is defined
- Phase 2 ESP32-S3 firmware was created for both Arduino IDE and PlatformIO
- system is ready for first real 8-electrode bench testing
- full automated tomography hardware is not built yet
