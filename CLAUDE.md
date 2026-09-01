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
.\.venv\Scripts\python.exe tree_ert_app.py --demo      # UI without hardware, deterministic frames
.\.venv\Scripts\python.exe tree_ert_app.py --port COM3 # UI against real ESP32-S3
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
- **`pyeit_analyzer.py`** — offline analysis of exported `.npz`/`.csv` capture files (`load_export`, `summarize_export`, `plot_export`), independent of the live serial path.

### `tree_ert/` package — Tkinter debug UI

Layers, thin-to-thick:
- `tree_ert/settings.py` — `UiSettings` dataclass (port, pattern, dac, settle_ms, samples, warmup/baseline/frame counts, logging) with `validate()`; the single source of truth for UI-configurable capture parameters.
- `tree_ert/acquisition.py` — `Acquisition` protocol with two implementations: `SerialAcquisition` (real ESP32-S3 over `pyserial`, sends firmware commands from `settings`, delegates frame parsing to `phase3a_unified_reconstruct.request_frame`) and `DemoAcquisition` (deterministic synthetic frames for `--demo`, no hardware). Controller code is written against the `Acquisition` protocol so both are interchangeable.
- `tree_ert/controller.py` — `DebugController` state machine (`ControllerState`: disconnected → connected → configured → baseline_ready → target_ready / stopped / failed) orchestrating connect/configure/capture_baseline/capture_control/capture_target/tune_drift against an `Acquisition`. Reuses `phase3a_reconstruct.create_solver`/`reconstruct_difference` and `phase3a_unified_reconstruct` scoring/drift functions rather than duplicating logic. `tune_drift` sweeps `drift_tuning_candidates(settings)` (settle/samples/warmup/baseline profiles) and picks the best by lowest max relative RMS drift, then lowest max RMS, then highest min correlation.
- `tree_ert/ui.py` — `DebugApp` (Tkinter) wraps a `DebugController`, renders reconstruction previews/control-drift/tuning summaries. Entry point `run_app(demo, port)`.
- `tree_ert_app.py` — CLI entry point (`--demo`, `--port`) that calls `tree_ert.ui.run_app`.

When changing capture/reconstruction logic, prefer extending `phase3a_unified_reconstruct.py` or `phase3a_reconstruct.py` and having `tree_ert/controller.py` consume the change, rather than putting logic directly in `tree_ert/ui.py` or `tree_ert/acquisition.py`.

### Tests (`tests/`)

One test module roughly per source module (`test_ert.py`, `test_phase3a_reconstruct.py`, `test_phase3a_unified_reconstruct.py`, `test_phase3a_unified_firmware.py`, `test_pyeit_analyzer.py`, `test_tree_ert_controller.py`, `test_tree_ert_settings.py`, `test_tree_ert_ui.py`) using stdlib `unittest`. `test_phase3a_unified_firmware.py` checks firmware source *text* against the Python side via string/regex matching — it does not compile, flash, or simulate the firmware, so a pass is a doc/code sync guard, not behavioral proof. Keep it in sync when touching the unified `.ino`; treat "confirmed on hardware" bench-session notes in `docs/validity-audit.md`/`docs/planned-improvements.md` as the real behavioral evidence.

### Data dirs

`phase3a_logs/` and `exports/` hold run-time generated CSV/NPZ/plot output, not source — safe to ignore when mapping code structure.
