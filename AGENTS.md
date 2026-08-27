# AGENTS.md

## Purpose

This repo is an experimental DC Electrical Resistance Tomography (ERT) prototype aimed at controlled testing on living coconut trees.

The current project state is **Phase 3A**:
- 12-electrode full-mesh dynamic switching (adjacent/opposite drive patterns).
- Hardware: ESP32-S3, MCP4725 DAC, ADS1115 ADC, four CD74HC4067 multiplexers, OPA2134PA Improved Howland Current Pump.
- Inline current measurement and difference image reconstruction via PyEIT.

Agents working in this repo should optimize for:
- Accurate hardware/software handoff (e.g., verifying shunt values and ADC mappings).
- Honest limits about what the current setup can and cannot do (we do difference imaging, not absolute conductivity maps).
- Safe, incremental stabilization of Phase 3A hardware and software.

## Read This First

Start with the authoritative Phase 3A documentation:
- [HANDOVER.md](file:///d:/Here/asd/HANDOVER.md) (Current hardware/software reality and limitations)
- [CONTEXT.md](file:///d:/Here/asd/CONTEXT.md) (Thesis terminology and domain language)
- [docs/first-working-prototype/](file:///d:/Here/asd/docs/first-working-prototype/) (Detailed build instructions and pinouts)
- [phase3a_unified_reconstruct.py](file:///d:/Here/asd/phase3a_unified_reconstruct.py) (Main Python tool)
- [docs/validity-audit.md](file:///d:/Here/asd/docs/validity-audit.md) (Known-broken list with reproductions; D-01 and D-02 affect how every reconstruction image must be read)

## Current Hardware Model (Phase 3A)

Known parts:
- `ESP32-S3`
- `MCP4725` (DAC)
- `ADS1115` (ADC)
- `OPA2134PA` (Improved Howland Current Pump replacing LM358)
- `4x CD74HC4067` (Muxes for I_SRC, I_RET, V_P, V_N)
- `12` electrodes

Current Phase 3A behavior:
- Independent address control for all four muxes.
- Switchable current injection and voltage sensing.
- Inline current measurement across a shunt resistor (ADS1115 A2-A3).

## Truths Agents Should Preserve

Do not overclaim capabilities.

The current setup **can** do:
- Multi-electrode live scanning (adjacent, opposite, etc.).
- Baseline stability tracking and RMS noise filtering.
- Real PyEIT difference reconstructions in a saline phantom.
- Data export to CSV.

The current setup does **not** yet do:
- Reliable absolute conductivity reconstruction.
- Diagnostic disease detection on trees (still gathering validation data).
- Guaranteed uniform current (there are known variations/outliers, e.g. E9/E10).

## Serial Protocol Contract

Phase 3A unified firmware emits `FRAME` records, not Phase 2 `SCAN:` blocks.

Example frame format:
```text
FRAME,2,1,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4
M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,-12.345,I,210.000,Q,OK
M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,12.210,I,208.500,Q,OK
END,1
```
Do not casually change this format unless you also update `phase3a_unified_reconstruct.py` and its tests. The old `ert.py` and `SCAN:` protocol are considered deprecated legacy.

## Python Workflow

[phase3a_unified_reconstruct.py](file:///d:/Here/asd/phase3a_unified_reconstruct.py) is the main live acquisition tool.

Current responsibilities:
- Reading and parsing Phase 3A unified `FRAME` blocks.
- Verifying baseline stability (RMS, correlation).
- Reconstructing PyEIT difference images.
- Generating contact sheets and logging CSVs.
- Launching the Tkinter debug UI ([tree_ert_app.py](file:///d:/Here/asd/tree_ert_app.py)).

If modifying it:
- Keep pure logic testable.
- Extend tests in `tests/test_phase3a_unified_reconstruct.py`.

Preferred verification:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --help
```
*(Note: adjust python path if your environment differs).*

## Firmware Workflow

Active firmware:
- `firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino`

If updating commands or GPIO behavior, make sure to update the README in that directory.

Current serial commands:
- `s` single scan
- `g` continuous scanning on
- `x` continuous scanning off
- `ma` set adjacent pattern
- `mo` set opposite pattern
- `ms` set skip-1 pattern
- `mk` set skip-2 pattern
- `p<number>` set DAC raw value, clipped to the active current range ceiling
- `t<number>` set mux settle time in ms
- `c<number>` set post-measurement discharge time in ms, `0` disables
- `n<number>` set ADC sample averaging count
- `el` / `em` / `eh` select LOW / MEDIUM / HIGH current range
- `j<number>` set the current-sense shunt value in ohms
- `a1` / `a0` enable or disable electrode-voltage PGA autoranging
- `i` scan the I2C bus
- `d` debug hold for multimeter work
- `?` print status
- `h` print help

Forward and reverse measurements are interleaved per sense pair, not run as two
separate passes. Do not restructure this back into per-polarity passes: holding
one polarity across a whole injection pair builds electrode polarisation, which
shows as current decaying across a fixed drive pair and as forward/reverse
voltages that stop inverting - the latter collapses the transfer resistance in
`paired_transfer_resistance()` toward zero.

Firmware enforces the DAC ceiling of the selected current range (LOW 420,
MEDIUM 680, HIGH 620) rather than one fixed limit, and boots in LOW. Set the
range to match the physically fitted Rs jumper.

The electrode-voltage channel autoranges its PGA per measurement rather than
sitting on a fixed `GAIN_ONE`. Do not pin it back to a fixed range: measured
saline voltages are under 250 mV against a 4096 mV fixed range, so one ADC step
was larger than the IR drop on distant pairs and their forward/reverse
difference quantised to exactly zero. The current-sense channel is deliberately
not autoranged - it already uses the finest range.

## Debugging and Validation Priorities

If asked to test or validate, follow the ladder from [HANDOVER.md](file:///d:/Here/asd/HANDOVER.md):
1. **I2C Scan**: Confirm MCP4725 at `0x60` and ADS1115 at `0x48`.
2. **Shunt Value**: Confirm physical shunt matches the firmware constant (10 vs 100 ohms).
3. **Current Pump Output**: Confirm DAC commands change current cleanly on dummy loads.
4. **Mux/Electrode Verification**: Test channels C0-C11 electrically before trusting tank data.
5. **Phantom Control Run**: Run `--control` on a saline phantom and verify stable drift.
6. **Reconstruction**: Only after the above are stable, trust difference images.

## Working Style

When changing code:
- Prefer small, test-backed edits.
- Preserve the user's current wiring assumptions unless explicitly changing hardware design.
- Keep docs in sync with code.
- Always check hardware limitations (e.g., max current headroom) before writing overly aggressive data filters.
- If a result is experimental or approximate, label it clearly.
