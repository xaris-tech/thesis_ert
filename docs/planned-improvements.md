# Planned Improvements — Phase 3A

This document records improvements agreed during the 2026-08-27 bench session, covering
both the unified ESP32-S3 firmware and the Python host tooling / Tkinter debug UI. It is a
work queue and a rationale record. For canonical current behaviour see `AGENTS.md` and
`HANDOVER.md`.

Each item states what it does, why it is needed, and where it belongs in the codebase.
Implementation order is proposed at the end.

## Status

Implemented on 2026-08-27: **F1, F2, F3, F4, F5, F8, R1, R2, R3, R5, R6, R8, R9, R10,
R11, R12, R13**, plus an emergency stop (R17) not in the original list. F8 (electrode-voltage
PGA autoranging) was not in the original list either; it came out of the first on-hardware
probe after F1 landed.

Still outstanding: **F6, F7, R4, R7, R14, R15, R16, D1, D2, D3**.

Implemented items are marked `[done]` in the sections below. Note that the firmware
changes have been written and unit-tested against the source, but at the time of writing
the board had **not yet been reflashed** — the polarisation and offset fixes are unverified
on hardware.

---

## 1. Motivation — measured findings, 2026-08-27

These bench measurements motivate most of the items below. They are recorded here rather
than in `HANDOVER.md` because some warrant independent confirmation before being treated as
canonical hardware truths.

### 1.1 Current pump has low output impedance

Dummy-load sweep at a fixed DAC code, measured through the full mux and shunt path:

| Load | Measured current |
|---:|---:|
| 10 kohm | ~36 uA |
| 4.7 kohm | ~72.5 uA |

Current tracks `1/R_load`, which is constant-voltage behaviour, not constant-current.
Solving both points as a single Thevenin source:

```text
Rout + Ron(mux) ~= 430 ohm
Vth             ~= 0.38 V   (at the DAC code used for that sweep)
```

A later run at a lower DAC code gave `Vth ~= 0.262 V`, with both loads agreeing on that
figure within 1 percent — so the source model is linear and repeatable.

For a current source, `Rout` must be much larger than the load. At roughly 430 ohm it is
well below the 4.7-10 kohm dummy loads, so the load sets the current.

Cause is leg mismatch in the Improved Howland network. Output impedance goes roughly as
`Rout ~= Rs / e`, where `e` is the relative mismatch between `R2/R1` and `R4/R3`. With
`Rs = 10.2 ohm` measured and `Rout ~= 300-430 ohm`, `e` is around 2-3 percent — consistent
with the non-0.1-percent resistors actually fitted. `Rs = 10 ohm` (the HIGH range) is the
least forgiving value in the range table; `docs/first-working-prototype/03-howland-current-source.md`
specifies starting on LOW (68 ohm).

> **Cause re-identified 2026-09-02 by
> [ADR-0014](adr/0014-current-sense-feedback-tapped-before-rs.md).** The measurements in this
> section are correct and are the strongest retrospective evidence for that ADR, but the
> causal claim below - leg mismatch - is wrong. OPA2134 pin 5 is tied to pin 1 instead of
> `I_SRC_OUT`, so the loop never sensed current. The `Rout ~= 430 ohm` measured here is simply
> `Rs` plus two mux `Ron`, with no regulation at all.
>
> **Withdrawn 2026-09-02 by [ADR-0013](adr/0013-repair-howland-ratio-match.md).** The claim
> below was made before the individual resistors were measured. They since were: R1 is 4.498k
> and R3 is 5.022k against a shared 5.00k nominal, giving `e = 10.7%` and `Rout = 94 ohm`, not
> the 2-3% and 430 ohm estimated here. At that mismatch the pump drives `I_SRC_OUT` to 3.86 V,
> past the 3.3 V mux supply, so it is a defect to repair and not a property to design around.

~~The resistors are soldered and cannot practically be reworked or trimmed, so this is now a
fixed property of the rig to design around rather than a defect to repair.~~

Consequence to design around: difference imaging still works, because
`paired_transfer_resistance()` normalises each measurement by its own measured current. The
real limit is that a high-impedance load (a living tree, as opposed to a saline phantom)
pulls current down toward the noise floor.

### 1.2 Electrode polarisation in saline

Within a single fixed injection pair (E1 to E2), with drive electrodes unchanged, measured
current decayed monotonically across successive measurements:

