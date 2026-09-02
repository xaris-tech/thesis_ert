# Current Setup Validation Runbook

> **2026-09-02:** the rig is mid-repair. OPA2134 pin 5 is wired to pin 1 instead of
> `I_SRC_OUT`, so the pump has never regulated current and currently latches, reporting
> `Q,I_SAT` on every measurement. Do not treat any capture as valid until the repair and its
> acceptance tests pass — see
> [`i-sat-investigation-2026-09-02.md`](i-sat-investigation-2026-09-02.md).

Use this runbook to validate the Phase 3A setup before trusting any reconstruction image.

This runbook targets the active firmware
(`firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino`)
and a Windows/COM-port host, matching `CLAUDE.md`. Reconcile this document with the firmware
source whenever either changes — see `docs/validity-audit.md` X-01 for the prior drift that
made this runbook fail its own checks.

## Quick path: the Self Test tab

The debug UI runs most of this runbook automatically. Launch it, press **Connect**, then
**Self Test**, and read the tab: one row per component, worst-first remedy in the pane
underneath, `Save report` to keep a copy next to the run logs.

```powershell
.\.venv\Scripts\python.exe tree_ert_app.py --port COM3
```

It covers steps 0, 2, 6 and parts of 5 and 7, and reports the shunt and current-range
mismatches this document warns about. It cannot cover what needs a multimeter: the direct
dummy-load sweep in step 4, and confirming the physically fitted Rs. Set the measured shunt
in the **Fitted shunt ohm** field so the self test has something to compare the firmware's
value against - left blank, that check can only warn.

Run it with no board attached too: the host checks still run, and the hardware checks report
SKIP rather than a misleading pass.

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
"Silicon Labs" or "USB Serial" friendly name). The debug UI's **Refresh ports** button lists
the same thing. If nothing new appears, check the cable, board power, USB mode, and driver.
Note the COM port - it is passed to `tree_ert_app.py --port COM3` or
`phase3a_unified_reconstruct.py --port COM3` (substitute the actual port).

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
- `?` prints `STATUS,2,...` including `SHUNT_OHMS`. The firmware default is `97.9` (the
  measured value - see `docs/validity-audit.md` D-F4/F4; do not expect `100.0`). What matters
  is that it matches the resistor physically fitted, which `j<ohms>` sets.
- `i` prints an I2C scan and should find:
  - MCP4725 at `0x60` **or `0x61`** - the A0 strap picks the low address bit, so this
    board has scanned at both; the firmware probes both at boot and the UI rebinds from the
    scan
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

## 3b. Null Frame Check (do this before every capture session)

**This is the single highest-value check in the runbook and it takes thirty seconds.** It found
a defect on 2026-09-02 that months of reconstruction analysis had not.

Disconnect the OPA2134 supply - battery off, or `V+`/`V-` unplugged - leaving the ESP32-S3, ADC,
and muxes powered over USB. No injected current is physically possible in this state. Then
capture one frame:

```text
s
```

Expected: **every measurement reports `Q,I_LOW`, and no measurement reports `Q,OK`.**

If any measurement reports `Q,OK`, stop. The instrument is certifying noise as data, and every
capture taken under the same firmware is suspect. On the run that motivated this section,
10 of 20 measurements in an unpowered frame were stamped `Q,OK`, with shunt readings from
0.000 to 2.554 uA against a 1.0 uA floor - see [ADR-0012](adr/0012-current-floor-from-measured-noise.md),
which raised that floor to 10.0 uA.

Two things to read off the same frame while you have it:

- **Current readings** show the noise floor of the shunt channel. They should quantise in steps
  of about 0.319 uA, which is 4 LSB of the ADS1115 on `GAIN_SIXTEEN`. A peak materially above
  2.5 uA means `MIN_CURRENT_UA` is no longer far enough above the noise and must be raised.
- **Voltage readings** are pure electrode half-cell potential, since no current is flowing.
  Values of 185-443 mV are normal and are the offset that `paired_transfer_resistance()` exists
  to cancel (`planned-improvements.md` 1.3). Their spread across electrodes is a useful contact
  check in its own right: an electrode far from its neighbours is a contact problem.

## 4. Direct Dummy-Load Check

