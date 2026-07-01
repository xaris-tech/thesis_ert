# Phase 3A Hybrid Debug UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a simple Windows Tkinter debug UI for the active Phase 3A unified ERT workflow with clickable controls, demo mode, serial diagnostics, health metrics, reconstruction preview, and safe stop.

**Architecture:** Keep `phase3a_unified_reconstruct.py` as the CLI and core logic source. Add a focused `tree_ert/` package for UI settings, acquisition wrappers, controller state, and Tkinter widgets. The UI talks to hardware through the existing `FRAME,2` protocol and exposes demo mode for development without ESP32 hardware.

**Tech Stack:** Python 3, Tkinter, pyserial, NumPy, Matplotlib, PyEIT, unittest

---

## File Structure

- Create `tree_ert/__init__.py`: package marker and version string.
- Create `tree_ert/settings.py`: UI setting dataclass and form parsing helpers.
- Create `tree_ert/acquisition.py`: serial and demo acquisition classes.
- Create `tree_ert/controller.py`: state machine for connect, configure, baseline, control, target, stop.
- Create `tree_ert/ui.py`: Tkinter app, tabs, queue handling, Matplotlib embedding.
- Create `tree_ert_app.py`: app entry point and CLI args.
- Create `tests/test_tree_ert_settings.py`: settings validation tests.
- Create `tests/test_tree_ert_controller.py`: controller workflow and stop tests.
- Modify `docs/first-working-prototype/README.md` only if a UI guide link already fits naturally.

## Task 1: Settings Model

**Files:**
- Create: `tree_ert/__init__.py`
- Create: `tree_ert/settings.py`
- Test: `tests/test_tree_ert_settings.py`

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_tree_ert_settings.py`:

```python
import unittest

from tree_ert.settings import UiSettings, parse_int_field, parse_float_field


