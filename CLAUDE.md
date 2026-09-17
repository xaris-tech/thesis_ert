# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DC Electrical Resistance Tomography (ERT) research prototype for controlled testing on living coconut trees. Current phase: **Phase 3A** — 12-electrode full-mesh dynamic switching (adjacent/opposite/skip-1/skip-2 drive patterns) via ESP32-S3 firmware, difference-image reconstruction via PyEIT on the Python side.

**Read `AGENTS.md` first** — it is the canonical source for domain truths (what the hardware can/cannot currently do), the serial `FRAME` protocol contract, the debugging/validation ladder, and firmware serial commands. Do not duplicate or contradict it; this file covers commands and code architecture only.

Other key docs: `HANDOVER.md` (hardware/software reality), `CONTEXT.md` (thesis terminology), `docs/first-working-prototype/` (build/pinout details), `docs/drift-tuning-presets.md`, `docs/current-setup-validation-runbook.md`, `docs/planned-improvements.md` (agreed-but-unimplemented firmware/GUI work queue, plus measured hardware findings that motivate it — read before proposing changes in these areas), `docs/validity-audit.md` (2026-08-27 independent review: 5 reproduced defects, 3 architectural limits, and what was verified correct — read before trusting a reconstruction image or citing a capability), `docs/adr/` (architecture decision records — why things are the way they are).

## Architecture Decision Records — mandatory

**Every non-obvious decision made in this repo gets an ADR in `docs/adr/`, written as part of the change that implements it, not afterwards.** This is not optional and does not require the user to ask for it.

Write one when a decision changes what a reconstruction image means, picks a judgement-call threshold or constant, rejects a more obvious approach, accepts a known limitation instead of fixing it, changes the serial protocol or capture methodology, or affects a claim the thesis makes about the instrument. Skip it for routine refactors, typo fixes, and dependency bumps. When unsure, write it.

Process: copy `docs/adr/template.md` to `docs/adr/NNNN-short-kebab-title.md` with the next free number, fill in Context / Decision / Rationale / Consequences / Verification, add a row to the index table in `docs/adr/README.md`, and cite the ADR number in the commit message. Accepted ADRs are immutable — supersede with a new one rather than editing. `docs/adr/README.md` has the full convention.

## Commands