```text
FWD:   338 -> 138 -> 79 -> 54 -> 42 -> 32 -> 25 -> 19 -> 15.6 uA
REV:  1572 -> 943 -> 656 -> 478 -> 362 -> 282 -> 228 -> 189 -> 159 uA
```

Current cannot legitimately depend on which unrelated pair is being voltage-sensed, so this
is time-dependent behaviour: DC through metal electrodes in electrolyte builds an ionic
double layer that opposes the drive. The low output impedance from 1.1 means that
counter-EMF translates directly into lost current.

The REV spike is the same effect in reverse. `emitPolarity()` runs all nine FWD measurements
before any REV measurement, so by the end of the FWD block the electrodes are strongly
polarised; flipping polarity makes the stored counter-EMF briefly aid the drive, producing
the 1572 uA reading (flagged `I_HIGH`), which then decays as polarisation reverses.

### 1.3 Voltage readings are offset-dominated

Comparing FWD and REV on identical sense pairs from the same frame:

| Sense pair | FWD (mV) | REV (mV) |
|---|---:|---:|
| E5-E6 | 10.000 | 10.000 |
| E7-E8 | 46.000 | 46.000 |
| E8-E9 | -28.000 | -28.000 |

Reversing the injected current must invert the sign of an IR drop. These do not move,
indicating the readings are dominated by static electrode half-cell potential rather than by
the injected signal.

This matters more than 1.1 or 1.2: `paired_transfer_resistance()` computes
`0.5 * (fwd_resistance - rev_resistance)` specifically to cancel that offset. When
`V_fwd` approximately equals `V_rev`, the result collapses toward zero and no usable
transfer resistance survives. Nothing in the current tooling warns about this.

### 1.4 A single bad measurement destroys a whole capture

`validate_record()` (`phase3a_unified_reconstruct.py:165`) raises on any record whose quality
is not `OK`, and `paired_transfer_resistance()` calls it on every record. One `I_LOW` among a
frame's 216 measurements aborts the capture in progress.

At `n16` a frame takes roughly 15-20 seconds, so the default 10 warmup plus 10 baseline
frames is about 6 minutes of work that a single weak measurement can discard.

Relevant thresholds:

| Constant | Value | Location |
|---|---:|---|
| `MIN_CURRENT_UA` (sets `I_LOW`) | 1.0 uA | firmware line 13 |
| `MIN_VALID_CURRENT_UA` | 0.5 uA | host line 22 |
| `MAX_BASELINE_RELATIVE_RMS_PERCENT` | 2.0 % | host line 26 |
| `MAX_BASELINE_ABSOLUTE_RMS_KOHM` | 0.002 kohm | host line 27 |
| `MIN_BASELINE_CORRELATION` | 0.995 | host line 28 |

The firmware's 1.0 uA threshold binds first.

---

## 2. Firmware improvements

Target: `firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino`.

Any change here that alters serial output must be matched in
`phase3a_unified_reconstruct.py` and in `tests/test_phase3a_unified_firmware.py`, per the
protocol contract in `AGENTS.md`.

### F1. [done] Interleave forward and reverse polarity per measurement

Currently `emitFrame()` calls `emitPolarity("FWD", ...)` for all sense pairs, then
`emitPolarity("REV", ...)` for all sense pairs. Restructure so each sense pair is captured
FWD then REV back to back before moving to the next pair.

Two benefits:

- Net DC per electrode stays near zero across the frame, so polarisation never accumulates
  (addresses 1.2 at source).
- FWD and REV for a given pair are separated by milliseconds instead of seconds, which
  substantially improves the offset cancellation in `paired_transfer_resistance()`
  (addresses 1.3).

Record order within the frame changes. Verify `parse_v2_frame()` and
`paired_transfer_resistance()` are order-independent before relying on this; they key
records by pair rather than position, but this must be confirmed and covered by a test.

This is the single highest-value change in this document.

### F2. [done] Inter-measurement discharge interval

Add a configurable idle period after `enterSafeIdle()` and before the next
`configureDriveAndSense()`, allowing the electrode double layer to relax between
measurements. Expose as a serial command alongside `t` (settle).

Complements F1: F1 prevents accumulation, F2 gives what does accumulate time to decay.

### F3. [done] Correct the MCP4725 fatal-error message

`configureI2CDevices()` uses `MCP4725_ADDRESS = 0x61` (line 9) but prints
`"[FATAL] MCP4725 not found at 0x60"` (line 382). The message is wrong and will mislead
anyone debugging a bus fault. Print the actual constant.

