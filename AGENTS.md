# AGENTS.md

## Purpose

This repo is an experimental ERT/EIT prototype.

The current project state is:

- live acquisition in Python works
- Phase 2 firmware exists for an `ESP32-S3`
- hardware is an `8-electrode scanner` with fixed injection
- full tomography reconstruction hardware is **not** complete yet

Agents working in this repo should optimize for:

- accurate hardware/software handoff
- honest limits about what the current setup can and cannot do
- safe incremental changes to Python analysis and ESP32 firmware

## Read This First

Start with:

- [PROJECT_CONTEXT.md](/C:/Users/Vidad/Documents/ERT/PROJECT_CONTEXT.md)
- [ert.py](/C:/Users/Vidad/Documents/ERT/ert.py)
- [tests/test_ert.py](/C:/Users/Vidad/Documents/ERT/tests/test_ert.py)

For firmware:

- Arduino IDE version:
  - [esp32s3_phase2.ino](/C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2-arduino/esp32s3_phase2/esp32s3_phase2.ino)
  - [README.md](/C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2-arduino/README.md)
- PlatformIO version:
  - [main.cpp](/C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2/src/main.cpp)
  - [platformio.ini](/C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2/platformio.ini)

## Current Hardware Model

Known parts:

- `ESP32-S3`
- `MCP4725`
- `ADS1115`
- `LM358`
- `CD74HC4067`
- `8` electrodes

Current Phase 2 behavior:

- fixed current injection pair:
  - `E1` = drive electrode
  - `E5` = return/reference electrode
- voltage sensing is scanned through one `CD74HC4067`
- the mux selects which electrode is measured
- the current path is **not** routed through the mux common

Important:

- `E1` is both the drive electrode and connected to mux channel `C0`
- this is intentional and electrically allowed
- one `CD74HC4067` is enough for scanning sensed voltages
- one `CD74HC4067` is **not** enough for full switched EIT tomography

## Truths Agents Should Preserve

Do not overclaim.

The current setup can do:

- multi-electrode live scanning
- baseline vs current comparison
- per-electrode delta analysis
- offline export to CSV/NPZ
- firmware-driven 8-channel scan frames

The current setup does **not** yet do:

- proper multi-pattern current injection
- full `PyEIT` reconstruction input completeness
- physically rigorous tomography inversion

If asked whether this reconstructs already, the answer should be:

- acquisition/scanning: yes
- real reconstruction: not yet

## Serial Protocol Contract

The Python side expects scan frames in this exact shape:

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

Do not casually change this format unless you also update the Python parser and tests.

## Python Workflow

[ert.py](/C:/Users/Vidad/Documents/ERT/ert.py) is the main live acquisition tool.

Current responsibilities:

- serial reading
- scan parsing
- baseline/session management
- plotting
- export to CSV / `.npz`

It now supports multi-electrode views and recent delta history.

If modifying it:

- keep pure logic testable
- extend tests in [tests/test_ert.py](/C:/Users/Vidad/Documents/ERT/tests/test_ert.py)
- preserve export compatibility unless intentionally versioning it

Preferred verification:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ert -v
.\.venv\Scripts\python.exe -c "import ert; print('import ok')"
.\.venv\Scripts\python.exe .\ert.py --help
```

## Firmware Workflow

There are two firmware variants:

- Arduino IDE
- PlatformIO

Prefer keeping them behaviorally aligned.

If updating commands, scan format, or GPIO behavior:

- update both firmware variants if possible
- update the corresponding README
- keep the serial command contract documented

Current firmware commands:

- `s` single scan
- `g` continuous scanning on
- `x` continuous scanning off
- `p<number>` set DAC raw value
- `t<number>` set mux settle time in ms
- `r<number>` set continuous scan period in ms
- `h` print help

## GPIO Map

Current Phase 2 GPIO assignments:

- `GPIO8` -> `SDA`
- `GPIO9` -> `SCL`
- `GPIO4` -> `CD74HC4067 S0`
- `GPIO5` -> `CD74HC4067 S1`
- `GPIO6` -> `CD74HC4067 S2`
- `GPIO7` -> `CD74HC4067 S3`
- `GPIO15` -> `CD74HC4067 EN`

Do not silently change these without updating firmware docs and project context.

## Testing Guidance

Good current test media:

- saline sponge
- lightly salted water

Saline sponge is acceptable for bench validation, but it is not a final tomography medium.

Use it for:

- contact testing
- switching verification
- stability checks
- repeatability checks

Not for:

- claiming reconstruction quality
- claiming proper geometry for `PyEIT`

## Preferred Next Work

Good next tasks in this repo:

- improve Python offline analysis of exported scans
- add stability metrics and noise summaries
- add a separate `PyEIT`-prep/analyzer tool that stops short of fake reconstruction
- improve firmware robustness and documentation
- prepare hardware/firmware for more complete switching later

Avoid jumping straight to “image reconstruction” unless the hardware assumptions have changed.

## Working Style

When changing code:

- prefer small, test-backed edits
- preserve the user's current wiring assumptions unless explicitly changing hardware design
- keep docs in sync with code
- if a result is experimental or approximate, label it clearly

If adding new analysis files, keep them separate from `ert.py` unless they are truly part of the live acquisition loop.