Run from repo root, using the project venv:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run a single test file or case:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase3a_unified_reconstruct -v
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_controller.SomeTestClass.test_something -v
```

Run the live acquisition CLI or the debug UI:

```powershell
.\.venv\Scripts\python.exe phase3a_unified_reconstruct.py --help
.\.venv\Scripts\python.exe tree_ert_app.py --demo      # Tkinter UI without hardware (frozen, ADR-0024)
.\.venv\Scripts\python.exe tree_ert_app.py --port COM3 # Tkinter UI against real ESP32-S3
.\.venv\Scripts\python.exe tree_ert_qt.py --demo       # PyQt6 capture-session UI, no hardware
.\.venv\Scripts\python.exe tree_ert_qt.py --port COM3  # PyQt6 UI against real ESP32-S3
```

No linter/formatter is configured in this repo; there is no build step (pure Python + Arduino `.ino` firmware flashed via Arduino IDE/PlatformIO).

## Architecture

**Two parallel layers: firmware (C++/Arduino) and host tooling (Python).** They communicate over serial using the line-based `FRAME` protocol documented in AGENTS.md — any change to the protocol on one side requires a matching change on the other, plus test updates.

### Firmware (`firmware/`)

Multiple generations exist side by side; only one is active:
- **Active**: `firmware/esp32s3-phase3a-unified-arduino/esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino` — emits v2 `FRAME` records, supports adjacent/opposite/skip-1/skip-2 pattern switching and runtime-tunable DAC/settle/discharge/sample-average/current-range/shunt via serial commands. Forward and reverse are interleaved per sense pair (not run as two passes) to suppress electrode polarisation; DAC ceilings are enforced per selected current range.
- Older generations (`esp32s3-phase2*`, `esp32s3-phase3a-arduino`, `esp32s3-phase3a-adjacent-arduino`, `esp32s3-phase3a-opposite-arduino`, `esp32s3-hcp-test-arduino`) are prior iterations kept for reference/history, not for new work. Each has its own README with pinout/wiring for that generation.

### Python host tooling

Two generations coexist here too:

- **`phase3a_unified_reconstruct.py`** (main/active) — parses v2 `FRAME` blocks into `UnifiedFrame`/`MeasurementRecord`, verifies baseline stability (RMS + correlation via `assess_baseline_stability`/`require_stable_baseline`), scores per-pair/per-frame health (`analyze_baseline_pair_health`, `filter_frame_vector_best_effort`), tracks control-run drift (`analyze_control_drift` → `ControlDriftReport`), and drives the CLI capture loop (`capture_vectors`/`capture_average`) plus CSV/report writers and reconstruction plotting.
- **`phase3a_reconstruct.py`** — shared PyEIT plumbing: builds `PyEITProtocol` variants (`build_adjacent_protocol`, `build_opposite_protocol`, `build_skip_one_protocol`, `build_skip_two_protocol`), `create_solver` (mesh + JAC solver), `reconstruct_difference`, and CSV frame logging (`FrameLogger`). `phase3a_unified_reconstruct.py` imports this module as `base` for mesh/solver/reconstruction — don't reimplement solver setup elsewhere.
- **`phase3a_reconstruct_opposite.py`** — thin standalone CLI wrapper around `phase3a_reconstruct` for opposite-drive-only capture (a Phase-2-era entry point; the unified tool now covers this case for Phase 3A).
- **`ert.py`** — legacy `SCAN:`-protocol tool, deprecated, do not extend.
- **`dummy_load_sweep.py`** — bench tool, not part of the capture path. Drives the firmware `d` (debug hold) command, which emits a `HOLD` record read through the instrument's own shunt, and fits `I = Vth / (Rout + Rload)` across hand-fitted resistors to measure the current source's output impedance (ADR-0015). `measure` runs one resistor, `fit` solves across the CSV they append to.
- **`pyeit_analyzer.py`** — offline analysis of exported `.npz`/`.csv` capture files (`load_export`, `summarize_export`, `plot_export`), independent of the live serial path.

### `tree_ert/` package — Tkinter debug UI

Layers, thin-to-thick:
- `tree_ert/settings.py` — `UiSettings` dataclass (port, pattern, dac, settle_ms, samples, warmup/baseline/frame counts, logging) with `validate()`; the single source of truth for UI-configurable capture parameters.
- `tree_ert/acquisition.py` — `Acquisition` protocol with two implementations: `SerialAcquisition` (real ESP32-S3 over `pyserial`, sends firmware commands from `settings`, delegates frame parsing to `phase3a_unified_reconstruct.request_frame`) and `DemoAcquisition` (deterministic synthetic frames for `--demo`, no hardware). Controller code is written against the `Acquisition` protocol so both are interchangeable.
- `tree_ert/controller.py` — `DebugController` state machine (`ControllerState`: disconnected → connected → configured → baseline_ready → target_ready / stopped / failed) orchestrating connect/configure/capture_baseline/capture_control/capture_target/tune_drift/run_self_test against an `Acquisition`. `run_self_test` collects the evidence (a `?` reply, an I2C scan, a few frames) and hands it to the pure checks in `tree_ert/selftest.py`; hardware checks are reported SKIP rather than FAIL when there is no connection. Reuses `phase3a_reconstruct.create_solver`/`reconstruct_difference` and `phase3a_unified_reconstruct` scoring/drift functions rather than duplicating logic. `tune_drift` sweeps `drift_tuning_candidates(settings)` (settle/samples/warmup/baseline profiles) and picks the best by lowest max relative RMS drift, then lowest max RMS, then highest min correlation.
- `tree_ert/selftest.py` — per-component sanity checks (`CheckResult`/`SelfTestReport`) covering host protocol/solver/forward-model conventions, firmware `STATUS` and I2C, DAC binding, shunt, current range, PGA autoranging, then one captured frame's shape, polarity interleaving, quality flags, current margin, polarisation, offset domination, voltage quantisation, per-electrode liveness, and frame-to-frame repeatability. Every check is a pure function over already-collected evidence, so the suite is testable with no board attached.
- `tree_ert/capture_view.py` — toolkit-free presentation logic: `record_rows` (one row per measurement, capture order preserved), `frame_summary`/`format_frame_summary` (per-frame health, quality flags, polarity interleaving), `quantisation_report` (how many ADC steps separate each forward/reverse pair — replaces the fixed resistance window, ADR-0026), `reciprocity_summary`, `noise_summary` (per-pair frame-to-frame spread — the detection floor) and `session_summary`. Imports no UI toolkit, so every displayed number is unit-testable. Prefer extending this over computing numbers inside a widget.
- `tree_ert/reconstruction.py` — difference reconstruction between two recorded runs (ADR-0026). `MEASUREMENT_SETTINGS`/`settings_mismatch`/`require_compatible` gate comparability (pattern, current range, DAC, settle, samples, electrode mapping must match; frame and warmup counts need not), raising `SettingsMismatch` rather than annotating the figure. `reconstruct()` averages frames, drops NaN rows from the solver rather than substituting them (ADR-0002), and returns peak value/angle alongside the image. `split_half_control()` differences the baseline's frames against themselves to produce a noise image in the same units, and `significance()` is the ratio of the two peaks (under 2.0 = indistinguishable from noise, ADR-0027). `save_reconstruction()` writes a two-panel PNG (image beside control, one shared colour scale) and an `.npz`, with the magnitude, scale, noise floor and significance printed on the figure. Only difference imaging — absolute stays unlicensed while reciprocity is open.
- `tree_ert/ui.py` — `DebugApp` (Tkinter) wraps a `DebugController`, renders reconstruction previews/control-drift/tuning summaries, and the Self Test tab (one row per check, colour-coded, with a remedy pane and a `Save report` button). Entry point `run_app(demo, port)`. **Frozen (ADR-0024)** — runnable, bug fixes only; new UI work goes to `tree_ert/qt/`.
- `tree_ert/qt/` — PyQt6 front-end (ADR-0024, ADR-0026). `theme.py` holds the light palette, the stylesheet and `frame_state` (semantic status colour; arrow icons are painted to PNG at runtime because Qt cannot render a CSS border-triangle for a styled sub-control). `worker.py` holds `CaptureWorker` (connect, configure, warm up, capture, record, reconstruct — all on a worker thread, reporting by signal; cancellation is cooperative between frames) and `SessionBaseline`. `main_window.py` holds `SettingsPanel`, `ConditionsPanel` and `MainWindow`, with a tabbed right pane (Measurements / Reconstruction). Entry point `tree_ert_qt.py`. Reconstruction follows a **session-baseline** model: the first completed run of a session becomes the baseline and later runs are differenced against it; the baseline itself has no image and the UI says why. Still no self-test tab — that stays in the Tkinter UI.
- `tree_ert_app.py` — CLI entry point (`--demo`, `--port`) that calls `tree_ert.ui.run_app`.

When changing capture/reconstruction logic, prefer extending `phase3a_unified_reconstruct.py` or `phase3a_reconstruct.py` and having `tree_ert/controller.py` consume the change, rather than putting logic directly in `tree_ert/ui.py` or `tree_ert/acquisition.py`. Presentation numbers belong in `tree_ert/capture_view.py`, never in a widget.

### `run_record.py` — per-run capture records

Top-level module (not in `tree_ert/`, because the dependency direction runs `tree_ert` → `phase3a_*` and both the CLI and the Qt UI need it). `RunRecorder`/`create_run` write one self-contained directory per capture under `<scans root>/runs/<timestamp>-<label>/`: `conditions.json` + `conditions.md` (physical conditions, instrument settings, git commit, and an explicit list of fields that were *not* recorded), `frames.csv` (every record of every frame, unaveraged and flushed per frame), `raw/frame-NNN.txt` (verbatim serial text), `media/` (photographs — ground truth for a target run). `Conditions` names the physical fields explicitly: medium, saline g/L, fill depth, water temperature, electrode protrusion, grounding, tank contents, target, electrode map, operator, notes.

Three rules are load-bearing and should not be "optimised" away (ADR-0023): conditions are written when the run **opens**, not when it closes; frames are stored **unaveraged** because frame-to-frame spread is the noise floor; unrecorded fields are **named in the record**. `Conditions.validate()` returns warnings and never raises — a capture already taken must always be recordable. The module deliberately imports nothing from `phase3a_unified_reconstruct` and duck-types the frame it is handed.

The module also owns the scans root itself (ADR-0025): `SessionLog` (append-only `session.log`, one per root, timestamped, banners at session and run boundaries — the UI log pane mirrors into it so closing the window does not lose warmup frames, cancellations or failures) and `append_index_row`/`read_index`/`INDEX_COLUMNS` (`index.csv`, one row per scan with conditions, settings, frame count, reciprocity and noise metrics, git commit, and an `outcome` of complete/cancelled/failed). `RunRecorder.index_row()` builds a run's row from its own conditions and settings so the index cannot drift from `conditions.json`. Treat `INDEX_COLUMNS` as append-only: unknown keys are ignored and missing ones written empty, so adding a column is safe but renaming one breaks every row already written.

The legacy flat `phase3a_logs/phase3a-<pattern>-<stamp>.csv` path still exists and is still used by the CLI and Tkinter UI.

### Data roots

`scans/` is the documented capture series (ADR-0025) and the default for `tree_ert_qt.py` — everything in it has a conditions sheet. `phase3a_logs/` is the legacy root: ~190 flat CSVs with no record of the conditions they were taken under, plus the CLI/Tkinter output. Do not mix them; membership in the documented series is meant to be checkable by looking at the directory. `scans/README.md` documents the layout and how to read `index.csv` for each comparison (titration series, CMRR floating-vs-grounded, detection floor).

### Tests (`tests/`)

One test module roughly per source module (`test_ert.py`, `test_phase3a_reconstruct.py`, `test_phase3a_unified_reconstruct.py`, `test_phase3a_unified_firmware.py`, `test_pyeit_analyzer.py`, `test_run_record.py`, `test_capture_view.py`, `test_tree_ert_controller.py`, `test_tree_ert_qt.py`, `test_tree_ert_selftest.py`, `test_tree_ert_settings.py`, `test_tree_ert_ui.py`) using stdlib `unittest`. `test_tree_ert_qt.py` sets `QT_QPA_PLATFORM=offscreen` and skips cleanly when PyQt6 is absent; it drives `CaptureWorker.run()` synchronously rather than through a `QThread`, so the sequence is deterministic. `test_phase3a_unified_firmware.py` checks firmware source *text* against the Python side via string/regex matching, so a pass is a doc/code sync guard, not behavioral proof. Keep it in sync when touching the unified `.ino`. `test_firmware_compiles.py` additionally *compiles* the active sketch via the Arduino IDE's bundled `arduino-cli` (ADR-0016), skipping when no toolchain is installed; that catches syntax errors, bad identifiers and overflowing builds, but nothing flashes or simulates the firmware, and a wrong pin number or inverted mux enable compiles perfectly. Treat "confirmed on hardware" bench-session notes in `docs/validity-audit.md`/`docs/planned-improvements.md` as the real behavioral evidence.

### Data dirs

`scans/`, `phase3a_logs/` and `exports/` hold run-time generated output, not source — safe to ignore when mapping code structure. See **Data roots** above for which is which.