Note the wider discrepancy: `PHASE_3A_PINOUT_TABLES.md` and
`docs/first-working-prototype/04-complete-pinout-and-wiring.md` both state the ADDR pin is
tied to ground for address `0x60`, but the hardware answers at `0x61` and this is confirmed
working. Either the docs or the wiring is stale — see D2.

### F4. [done] Match the shunt constant to the measured shunt

`SHUNT_OHMS = 100.0f` (line 12); the fitted shunt measures 97.9 ohm. This is a flat 2 percent
error on every current reading. Either correct the constant or, preferably, make it settable
at runtime and reported in `STATUS` so the value used is always recorded with the data.

Already tracked in `TODO.md` as an open hardware-verification item.

### F5. [done] Enforce the DAC ceiling for the fitted Rs range

`MAX_DAC_CODE` is a single fixed 620.
`docs/first-working-prototype/03-howland-current-source.md` requires the firmware and app to
enforce the maximum DAC code associated with the physically selected Rs jumper:

| Range | Rs | Max DAC code | Approx max current |
|---|---:|---:|---:|
| LOW | 68 ohm | 420 | 100 uA |
| MEDIUM | 22 ohm | 680 | 500 uA |
| HIGH | 10 ohm | 620 | 1.0 mA |

Add a range setting, enforce the matching ceiling, and report the active range in `STATUS`.
This is a safety item: it exists to prevent commanding a current the fitted hardware was not
validated for.

### F8. [done] Autorange the electrode-voltage PGA

`readVoltageMv()` used a fixed `GAIN_ONE` (+/-4096 mV). The first on-hardware probe after F1
showed every electrode voltage in a saline frame under 250 mV, so roughly 94 percent of the
ADC's range went unused and one step was 125 uV - larger than the injected IR drop on pairs
far from the injection pair. Forward and reverse then returned the *same* ADC code and their
difference was exactly zero, which the host reports as an offset-dominated pair.

Each voltage read now takes one throwaway conversion on the widest range to size the signal,
selects the tightest of `GAIN_SIXTEEN`/`GAIN_EIGHT`/`GAIN_FOUR`/`GAIN_TWO`/`GAIN_ONE` that
fits it with 25 percent headroom, and runs the averaged read there; if the signal grows
between the two reads and the tight range clips, it falls back to the widest range and
re-reads. `a1`/`a0` toggle it, and `?` reports `VGAIN_AUTO` and `VRANGE_MV`.

Autoranging is also what makes F4 (D-04, the averaging fix) do anything: at `GAIN_ONE` all
16 samples returned identical counts, so there was no dither to average against. A tighter
range turns sub-LSB noise into several LSBs.

Cost is one extra conversion per measurement, roughly 0.26 s across a 216-measurement frame.

The current-sense channel is deliberately left alone: it already uses `GAIN_SIXTEEN`, and
1 mA across the shunt stays well inside +/-256 mV.

### F6. Runtime-configurable quality thresholds

`MIN_CURRENT_UA` and `MAX_CURRENT_UA` are compile-time constants. Make them settable and
report them in `STATUS`, so a rig with known-low current can be characterised without
reflashing.

### F7. Report range and shunt metadata in the FRAME header (optional)

Adding shunt value and Rs range to the `FRAME` header would make every logged capture
self-describing. This changes the protocol and therefore requires a version bump plus
matching parser and test changes. Deferred unless the logging requirement (R4) proves
insufficient on its own.

---

## 3. Host and GUI improvements

Per `CLAUDE.md`, analysis logic belongs in `phase3a_unified_reconstruct.py`, with
`tree_ert/controller.py` consuming it and `tree_ert/ui.py` staying a thin presentation layer.

### Tier 1 — Stop losing runs

**R1. [done] Pre-flight single-frame probe.**
A button that captures exactly one frame with no warmup and no stability gate, reporting the
minimum current across the whole frame, which injection/sense pair produced it, the margin
against `MIN_CURRENT_UA`, and a count of each quality flag.

The minimum current across a frame — not the average — predicts whether a long capture will
survive, because the weakest single measurement is what aborts it. Averages conceal exactly
the pair that causes the failure.

New `probe_frame()` on the controller; summary formatter in `phase3a_unified_reconstruct.py`.

