# ESP32-S3 Phase 2 Firmware Design

**Goal**

Create new ESP32-S3 firmware for the user's 8-electrode Phase 2 prototype using a fixed current injection pair, one CD74HC4067 for voltage scanning, MCP4725 for drive setpoint, and ADS1115 for differential voltage measurement.

**Context**

The current Python tool expects serial frames in the form:

```text
SCAN:
0,E1,<value>
1,E2,<value>
...
END
```

The user's current hardware can scan electrode voltages but cannot yet switch current injection pairs automatically. The firmware should therefore produce stable 8-channel voltage frames, not claim full tomography.

**Design**

- Use PlatformIO with Arduino framework for ESP32-S3.
- Keep hardware assumptions explicit in a single config section:
  - I2C on `GPIO8`/`GPIO9`
  - mux select on `GPIO4`/`GPIO5`/`GPIO6`/`GPIO7`
  - mux enable on `GPIO15`
- Support a fixed current injection pair wired externally:
  - `E1` driven by the LM358 current source
  - `E5` used as current return and ADC reference
- Sweep mux channels `0..7`, read ADS1115 differential `A0-A1`, and emit one 8-line frame per scan.
- Keep serial commands simple:
  - `s` single scan
  - `g` start continuous scanning
  - `x` stop continuous scanning
  - `p<number>` set DAC raw code
  - `t<number>` set settle time in milliseconds
  - `h` print help/status

**Non-Goals**

- No automatic current pair switching.
- No on-device image reconstruction.
- No calibration or filtering beyond simple averaging.

**Testing**

- Verify the firmware emits the exact frame markers expected by `ert.py`.
- Verify pin definitions and serial command contract through repo-level inspection.
- Document the flash workflow because no embedded toolchain is installed in this workspace.
