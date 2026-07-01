# Phase 3A Hybrid Debug UI Design

## Objective

Build a simple Windows desktop UI for the active Phase 3A ERT workflow so hardware debugging, baseline capture, control drift checks, target runs, logs, and reconstruction previews can be done with real clickable controls instead of terminal-only CLI commands.

The app must support the active `phase3a_unified_reconstruct.py` workflow and the Phase 3A unified firmware serial protocol:

```text
FRAME,2,<id>,<pattern>,DAC,<code>,SETTLE,<ms>,SAMPLES,<count>
M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,-12.345,I,210.000,Q,OK
M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,12.210,I,208.500,Q,OK
END,<id>
```

The app must not silently fall back to the older Phase 2 `SCAN:` parser.

## Chosen Layout

Use the approved `Hybrid Lab Bench` layout:

- Left control rail for connection, configuration, capture actions, export, and emergency stop.
- Right tabbed workspace for `Status`, `Reconstruction`, `Health`, `Serial`, and `Files`.
- Large always-visible `STOP / CURRENT IDLE` control that sends `x` and closes the current path safely.

This layout keeps guided experiment steps visible while still exposing low-level debug information when hardware behavior is confusing.

## User Flow

1. User selects serial port, baud, pattern, DAC code, settle time, sample count, frame counts, diameter label, and log option.
2. User clicks `Connect`.
3. App sends or exposes firmware diagnostic commands: `h`, `?`, and `i`.
4. User clicks `Configure`, which sends pattern, DAC, settle, and sample commands.
5. User clicks `Baseline` to capture warmup and baseline frames.
6. App runs the same stability checks used by `phase3a_unified_reconstruct.py`.
7. User can run `Control Drift` with no target movement to validate repeatability.
8. User can run `Target Run` after placing a controlled object or sample.
9. App displays reconstruction and health metrics and writes logs/images under `phase3a_logs/`.

## Required Controls

- `Connect`: open serial connection.
- `Configure`: send pattern mode command plus `p`, `t`, and `n`.
- `Help`: send `h` and show response in serial tab.
- `Status`: send `?` and show response in serial tab.
- `I2C Scan`: send `i` and show detected devices.
- `Baseline`: capture baseline vectors and show stability result.
- `Control Drift`: capture same-condition frames and show repeatability metrics.
- `Target Run`: capture comparison frames and update reconstruction.
- `Export`: save current run summary and any generated images.
- `STOP / CURRENT IDLE`: send `x` immediately; available in every state.

## Tabs

### Status

Shows connection state, selected pattern, DAC, settle time, sample count, current median, quality labels, baseline stability, and last error.

### Reconstruction

Embeds a Matplotlib reconstruction plot using the existing PyEIT solver path. It should show the average target reconstruction more prominently than any single noisy frame.

### Health

Shows pair and electrode diagnostics:

- baseline RMS per pair
- dropped pair count
- kept pair ratio
- current median and spread
- quality flag counts such as `OK`, `I_LOW`, `I_HIGH`, and `I_REVERSED`
- top unstable electrodes and pairs

### Serial

Shows raw incoming serial lines, parsed frame summaries, and command responses. This tab is for firmware/hardware debugging.

### Files

Shows the latest CSV logs, stability reports, consistency reports, contact sheets, and average reconstruction images generated in `phase3a_logs/`.

## Architecture

Create a new application entry point:

```text
tree_ert_app.py
```

Keep current CLI scripts working. Do not rewrite `phase3a_unified_reconstruct.py` into a UI file.

Add a small `tree_ert/` package only if needed to keep the UI maintainable:

- `tree_ert/acquisition.py`: serial connection, command sending, frame capture worker.
- `tree_ert/controller.py`: UI-safe state machine for configure, baseline, control, and target runs.
- `tree_ert/ui.py`: Tkinter widgets, tabs, event queue, and Matplotlib embedding.
- `tree_ert/demo.py`: deterministic demo data for UI smoke testing without hardware.

Reuse existing functions from `phase3a_unified_reconstruct.py` for parsing, vector conversion, baseline stability, control drift, filtering, reconstruction image saving, and reports. Refactor only when reuse requires a clearer boundary.

## Threading And Safety

The Tkinter main thread must own all widget updates. Serial reads and long captures run in a worker thread and send immutable events through a queue.

The `STOP / CURRENT IDLE` button must be callable even if a capture is in progress. It sends `x`, marks the active capture cancelled, and leaves the UI in a safe stopped state.

All serial exceptions, parse errors, protocol mismatches, and baseline instability messages must be displayed in the UI instead of disappearing into the terminal.

## Validation Boundaries

The app can support approximate Phase 3A difference reconstruction and hardware validation. It must not claim absolute conductivity imaging or diagnostic tree decay detection.

The main validation targets are:

- firmware command response
- I2C device presence
- current level and spread
- baseline repeatability
- per-pair and per-electrode stability
- controlled target response relative to baseline

## Testing

Add tests for pure logic first:

- form values convert to valid run settings
- invalid settings produce field-specific errors
- controller blocks target run before baseline
- demo acquisition produces deterministic frames
- STOP calls acquisition idle behavior

Manual smoke checks:

```powershell
.\.venv\Scripts\python.exe tree_ert_app.py --demo
.\.venv\Scripts\python.exe tree_ert_app.py --port COM3
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Success Criteria

- User can debug Phase 3A with clickable controls instead of memorizing CLI flags.
- Demo mode opens without hardware.
- Hardware mode can connect, configure, run baseline, run control drift, run target capture, and stop safely.
- UI shows raw serial and health metrics when readings are bad.
- Existing CLI behavior remains available.
- Generated logs remain compatible with the current `phase3a_logs/` workflow.