class TestUiSettings(unittest.TestCase):
    def test_defaults_are_safe_for_demo(self):
        settings = UiSettings.default()
        self.assertEqual(settings.port, "COM3")
        self.assertEqual(settings.baud, 115200)
        self.assertEqual(settings.pattern, "adjacent")
        self.assertEqual(settings.dac, 100)
        self.assertEqual(settings.settle_ms, 30)
        self.assertEqual(settings.samples, 4)
        self.assertEqual(settings.baseline_frames, 10)
        self.assertEqual(settings.frames, 20)

    def test_rejects_invalid_pattern_and_ranges(self):
        with self.assertRaisesRegex(ValueError, "pattern"):
            UiSettings(pattern="bad").validate()
        with self.assertRaisesRegex(ValueError, "dac"):
            UiSettings(dac=700).validate()
        with self.assertRaisesRegex(ValueError, "settle_ms"):
            UiSettings(settle_ms=0).validate()

    def test_parses_fields_with_clear_errors(self):
        self.assertEqual(parse_int_field("dac", "120", 0, 620), 120)
        self.assertEqual(parse_float_field("diameter_cm", "16.5", minimum=0.1), 16.5)
        with self.assertRaisesRegex(ValueError, "dac"):
            parse_int_field("dac", "abc", 0, 620)
        with self.assertRaisesRegex(ValueError, "diameter_cm"):
            parse_float_field("diameter_cm", "0", minimum=0.1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_settings -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tree_ert'`.

- [ ] **Step 3: Implement settings**

Create `tree_ert/__init__.py`:

```python
"""Phase 3A ERT debug UI package."""

__version__ = "0.1.0"
```

Create `tree_ert/settings.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VALID_PATTERNS = ("adjacent", "opposite", "skip-1", "skip-2")


def parse_int_field(name: str, value: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def parse_float_field(name: str, value: str, minimum: float | None = None) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum:g}")
    return parsed


@dataclass(frozen=True)
class UiSettings:
    port: str = "COM3"
    baud: int = 115200
    pattern: str = "adjacent"
    dac: int = 100
    settle_ms: int = 30
    samples: int = 4
    warmup_frames: int = 10
    baseline_frames: int = 10
    frames: int = 20
    diameter_cm: float | None = None
    log_dir: Path = Path("phase3a_logs")
    log_enabled: bool = True
    allow_unstable_baseline: bool = False

    @classmethod
    def default(cls) -> "UiSettings":
        return cls()

    def validate(self) -> "UiSettings":
        if not self.port.strip():
            raise ValueError("port is required")
        if self.baud <= 0:
            raise ValueError("baud must be positive")
        if self.pattern not in VALID_PATTERNS:
            raise ValueError(f"pattern must be one of {', '.join(VALID_PATTERNS)}")
        if self.dac < 0 or self.dac > 620:
            raise ValueError("dac must be between 0 and 620")
        if self.settle_ms <= 0:
            raise ValueError("settle_ms must be positive")
        if self.samples <= 0:
            raise ValueError("samples must be positive")
        if self.warmup_frames < 0:
            raise ValueError("warmup_frames cannot be negative")
        if self.baseline_frames <= 0:
            raise ValueError("baseline_frames must be positive")
        if self.frames <= 0:
            raise ValueError("frames must be positive")
        if self.diameter_cm is not None and self.diameter_cm <= 0:
            raise ValueError("diameter_cm must be positive")
        return self
```

- [ ] **Step 4: Run settings tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_settings -v
```

Expected: PASS.

## Task 2: Acquisition Layer

**Files:**
- Create: `tree_ert/acquisition.py`
- Test: `tests/test_tree_ert_controller.py`

- [ ] **Step 1: Write failing acquisition/controller tests**

Create `tests/test_tree_ert_controller.py`:

```python
import unittest

from tree_ert.acquisition import DemoAcquisition
from tree_ert.controller import DebugController, ControllerState
from tree_ert.settings import UiSettings


class TestDebugController(unittest.TestCase):
    def test_demo_controller_captures_baseline_then_target(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        baseline = controller.capture_baseline(settings)
        self.assertEqual(controller.state, ControllerState.BASELINE_READY)
        self.assertGreater(len(baseline), 0)
        target = controller.capture_target(settings)
        self.assertEqual(controller.state, ControllerState.TARGET_READY)
        self.assertEqual(len(target.reconstructions), settings.frames)

    def test_target_requires_baseline(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        with self.assertRaisesRegex(RuntimeError, "baseline"):
            controller.capture_target(settings)

    def test_stop_calls_acquisition_stop(self):
        acquisition = DemoAcquisition()
        controller = DebugController(acquisition)
        controller.stop()
        self.assertTrue(acquisition.stopped)
        self.assertEqual(controller.state, ControllerState.STOPPED)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_controller -v
```

Expected: FAIL because `tree_ert.acquisition` and `tree_ert.controller` do not exist.

- [ ] **Step 3: Implement acquisition wrappers**

Create `tree_ert/acquisition.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import serial

import phase3a_unified_reconstruct as unified
from tree_ert.settings import UiSettings


class Acquisition(Protocol):
    def connect(self, settings: UiSettings) -> None: ...
    def configure(self, settings: UiSettings) -> None: ...
    def capture_frame(self) -> unified.UnifiedFrame: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


@dataclass
class DemoAcquisition:
    stopped: bool = False
    frame_id: int = 0
    pattern: str = "adjacent"

    def connect(self, settings: UiSettings) -> None:
        self.pattern = settings.pattern
        self.stopped = False

    def configure(self, settings: UiSettings) -> None:
        self.pattern = settings.pattern

    def capture_frame(self) -> unified.UnifiedFrame:
        self.frame_id += 1
        protocol, _ = unified.protocol_and_command(self.pattern)
        records = []
        rng = np.random.default_rng(self.frame_id)
        for ex_pair in protocol.ex_mat:
            i_plus = int(ex_pair[0])
            i_minus = int(ex_pair[1])
            for meas_pair in protocol.meas_mat[int(i_plus)]:
                v_plus = int(meas_pair[1])
                v_minus = int(meas_pair[0])
                base_mv = 20.0 * np.sin((i_plus + v_plus + 1) / 3.0)
                noise = float(rng.normal(0.0, 0.05))
                records.append(unified.MeasurementRecord(
                    polarity="FWD",
                    i_pair=(i_plus, i_minus),
                    v_pair=(v_plus, v_minus),
                    voltage_mv=base_mv + noise,
                    current_ua=250.0,
                    quality="OK",
                ))
                records.append(unified.MeasurementRecord(
                    polarity="REV",
                    i_pair=(i_minus, i_plus),
                    v_pair=(v_plus, v_minus),
                    voltage_mv=-(base_mv + noise),
                    current_ua=250.0,
                    quality="OK",
                ))
        return unified.UnifiedFrame(
            frame_id=self.frame_id,
            pattern=self.pattern,
            dac_code=100,
            settle_ms=30,
            sample_count=4,
            records=records,
        )

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.stop()


class SerialAcquisition:
    def __init__(self) -> None:
        self._serial: serial.Serial | None = None

    def connect(self, settings: UiSettings) -> None:
        self._serial = serial.Serial(settings.port, settings.baud, timeout=1.0)
        self._serial.reset_input_buffer()

    def configure(self, settings: UiSettings) -> None:
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        _, mode_command = unified.protocol_and_command(settings.pattern)
        self._serial.write(mode_command)
        self._serial.write(f"p{settings.dac}\n".encode())
        self._serial.write(f"t{settings.settle_ms}\n".encode())
        self._serial.write(f"n{settings.samples}\n".encode())

    def capture_frame(self) -> unified.UnifiedFrame:
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        return unified.request_frame(self._serial)

    def send_command(self, command: str) -> None:
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        self._serial.write(f"{command.strip()}\n".encode())

    def stop(self) -> None:
        if self._serial is not None:
            self._serial.write(b"x\n")

    def close(self) -> None:
        if self._serial is not None:
            self.stop()
            self._serial.close()
            self._serial = None
```

- [ ] **Step 4: Run controller test and confirm controller still missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_controller -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tree_ert.controller'`.

## Task 3: Controller

**Files:**
- Create: `tree_ert/controller.py`
- Test: `tests/test_tree_ert_controller.py`

- [ ] **Step 1: Implement controller**

Create `tree_ert/controller.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

import phase3a_unified_reconstruct as unified
import phase3a_reconstruct as base
from tree_ert.acquisition import Acquisition
from tree_ert.settings import UiSettings


class ControllerState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    CONFIGURED = "configured"
    BASELINE_READY = "baseline_ready"
    TARGET_READY = "target_ready"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class BaselineResult:
    baseline: np.ndarray
    stability: unified.BaselineStability
    pair_scores: list[unified.PairHealthScore]


@dataclass(frozen=True)
class TargetResult:
    reconstructions: list[np.ndarray]
    frame_healths: list[unified.FrameHealthScore]


class DebugController:
    def __init__(self, acquisition: Acquisition) -> None:
        self.acquisition = acquisition
        self.state = ControllerState.DISCONNECTED
        self.protocol = None
        self.solver = None
        self.mesh = None
        self.baseline_result: BaselineResult | None = None

    def connect(self, settings: UiSettings) -> None:
        settings.validate()
        self.acquisition.connect(settings)
        self.state = ControllerState.CONNECTED

    def configure(self, settings: UiSettings) -> None:
        settings.validate()
        self.protocol, _ = unified.protocol_and_command(settings.pattern)
        self.mesh, self.solver = base.create_solver(self.protocol)
        self.acquisition.configure(settings)
        self.state = ControllerState.CONFIGURED

    def capture_baseline(self, settings: UiSettings) -> BaselineResult:
        self._require_configured()
        vectors = []
        for _ in range(settings.warmup_frames):
            self.acquisition.capture_frame()
        for _ in range(settings.baseline_frames):
            frame = self.acquisition.capture_frame()
            self._verify_pattern(frame, settings.pattern)
            vectors.append(unified.frame_to_vector(frame, self.protocol))
        stability = unified.require_stable_baseline(
            vectors,
            allow_unstable=settings.allow_unstable_baseline,
        )
        baseline = unified.average_vectors(vectors)
        pair_scores = unified.analyze_baseline_pair_health(vectors, self.protocol)
        result = BaselineResult(baseline, stability, pair_scores)
        self.baseline_result = result
        self.state = ControllerState.BASELINE_READY
        return result

    def capture_control(self, settings: UiSettings) -> unified.ControlDriftReport:
        if self.baseline_result is None:
            raise RuntimeError("baseline is required before control drift")
        controls = []
        for _ in range(settings.frames):
            frame = self.acquisition.capture_frame()
            self._verify_pattern(frame, settings.pattern)
            controls.append(unified.frame_to_vector(frame, self.protocol))
        return unified.analyze_control_drift(
            self.baseline_result.baseline,
            controls,
            self.protocol,
        )

    def capture_target(self, settings: UiSettings) -> TargetResult:
        if self.baseline_result is None:
            raise RuntimeError("baseline is required before target capture")
        reconstructions = []
        healths = []
        for _ in range(settings.frames):
            frame = self.acquisition.capture_frame()
            self._verify_pattern(frame, settings.pattern)
            current = unified.frame_to_vector(frame, self.protocol)
            currents = np.asarray([abs(record.current_ua) for record in frame.records])
            filtered = unified.filter_frame_vector_best_effort(
                baseline=self.baseline_result.baseline,
                current=current,
                pair_scores=self.baseline_result.pair_scores,
                current_median_ua=float(np.median(currents)),
                current_spread_ua=float(np.max(currents) - np.min(currents)),
            )
            reconstructions.append(
                base.reconstruct_difference(
                    self.baseline_result.baseline,
                    filtered.filtered_vector,
                    self.solver,
                )
            )
            healths.append(filtered.frame_health)
        self.state = ControllerState.TARGET_READY
        return TargetResult(reconstructions, healths)

    def stop(self) -> None:
        self.acquisition.stop()
        self.state = ControllerState.STOPPED

    def close(self) -> None:
        self.acquisition.close()
        self.state = ControllerState.DISCONNECTED

    def _require_configured(self) -> None:
        if self.protocol is None or self.solver is None:
            raise RuntimeError("configure before capture")

    @staticmethod
    def _verify_pattern(frame: unified.UnifiedFrame, expected: str) -> None:
        if frame.pattern != expected:
            raise ValueError(f"Firmware returned {frame.pattern}, expected {expected}")
```

- [ ] **Step 2: Run controller tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_controller -v
```

Expected: PASS.

## Task 4: Tkinter UI Shell

**Files:**
- Create: `tree_ert/ui.py`
- Create: `tree_ert_app.py`

- [ ] **Step 1: Implement app entry point**

Create `tree_ert_app.py`:

```python
from __future__ import annotations

import argparse

from tree_ert.ui import run_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3A ERT hybrid debug UI")
    parser.add_argument("--demo", action="store_true", help="Run without hardware using deterministic demo frames")
    parser.add_argument("--port", default="COM3", help="Serial port for ESP32-S3")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_app(demo=args.demo, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Implement Tkinter UI**

Create `tree_ert/ui.py` with:

```python
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.controller import DebugController
from tree_ert.settings import UiSettings, parse_int_field, parse_float_field


class DebugApp(tk.Tk):
    def __init__(self, demo: bool, port: str) -> None:
        super().__init__()
        self.title("Phase 3A ERT Hybrid Debug UI")
        self.geometry("1180x760")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        acquisition = DemoAcquisition() if demo else SerialAcquisition()
        self.controller = DebugController(acquisition)
        self.demo = demo
        self._build_vars(port)
        self._build_layout()
        self.after(100, self._drain_events)

    def _build_vars(self, port: str) -> None:
        defaults = UiSettings.default()
        self.port_var = tk.StringVar(value=port)
        self.pattern_var = tk.StringVar(value=defaults.pattern)
        self.dac_var = tk.StringVar(value=str(defaults.dac))
        self.settle_var = tk.StringVar(value=str(defaults.settle_ms))
        self.samples_var = tk.StringVar(value=str(defaults.samples))
        self.warmup_var = tk.StringVar(value=str(defaults.warmup_frames))
        self.baseline_var = tk.StringVar(value=str(defaults.baseline_frames))
        self.frames_var = tk.StringVar(value=str(defaults.frames))
        self.diameter_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Demo mode" if self.demo else "Disconnected")

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Notebook(self)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_controls(left)
        self._build_tabs(right)

    def _build_controls(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Connection").pack(anchor="w")
        ttk.Entry(parent, textvariable=self.port_var, width=18).pack(fill="x", pady=2)
        ttk.Combobox(parent, textvariable=self.pattern_var, values=("adjacent", "opposite", "skip-1", "skip-2"), width=16).pack(fill="x", pady=2)
        for label, var in (
            ("DAC", self.dac_var), ("Settle ms", self.settle_var), ("Samples", self.samples_var),
            ("Warmup frames", self.warmup_var), ("Baseline frames", self.baseline_var),
            ("Run frames", self.frames_var), ("Diameter cm", self.diameter_var),
        ):
            ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 0))
            ttk.Entry(parent, textvariable=var, width=18).pack(fill="x", pady=2)
        for label, action in (
            ("Connect", self.connect), ("Configure", self.configure),
            ("Baseline", self.capture_baseline), ("Control Drift", self.capture_control),
            ("Target Run", self.capture_target), ("Export", self.export_placeholder),
        ):
            ttk.Button(parent, text=label, command=action).pack(fill="x", pady=4)
        tk.Button(parent, text="STOP / CURRENT IDLE", command=self.stop, bg="#b00020", fg="white").pack(fill="x", pady=12)

    def _build_tabs(self, notebook: ttk.Notebook) -> None:
        self.status_text = tk.Text(notebook, height=10)
        self.serial_text = tk.Text(notebook, height=10)
        self.health_text = tk.Text(notebook, height=10)
        self.files_text = tk.Text(notebook, height=10)
        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=notebook)
        for title, widget in (
            ("Status", self.status_text), ("Reconstruction", self.canvas.get_tk_widget()),
            ("Health", self.health_text), ("Serial", self.serial_text), ("Files", self.files_text),
        ):
            notebook.add(widget, text=title)
        self._append(self.status_text, "Ready.\n")

    def settings(self) -> UiSettings:
        diameter_text = self.diameter_var.get().strip()
        diameter = parse_float_field("diameter_cm", diameter_text, minimum=0.1) if diameter_text else None
        return UiSettings(
            port=self.port_var.get().strip(),
            pattern=self.pattern_var.get().strip(),
            dac=parse_int_field("dac", self.dac_var.get(), 0, 620),
            settle_ms=parse_int_field("settle_ms", self.settle_var.get(), 1, 10000),
            samples=parse_int_field("samples", self.samples_var.get(), 1, 1000),
            warmup_frames=parse_int_field("warmup_frames", self.warmup_var.get(), 0, 1000),
            baseline_frames=parse_int_field("baseline_frames", self.baseline_var.get(), 1, 1000),
            frames=parse_int_field("frames", self.frames_var.get(), 1, 1000),
            diameter_cm=diameter,
        ).validate()

    def connect(self) -> None:
        self._run_worker("connect", lambda: self.controller.connect(self.settings()))

    def configure(self) -> None:
        self._run_worker("configure", lambda: self.controller.configure(self.settings()))

    def capture_baseline(self) -> None:
        self._run_worker("baseline", lambda: self.controller.capture_baseline(self.settings()))

    def capture_control(self) -> None:
        self._run_worker("control", lambda: self.controller.capture_control(self.settings()))

    def capture_target(self) -> None:
        self._run_worker("target", lambda: self.controller.capture_target(self.settings()))

    def export_placeholder(self) -> None:
        self._append(self.files_text, "Export uses phase3a_logs outputs from capture runs.\n")

    def stop(self) -> None:
        self.controller.stop()
        self._append(self.status_text, "STOP / CURRENT IDLE sent.\n")

    def _run_worker(self, name: str, fn) -> None:
        def worker() -> None:
            try:
                result = fn()
            except Exception as exc:
                self.events.put(("error", f"{name}: {exc}"))
            else:
                self.events.put((name, result))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, payload)
        self.after(100, self._drain_events)

    def _handle_event(self, event: str, payload: object) -> None:
        if event == "error":
            self._append(self.status_text, f"ERROR {payload}\n")
            messagebox.showerror("ERT UI Error", str(payload))
            return
        self._append(self.status_text, f"{event} complete.\n")
        if event == "baseline":
            self._append(self.health_text, f"Baseline: {payload.stability}\n")
        if event == "control":
            self._append(self.health_text, f"Control frames: {len(payload.frames)}\n")
        if event == "target":
            self._draw_average(payload.reconstructions)
            self._append(self.health_text, f"Target frames: {len(payload.reconstructions)}\n")

    def _draw_average(self, reconstructions: list[np.ndarray]) -> None:
        self.ax.clear()
        if reconstructions:
            average = np.mean(np.stack(reconstructions), axis=0)
            self.ax.plot(average)
            self.ax.set_title("Average reconstruction vector")
        self.canvas.draw_idle()

    @staticmethod
    def _append(widget: tk.Text, text: str) -> None:
        widget.insert("end", text)
        widget.see("end")


def run_app(demo: bool = False, port: str = "COM3") -> None:
    app = DebugApp(demo=demo, port=port)
    app.mainloop()
```

- [ ] **Step 3: Smoke-test demo UI**

Run:

```powershell
.\.venv\Scripts\python.exe tree_ert_app.py --demo
```

Expected: window opens. Click `Connect`, `Configure`, `Baseline`, `Control Drift`, `Target Run`; no traceback in terminal.

## Task 5: Verification And Polish

**Files:**
- Modify: `tree_ert/ui.py`
- Modify: `tree_ert/controller.py`
- Test: existing tests

- [ ] **Step 1: Run unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_settings tests.test_tree_ert_controller -v
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: PASS. If PyEIT or serial imports fail, capture exact traceback and fix missing dependency/configuration before proceeding.

- [ ] **Step 3: Run import/help checks**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import tree_ert_app; print('import ok')"
.\.venv\Scripts\python.exe tree_ert_app.py --help
```

Expected: both commands exit successfully.

- [ ] **Step 4: Hardware smoke command**

Run only when ESP32 is connected and Arduino Serial Monitor is closed:

```powershell
.\.venv\Scripts\python.exe tree_ert_app.py --port COM3
```

Expected: app opens. `Connect` opens serial, `Configure` sends Phase 3A commands, and `STOP / CURRENT IDLE` sends `x`.

## Self-Review

Spec coverage:

- Hybrid layout: Task 4.
- Real buttons: Task 4.
- Demo mode: Task 2 and Task 4.
- Serial Phase 3A protocol reuse: Task 2 and Task 3.
- Baseline, control, target flows: Task 3 and Task 4.
- STOP / CURRENT IDLE: Task 2, Task 3, Task 4.
- Health metrics: Task 3 and Task 4.
- Existing CLI preserved: no task modifies CLI behavior.

Placeholder scan:

- No `TODO` or `TBD` markers.
- Every new module has concrete initial code.

Type consistency:

- `UiSettings`, `DemoAcquisition`, `SerialAcquisition`, `DebugController`, `BaselineResult`, and `TargetResult` are defined before use.
- Tests reference only types introduced by this plan.