**R2. [done] Quality-tolerant capture mode.**
An option to exclude and record bad measurements instead of raising (see 1.4). Should reuse
the existing `filter_frame_vector_best_effort()` scoring rather than introduce a parallel
mechanism. Requires a strict/lenient flag on `paired_transfer_resistance()` and a
corresponding `UiSettings` field.

Note this is a different failure from an unstable baseline: `allow_unstable_baseline` already
rescues the stability gate (`require_stable_baseline`, line 691), but an `I_LOW` raises
earlier, inside `frame_to_vector`, and is not covered by it.

**R3. [done] Live per-frame stability readout.**
Display relative RMS and correlation for each baseline frame as it arrives, against the
2.0 percent and 0.995 limits, so an obviously diverging run can be aborted at frame 3 instead
of running to completion and then raising.

**R4. Always-on raw logging with a run manifest.**
Log by default rather than opt-in, and record DAC, settle, samples, pattern, shunt value,
min/median current, and the stability summary for every run. A failed run then still yields
usable raw data for offline analysis via `pyeit_analyzer.py`.

Already requested in `TODO.md`.

### Tier 2 — Surface the physics

**R5. [done] Polarisation detector.**
Within each fixed injection pair, fit measured current against measurement index and flag
monotonic decay beyond a threshold, reporting the first-to-last decay ratio. Addresses 1.2,
which is currently invisible without reading raw serial output line by line.

**R6. [done] Forward/reverse offset-domination check.**
Per sense pair, compare `V_fwd` against `V_rev` and flag pairs that fail to invert — for
example when `|V_fwd + V_rev|` is large relative to `|V_fwd - V_rev|`. Report the affected
fraction of pairs.

This is the highest-priority diagnostic in Tier 2. Per 1.3 it determines whether
reconstruction is possible at all, and it currently fails silently.

**R7. Per-measurement current table.**
A grid of measured current indexed by injection pair against sense pair, coloured by margin
to the threshold. Replaces manual inspection of raw dumps and makes weak electrodes
immediately visible.

**R8. [done] Per-electrode health summary.**
For each electrode, aggregate median current when driving, median when sensing, and outlier
count. Already requested in `TODO.md`, which flags E9 and E10 as known suspects.

### Tier 3 — Speed and friction

**R9. [done] Serial port auto-detect.** `UiSettings.port` defaults to `COM3`; the actual device
enumerated as `COM7`. Enumerate available ports, present a dropdown, indicate which are busy.

**R10. [done] Built-in command console.** Send raw firmware commands (`s`, `?`, `i`, `d`, `x`) and
view replies without leaving the GUI. `SerialAcquisition.send_command()` already exists
(`tree_ert/acquisition.py:107`) and is currently unused by the UI. Avoids switching to the
Arduino Serial Monitor, which holds the port exclusively and blocks the GUI from connecting.

**R11. [done] Persist settings between sessions.** Save and restore the last-used `UiSettings` to
JSON, instead of re-entering DAC, settle, and sample values on every launch.

**R12. [done] Frame ETA and progress bar.** Estimate from measured frame duration and show elapsed
and remaining time for the full warmup plus baseline sequence.

**R13. [done] Abort that preserves partial data.** `stop()` currently raises `"capture stopped"` and
discards everything captured so far; it should return the partial result.

**R17. [done] Emergency stop.**
A second, harder stop next to the existing one. `DebugController.emergency_stop()` forces
the DAC idle and the muxes disabled, closes the serial port, clears protocol/solver/baseline
state, and returns to `DISCONNECTED`. Every step is attempted even if an earlier one raises,
and failures are returned rather than thrown, so one broken step cannot skip the rest.

The UI button also clears the busy flag unconditionally. The ordinary STOP leaves that flag
set until the worker thread unwinds, which locks every control if a capture is wedged;
after an emergency stop the port is closed, so a worker still unwinding cannot do anything
further and the flag is safe to drop.

**R18. [done] Substitution toggle and per-frame pair reporting.**
`filter_frame_vector_best_effort` writes the baseline value into any pair whose change
exceeds `MAX_RECON_PAIR_DELTA_KOHM = 0.05`, which asserts "nothing changed here" to the
solver. Measured transfer resistances on the saline tank run 0.04-0.23 kOhm, so a genuine
target can exceed that threshold and be discarded as unstable - producing a null image from
good data. This is the failure direction validity-audit D-05 warns about.

