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
- [docs/adr/](file:///d:/Here/asd/docs/adr/) (Architecture decision records — why the code is the way it is, including rejected alternatives. Read the index before proposing a change in an area an ADR already covers.)

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
- Launching the Tkinter debug UI (`tree_ert_app.py`) — frozen as of ADR-0024, bug fixes only.

The PyQt6 capture-session UI is `tree_ert_qt.py` (`--demo` / `--port`). It runs on Windows and on
Linux/Raspberry Pi, writes run folders, and is where new UI work goes. Presentation numbers live
in `tree_ert/capture_view.py`, which imports no UI toolkit — put displayed values there, not in a
widget.

If modifying it:
- Keep pure logic testable.
- Extend tests in `tests/test_phase3a_unified_reconstruct.py`.

Preferred verification:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --help
```
*(Note: adjust python path if your environment differs).*

## Capture Records

Every new capture writes a **run folder**, not a flat CSV, under the **`scans/`** root:
`scans/runs/<timestamp>-<label>/` holding `conditions.json` + `conditions.md`, `frames.csv`
(every frame, unaveraged), `raw/frame-NNN.txt` and `media/`. `run_record.py` owns this;
ADR-0023 and ADR-0025 have the reasoning.

`scans/` also holds `index.csv` (one row per scan — conditions, settings, reciprocity, noise
floor, and an outcome of complete/cancelled/failed) and `session.log` (append-only, everything
the UI printed, including the warmup frames and failures that never reach `frames.csv`).

**`scans/` and `phase3a_logs/` are not interchangeable.** Everything under `scans/` has a
conditions sheet; the ~190 flat CSVs in `phase3a_logs/` do not. Keeping them separate is what
makes that checkable by looking. Do not write new captures into `phase3a_logs/`.

Do not average frames at capture time and do not drop the raw serial text. Frame-to-frame spread
*is* the noise floor, and the noise floor is what licenses any detection claim. The flat
`phase3a-<pattern>-<stamp>.csv` files from the CLI and Tkinter paths are the legacy layout and
record nothing about the specimen.

The physical conditions are not optional metadata. `grounding` in particular is the discriminator
for the CMRR hypothesis behind the 57.5 percent reciprocity violation (ADR-0021), and a run whose
grounding state was not noted cannot join that comparison at all.

## Saline Tank Phantom

A circular saline tank with twelve stainless nails now exists. It is ADR-0018's deferred phantom:
the constraints that shelved it in ADR-0019 were about the trunk, not about a separate tank.

Conventions, all with ADRs:

- **Electrodes are short bare tips**, roughly 3-5 mm wetted, in tank *and* tree (ADR-0020). This
  matches the published tree-ERT method of inserting only to the outer sapwood. Do not propose
  insulating the shaft — that is borehole geophysics practice and is off-method here.
- **The medium is titrated with the instrument** (ADR-0022): tap water, salt added in measured
  increments, watching for `I_HIGH`/`I_LOW` flags and keeping drive voltage under the 3 V
  `MAX_MUX_VOLTAGE_MV` cap. More salt is not better: heavy brine collapses sense voltages into the
  ADC step size, which is the quantisation failure recorded in `docs/validity-audit.md`.
  **ADR-0022's 200 ohm - 2 kohm target band is superseded** (ADR-0026) - it was set from a
  misread illustration, and the measured trunk baseline median is 9.4 ohm. Judge the medium by the
  quantisation check, not by a resistance band.
- The tank is **diagnostic before pictorial**. Reciprocity, symmetry under rotation, monotonic
  decay and noise/drift come first; images come after those read clean. Symmetry and decay have
  no automated check yet — they are analysed by hand until the first session shows what a healthy
  tank looks like on this instrument.

## Reconstruction

Difference imaging only. Absolute reconstruction stays unlicensed while the 57.5 percent
reciprocity violation is open (ADR-0017, ADR-0018) - a difference image survives that fault only
because a systematic error stable between the two captures subtracts out.

The Qt UI images on a **session-baseline** model (ADR-0026): the first completed run of a session
is the baseline, later runs are differenced against it, and each imaged run stores
`reconstruction.png`, `.npz` and `.txt` in its own folder. Baseline and target must share
pattern, current range, DAC, settle, samples and electrode mapping - a mismatch is refused
outright, not annotated.

A difference image shows only what *changed*. A feature present in both states - the drilled void
in the trunk specimen - subtracts out and is structurally invisible (ADR-0019). A flat image means
either nothing changed or the change was below the instrument's resolution, and the figure cannot
tell those apart; the control panel beside it is what separates those cases.

**A diseased tree has no baseline** (ADR-0028). Decay is present in every capture of it, so no
difference image of a single visit can show disease. The thesis's headline capability needs
*absolute* reconstruction, which is blocked on reciprocity - so reciprocity is on the critical path
to the thesis, not just to instrument quality. Never present a difference image of a living tree as
showing decay; it shows change between two captures. Work order: contacts, then reciprocity, then
baseline strategy.

**Every image is rendered beside a control** - the baseline's frames split in half and differenced
against themselves (ADR-0027). Nothing changed between those halves by construction, so the
control is what noise looks like through this solver, in the same units, on one shared colour
scale. `significance` is the ratio of the two peaks; under 2.0 the image is reported as
indistinguishable from noise. This is not optional decoration: on 2026-09-16 an unchanged
specimen produced a strong structured image that scored 1.74x and whose control panel was visually
identical - the pattern was the instrument's own signature, not the tree.

Do not present a difference image without its control, do not scale the panels independently, and
do not remove the magnitude caption. An auto-scaled image of noise is indistinguishable from an
auto-scaled image of signal.

A significance above 2.0 is **not** a detection and must not be reported as one. It is a ratio of
two peak magnitudes with no statistical meaning - not a p-value.

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
- `b<hex>` set the MCP4725 I2C address (`b60` / `b61`); `b` alone reports it. The A0
  strap picks the low address bit and this board has scanned at both, so firmware
  probes 0x61 then 0x60 at boot and the debug UI re-binds it from a scan on connect
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
1. **I2C Scan**: Confirm MCP4725 at `0x61` and ADS1115 at `0x48`.
2. **Shunt Value**: Confirm physical shunt matches the firmware constant. Measured 97.9 ohm on 2026-08-27; `DEFAULT_SHUNT_OHMS` is `97.9f`. Do not expect `100.0`.
3. **Current Pump Output**: Confirm DAC commands change current cleanly on dummy loads.
4. **Mux/Electrode Verification**: Test channels C0-C11 electrically before trusting tank data.
5. **Phantom Control Run**: Run `--control` on a saline phantom and verify stable drift.
6. **Reconstruction**: Only after the above are stable, trust difference images.

## Recording Decisions (ADRs)

**Every non-obvious decision in this repo is recorded as an ADR in `docs/adr/`.** Write it as
part of the change that implements the decision — not afterwards, and without waiting to be
asked.

Write one when a decision:
- changes what a reconstruction image means, or how it must be read
- picks a threshold, constant, or tolerance whose value is a judgement call
- rejects a more obvious approach for a non-obvious reason
- accepts a known limitation instead of fixing it
- changes the serial protocol, the capture procedure, or the measurement methodology
- affects a claim the thesis makes about what the instrument can do

Skip it for routine refactors, typo fixes, test-only additions, and dependency bumps. When
unsure, write it — a redundant ADR costs five minutes, a missing one costs a re-derivation.

Process:
1. Copy `docs/adr/template.md` to `docs/adr/NNNN-short-kebab-title.md`, next free number.
2. Fill in Context / Decision / Rationale / Consequences / Verification. Name the rejected
   alternatives explicitly. State known imperfections rather than hiding them.
3. Add a row to the index table in `docs/adr/README.md`.
4. Cite the ADR number in the commit message that implements it.

Accepted ADRs are immutable. Supersede with a new ADR rather than editing an old one — the
reasoning behind a reverted decision has to survive too.

## Working Style

When changing code:
- Record the decision as an ADR (see above) whenever it meets the bar.
- Prefer small, test-backed edits.
- Preserve the user's current wiring assumptions unless explicitly changing hardware design.
- Keep docs in sync with code.
- Always check hardware limitations (e.g., max current headroom) before writing overly aggressive data filters.
- If a result is experimental or approximate, label it clearly.
