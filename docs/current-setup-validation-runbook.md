# Current Setup Validation Runbook

Use this runbook to validate the Phase 3A setup before trusting any reconstruction image.

This runbook targets the active firmware
(`firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino`)
and a Windows/COM-port host, matching `CLAUDE.md`. Reconcile this document with the firmware
source whenever either changes — see `docs/validity-audit.md` X-01 for the prior drift that
made this runbook fail its own checks.

## 0. Software Baseline

From the repo root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected result: all tests pass. This exercises host-side logic only — it does not compile,
flash, or run the firmware (see `tests/test_phase3a_unified_firmware.py`'s module docstring).

## 1. USB Serial Detection

Connect the ESP32-S3 with a data-capable USB cable, then check ports:

```powershell
Get-PnpDevice -Class Ports -PresentOnly
```

Expected result: a new `COMn` entry appears after plugging in the ESP32-S3 (typically under a
"Silicon Labs" or "USB Serial" friendly name). If nothing new appears, check the cable, board
power, USB mode, and driver. Note the COM port — it is passed to `tree_ert_app.py --port COM3`
or `phase3a_unified_reconstruct.py --port COM3` (substitute the actual port).

## 2. Firmware Diagnostic

Open a serial terminal (Arduino IDE Serial Monitor, PuTTY, or `tree_ert_app.py`) at 115200 baud
with newline enabled. Send:

```text
h
?
i
```

Expected:

- `h` prints the command list.
- `?` prints `STATUS` including `SHUNT_OHMS,97.9` (the measured value — see
  `docs/validity-audit.md` D-F4/F4; do not expect `100.0`).
- `i` prints an I2C scan and should find:
  - MCP4725 at `0x61`
  - ADS1115 at `0x48`

If either I2C device is missing, stop and fix wiring/power before scanning.

## 3. Safe Idle Check

Send:

```text
x
```

Expected:

- DAC command is forced to zero.
- All muxes are disabled.
- No electrode current should be intentionally driven.

## 4. Direct Dummy-Load Check

Start without routing through the electrode muxes:

```text
HCP current output -> dummy resistor -> shunt -> system ground
```

Use these loads:

- 1 kOhm
- 4.7 kOhm
- 10 kOhm

Use these DAC codes:

- 50
- 100
- 200
- 300
- 400

For each setting, measure the voltage across the shunt with a multimeter and confirm it matches
what `?` reported for `SHUNT_OHMS` (measured 97.9 ohm as of 2026-08-27; re-check if the board or
shunt component has changed).

```text
I = Vshunt / SHUNT_OHMS
```

Pass condition:

- current is stable
- current increases predictably with DAC code
- current is in a useful microamp range
- no analog node exceeds the safe mux/ADC range

## 5. Mux Path Check

After direct dummy-load behavior is correct, test through the mux source and return path. Use `p100` first.

Expected based on prior good logs:

- DAC `100` can produce roughly `300-350 uA` in good runs.
- `OK` quality should dominate.

If a pair reports near-zero current, debug that source/return electrode path and mux channel before looking at reconstruction.

## 6. Single Frame Check

Use adjacent mode first:

```text
ma
p100
t30
n4
s
```

Expected:

- one `FRAME,2,...,ADJACENT...` block
- measurement records with `Q,OK`
- median current roughly in the selected target range
- no repeated `I_LOW`, `I_HIGH`, `I_REVERSED`, or `V_RANGE`

## 7. Python Acquisition Check

After the serial port is visible, run a short control capture:

```powershell
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py `
  --port COM3 `
  --pattern adjacent `
  --dac 100 `
  --settle-ms 30 `
  --samples 4 `
  --warmup-frames 1 `
  --baseline-frames 3 `
  --frames 3 `
  --log `
  --control
```

(substitute the actual COM port from step 1)

Expected:

- raw CSV log is created in `phase3a_logs/`
- frames are written, not just the CSV header
- baseline/control stability report is produced

If the CSV contains only a header, the script opened a log but did not capture frames. Check serial port, firmware reset timing, command mode, and whether another serial monitor is holding the port.

## 8. Known Current Findings From Existing Logs

Existing good Phase 3A logs show that DAC `100` can produce stable current around `318-342 uA` with `Q=OK`.

Existing bad early opposite-drive logs show current saturation or bad quality flags such as `I_HIGH`, `I_LOW`, or `I_REVERSED`. Treat those as electrical/acquisition failures, not reconstruction evidence.

## 9. Stop Conditions

Stop and debug hardware before reconstruction when:

- ESP32-S3 serial port is not visible
- I2C scan does not show `0x60` and `0x48`
- current is near zero or unstable
- current is saturated/high
- voltage exceeds safe mux/ADC range
- logs are header-only
- baseline stability fails