Start without routing through the electrode muxes:

```text
HCP current output -> dummy resistor -> shunt -> system ground
```

> **Never power the OPA2134 with no load connected.** An open circuit - electrodes in air,
> nothing in the tank, a disconnected dummy - latches the amplifier to a rail. A latched
> amplifier drives the electrode node past the CD4067's 3.3 V supply and can cause CMOS latch-up
> in the muxes. Connect the load first, then apply amplifier power.
>
> The `R_load = 4846 ohm` latch pole this note previously quoted came from
> [ADR-0013](adr/0013-repair-howland-ratio-match.md), which is **superseded by
> [ADR-0014](adr/0014-current-sense-feedback-tapped-before-rs.md)**: it was computed from an R1
> value later re-measured at 4980 ohm, and from a circuit whose sense feedback was miswired.
> **The pole has not been recomputed for the repaired circuit and no measured value replaces
> it.** Treat "connect the load first" as unconditional rather than relying on a number.

Use these loads:

- 500 Ohm
- 1 kOhm
- 2 kOhm

> The 4.7 kohm and 10 kohm loads this section previously specified were dropped as being above
> the then-computed latch pole. That pole figure is stale (see the warning above), but the three
> loads below span the tree's measured 1-1.5 kohm nail-to-nail impedance, which is what the
> sweep needs to bracket. Add a higher load only after the repaired circuit has been shown not
> to latch into it.

Use these DAC codes:

- 50
- 100
- 200
- 300
- 400

Run the sweep once per fitted resistor, then fit across them ([ADR-0015](adr/0015-measure-output-impedance-with-the-instrument.md)):

```powershell
.\.venv\Scripts\python.exe dummy_load_sweep.py measure --port COM7 --load-ohms 500
.\.venv\Scripts\python.exe dummy_load_sweep.py measure --port COM7 --load-ohms 1000
.\.venv\Scripts\python.exe dummy_load_sweep.py measure --port COM7 --load-ohms 2000
.\.venv\Scripts\python.exe dummy_load_sweep.py fit phase3a_logs/dummy-load-sweep.csv
```

This holds E1/E2 with the firmware `d` command and reads the shunt through the instrument's own
ADC - the same channel every reported transfer resistance is normalised by. Include DAC code 0,
which is the discriminating test for the 213 uA zero-command offset in
`docs/i-sat-investigation-2026-09-02.md` section 10.4: near zero implicates the electrodes,
near 213 uA implicates the circuit.

Cross-check at least one point with a multimeter across the shunt - the muxes stay held after
the reading for exactly this - and confirm `SHUNT_OHMS` from `?` matches the fitted part
(measured 97.9 ohm as of 2026-08-27). A shunt-value error scales every current by a constant.

```text
I = Vshunt / SHUNT_OHMS
```

Pass condition:

- current is stable
- current increases predictably with DAC code
- **current is roughly the same at all three loads.** This is the check that actually tests a
  current source, and it is the one that has never been run on the repaired rig. `fit` reports
  it as `flatness %`; a current source is flat, and the pre-repair rig tracked `1/R_load` at
  `Rout = 430 ohm`. An `Rout` far above 2 kohm is the same statement.
- **current responds to DAC code at all.** A reading that does not move when the code changes
  by a large factor is a latched amplifier, not a measurement.

> Earlier revisions of this section predicted 176 / 199 / 269 uA at DAC code 100 for the three
> loads. **Those numbers are withdrawn** - they were derived from ADR-0013's superseded model.
> On the tree after the repair, DAC code 100 measured 361 uA. Go in without a predicted value.
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
- I2C scan does not show `0x61` and `0x48`
- **a null frame (section 3b) reports any `Q,OK` with the current source unpowered**
- **`STATUS` reports `RS_DECLARED,0`, i.e. nobody has confirmed the fitted Rs jumper this
  session (see [ADR-0011](adr/0011-current-guard-derives-from-fitted-rs.md))**
- **any measurement reports `Q,I_SAT`: the current channel is railed and its reported value is
  fiction, not a large current**
- current is near zero or unstable
- current is saturated/high
- voltage exceeds safe mux/ADC range
- logs are header-only
- baseline stability fails