Target capture now reports kept/dropped pairs and the quality label for every frame, and
`UiSettings.filter_pairs` (checkbox "Substitute unstable pairs") disables the substitution so
the raw difference can be compared against the filtered one. Default stays on.

Diagnostic first, fix second: if a target run shows large dropped counts, the threshold is
wrong for this rig rather than the data being bad.

### Tier 4 — Characterisation

**R14. DAC margin sweep.** Sweep DAC codes, capture one frame at each, plot minimum current
against code, and recommend the lowest code that meets a target margin. Automates the
question of whether a given code starves the weak pairs, and finds the lowest workable
current — which also minimises polarisation.

**R15. Two-load source characterisation.** A guided flow that captures with two known dummy
loads and solves for `Vth` and `Rout + Ron`, storing the result as a recorded rig property.
This was done by hand in section 1.1; since `Rout` is the rig's defining limitation it should
be a stored number, re-checkable after any hardware change.

**R16. Extend `tune_drift` ranking.** The existing sweep in `tree_ert/controller.py:219`
optimises stability alone. Fold in the polarisation metric (R5) and offset-domination metric
(R6), since a run can show low drift while carrying no usable signal — a false pass under the
current ranking.

---

## 4. Documentation corrections

Separate from the improvements above; these are existing docs that contradict verified
hardware behaviour.

**D1. Stale op-amp table.** The "Current Pump Op Amp" table in `PHASE_3A_PINOUT_TABLES.md`
describes an LM358-era single-amplifier arrangement with amplifier B tied off as unused. The
verified design in `docs/first-working-prototype/03-howland-current-source.md` uses amplifier
B as an active buffer (pin 5 senses the load node, pins 6 and 7 form a follower driving R4).
The pinout table should defer to the Howland document.

**D2. I2C address discrepancy.** Docs state MCP4725 at `0x60` with ADDR tied to ground; the
hardware answers at `0x61` and the firmware is set accordingly. Confirm the physical ADDR
connection, then correct whichever side is wrong. See F3.

**D3. Stale ADS1115 A2/A3 note.** `PHASE_3A_PINOUT_TABLES.md` marks A2 and A3 as "optional
ISENSE_P later, leave open for first build". The current firmware actively reads the A2-A3
differential for current measurement and requires the shunt to be fitted.
`docs/first-working-prototype/04-complete-pinout-and-wiring.md` already has the correct
version.

---

## 5. Cross-cutting requirements

- Every new analysis function gets a unit test in
  `tests/test_phase3a_unified_reconstruct.py`; controller wiring in
  `tests/test_tree_ert_controller.py`; display formatters in `tests/test_tree_ert_ui.py`.
  The repo convention is one test module per source module.
- Firmware behaviour assertions live in `tests/test_phase3a_unified_firmware.py` and must be
  updated alongside any `.ino` change.
- R1 through R16 need no serial protocol change; all are derivable from existing v2 `FRAME`
  records. F1 changes record ordering but not record format. Only F7 changes the protocol
  itself and would require a version bump.
- R2 and R16 change what counts as a passing run, so `docs/drift-tuning-presets.md` and the
  validation ladder in `HANDOVER.md` need updating alongside them.
- Findings in section 1 should be folded into `HANDOVER.md` once independently confirmed, so
  the honest-limits section there reflects the measured output impedance.

---

## 6. Proposed implementation order

1. **F1** — interleaved polarity. Attacks both dominant faults (1.2 and 1.3) at source and
   may change what all subsequent measurements look like, so it should land before tooling is
   tuned against current behaviour.
2. **R1, R2** — cheap probing and tolerant capture. Removes the wasted-run problem and makes
   every later iteration faster.
3. **R6, R5** — offset and polarisation detectors. Confirm whether F1 actually fixed the
   physics, rather than assuming it.
4. **R7, R8** — current table and electrode health. Turns raw dumps into readable diagnosis.
5. **F3, F4, F5** — firmware correctness and safety constants. Small and independent; F5 is
   a safety gate that should precede any work on a living tree.
6. **R3, R4, R13** — live feedback and data preservation.
7. **Tier 3 (R9-R12)** — comfort items, schedulable at any point.
8. **R14, R15, R16** — characterisation, once cheap probing exists to build on.
9. **D1, D2, D3** — documentation corrections, independent of the code work.

F2, F6, and F7 are deferred pending results from F1; if interleaving alone suppresses
polarisation, the discharge interval may prove unnecessary.
