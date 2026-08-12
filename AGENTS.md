# AGENTS.md

## Purpose

This repo is a student-built DC Electrical Resistance Tomography prototype for
assessing coconut palm health categories. The active system is **Phase 3A**: 12
electrodes, ESP32-S3, four multiplexers, switched injection and sensing.

Agents working here should optimise for:

- honest limits about what the prototype can and cannot show
- measurement repeatability over visualisation polish
- small, test-backed changes across firmware, Python and docs together

## Read this first

| Read | For |
|---|---|
| `HANDOVER.md` | The built system: hardware, wiring, grounding rules, current state |
| `CONTEXT.md` | Project vocabulary. Use these terms; they are deliberate |
| `docs/adr/` | Why contested decisions were made. Do not silently reverse these |
| `docs/chapter-3-methodology-draft.md` | The full methodology and validation ladder |
| `docs/prd-aiot-ert-coconut-validation.md` | Product requirements and scope boundaries |
| `docs/current-setup-validation-runbook.md` | Hardware bring-up order when anything misbehaves |
| `PHASE_3A_PINOUT_TABLES.md` | Complete wiring tables |

`docs/archive/` is provenance only. Never build or wire from it.

## Current hardware

| Part | Role |
|---|---|
| ESP32-S3 | I2C, mux address pins, serial protocol |
| MCP4725 (`0x60`) | Sets the current-pump command voltage |
| ADS1115 (`0x48`) | Measures electrode voltage and current-shunt voltage |
| OPA2134PA | Improved Howland current pump |
| 4x CD74HC4067 | Switch current source, current return, voltage positive, voltage negative |
| 100 ohm shunt | Converts return current to measurable voltage |
| 12 stainless steel screws | Electrodes E1 to E12 |

Measurement is **tetrapolar**: current is injected through one electrode pair
while voltage is measured across a different pair, and the injected current is
measured rather than assumed.

**Critical power rule.** One signal ground reference shared by ESP32, MCP4725,
ADS1115, all mux GND pins, the converter output common, the shunt bottom and
ADS1115 A3. The op-amp negative rail `V-` is **not** system ground and must never
be tied to it.

## GPIO map (Phase 3A unified)

```
PIN_SDA = 8, PIN_SCL = 9

MUX_I_SRC = s0:4  s1:5  s2:6  s3:7  en:37
MUX_I_RET = s0:10 s1:11 s2:12 s3:13 en:38
MUX_VP    = s0:15 s1:16 s2:17 s3:18 en:39
MUX_VN    = s0:36 s1:35 s2:41 s3:42 en:40
```

Do not change these without updating `PHASE_3A_PINOUT_TABLES.md`, the firmware
README and the firmware tests.

## Serial protocol contract

Frames are the v2 format, **not** the old Phase 2 `SCAN:` format:

```text
FRAME,2,<frame_id>,<pattern>,DAC,<code>,SETTLE,<ms>,SAMPLES,<n>
M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,13.250,I,335.625,Q,OK
M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,-13.125,I,335.313,Q,OK
...
END,<frame_id>
```

Changing this format means updating the firmware, the Python parser in
`phase3a_unified_reconstruct.py`, and `tests/test_phase3a_unified_firmware.py`
in the same change.

Firmware commands:

```
s     capture one forward/reverse frame
ma    adjacent drive        ms   skip-1 drive
mk    skip-2 drive          mo   opposite drive
pN    set DAC code 0..620 (output stays idle until a scan)
tN    set mux settle time in ms
nN    set samples per ADC reading, 1..32
g     continuous frames on   x    stop and force safe idle
rN    set continuous frame interval in ms
i     scan I2C bus           ?    print status         h    help
```

## Invariants agents must not break

These are decisions with reasoning recorded in `docs/adr/`. Reversing one
silently will corrupt results in ways that are hard to notice.

1. **Logging requires labels.** Every CSV row carries `specimen` and `stage`.
   Acquisition refuses to run with logging enabled and no labels. A scan whose
   subject is only inferable from a timestamp is unusable, and cut-trunk defect
   stages cannot be re-scanned to recover the label.
2. **Never mask a measurement for changing a lot.** Excluding pairs that wobble
   while nothing is changing is legitimate noise rejection. Excluding pairs with
   a large delta deletes exactly the defect signal being looked for. Large
   deltas are counted as `large_delta_pairs`, never overwritten.
3. **Voltage channel is `GAIN_EIGHT`, shunt channel is `GAIN_SIXTEEN`.** Signals
   are around 13 mV; `GAIN_ONE` wastes 8x of the ADC range and puts quantisation
   error above the stability limit on nearly a tenth of measurements. The PGA
   setting does not change the ADS1115's absolute input limits.
4. **Frame duration is a drift driver.** Configure injection once per injection
   pair and hold it while the voltage muxes sweep. Do not reintroduce a
   per-measurement teardown of the injection path.
5. **Field baselines are quality control, never an imaging reference.** A tree
   cannot be scanned before it became diseased, so subtracting two same-session
   tree scans yields drift, not anatomy. Difference reconstruction is for the
   phantom and for consecutive cut-trunk defect stages only.
6. **No overclaiming.** The prototype does not diagnose disease, detect a named
   disease, replace Philippine Coconut Authority expert evaluation, or produce
   absolute conductivity maps.

## Python workflow

| File | Role |
|---|---|
| `phase3a_unified_reconstruct.py` | Active acquisition and reconstruction. CLI entry point |
| `phase3a_reconstruct.py` | Protocol, mesh and solver helpers, imported as `base` |
| `tree_ert/` + `tree_ert_app.py` | PyQt6 acquisition UI |
| `ert.py`, `pyeit_analyzer.py` | Legacy Phase 2 tools. Still tested and useful for export analysis; not the current path |

Verification (macOS/Linux):

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tree_ert_app.py --demo        # UI without hardware
```

Setup if `.venv` is missing:

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
```

`--demo` uses `DemoAcquisition`, so UI and controller changes can be exercised
with no board attached. Tests must stay hardware-free and must not write into
`phase3a_logs/`.

## Firmware workflow

Only one firmware is current:
`firmware/esp32s3-phase3a-unified-arduino/`. The Phase 2, adjacent-only and
opposite-only variants were removed; `firmware/esp32s3-hcp-test-arduino/`
remains as a current-pump bench tool for the dummy-load step.

When changing firmware, update in the same change: the `.ino`, the firmware
README, `PHASE_3A_PINOUT_TABLES.md` if pins move, and
`tests/test_phase3a_unified_firmware.py`, which asserts against firmware source
because that is the only automated seam available for Arduino code here.

## Working style

- Prefer small, test-backed edits. Add a test for any behaviour that was
  silently wrong before.
- Look up facts in the repo and in the logs under `phase3a_logs/` rather than
  assuming. Several long-standing problems here were visible in the data.
- Keep firmware, Python and docs behaviourally aligned; a change in one layer
  can silently invalidate another.
- Label experimental or approximate results clearly.
- When a doc contradicts an ADR, the ADR wins and the doc needs updating.
