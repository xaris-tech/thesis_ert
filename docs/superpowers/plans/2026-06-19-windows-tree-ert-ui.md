# Windows Tree-ERT UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows Tkinter application that creates traceable ERT experiments, captures compatible adjacent/opposite frames, validates baseline/anomaly matching, saves raw data, and displays PyEIT difference reconstruction.

**Architecture:** Extract protocol, experiment, and reconstruction logic from the current CLI into focused modules under `tree_ert/`. The Tkinter layer calls a controller through a small acquisition interface, allowing both serial hardware and deterministic demo acquisition. Existing CLI files remain functional while the new app gains an explicit firmware-mode mismatch check.

**Tech Stack:** Python 3, Tkinter, pyserial, NumPy, Matplotlib, PyEIT, `unittest`

---

## File Structure

- Create `tree_ert/__init__.py`: package exports and version.
- Create `tree_ert/models.py`: validated experiment settings and frame models.
- Create `tree_ert/protocols.py`: adjacent/opposite protocol construction and record ordering.
- Create `tree_ert/storage.py`: timestamped experiment folders and atomic metadata/raw-data writes.
- Create `tree_ert/acquisition.py`: serial and deterministic demo acquisition interfaces.
- Create `tree_ert/controller.py`: baseline/anomaly workflow and compatibility checks.
- Create `tree_ert/reconstruction.py`: averaging, quality metrics, and PyEIT solve wrapper.
- Create `tree_ert/ui.py`: Tkinter widgets and event wiring only.
- Create `tree_ert_app.py`: Windows application entry point.
- Create `tests/test_tree_ert_models.py`, `tests/test_tree_ert_storage.py`, `tests/test_tree_ert_controller.py`, and `tests/test_tree_ert_reconstruction.py`.
- Modify `phase3a_reconstruct.py`: delegate protocol helpers to `tree_ert.protocols` without changing CLI behavior.

### Task 1: Experiment Models and Validation

**Files:**
- Create: `tree_ert/__init__.py`
- Create: `tree_ert/models.py`
- Test: `tests/test_tree_ert_models.py`

- [ ] **Step 1: Write failing validation tests**

```python
import unittest
from tree_ert.models import ExperimentConfig, Pattern, SampleType


class TestExperimentConfig(unittest.TestCase):
    def test_accepts_complete_tree_experiment(self):
        config = ExperimentConfig(
            experiment_id="banana-001",
            sample_type=SampleType.BANANA,
            circumference_cm=62.0,
            electrode_depth_mm=12.0,
            e1_orientation="north",
            pattern=Pattern.ADJACENT,
            dac_code=300,
            settle_ms=25,
            samples_per_reading=4,
            frames_to_average=3,
            notes="intact baseline",
        )
        self.assertEqual(config.electrode_spacing_cm, 62.0 / 12.0)

    def test_rejects_missing_identity_and_invalid_ranges(self):
        with self.assertRaisesRegex(ValueError, "experiment_id"):
            ExperimentConfig("", SampleType.SALINE, 40, 10, "north", Pattern.ADJACENT, 300, 25, 4, 3, "")
        with self.assertRaisesRegex(ValueError, "circumference"):
            ExperimentConfig("x", SampleType.SALINE, 0, 10, "north", Pattern.ADJACENT, 300, 25, 4, 3, "")
```

- [ ] **Step 2: Run the tests and verify import failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_models -v`

Expected: FAIL because `tree_ert.models` does not exist.

- [ ] **Step 3: Implement enums and immutable validated config**

```python
from dataclasses import asdict, dataclass
from enum import Enum


class Pattern(str, Enum):
    ADJACENT = "adjacent"
    OPPOSITE = "opposite"


class SampleType(str, Enum):
    SALINE = "saline"
    BANANA = "banana"
    CUT_TRUNK = "cut_trunk"
    LIVING_TREE = "living_tree"


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    sample_type: SampleType
    circumference_cm: float
    electrode_depth_mm: float
    e1_orientation: str
    pattern: Pattern
    dac_code: int
    settle_ms: int
    samples_per_reading: int
    frames_to_average: int
    notes: str = ""

    def __post_init__(self):
        checks = {
            "experiment_id": bool(self.experiment_id.strip()),
            "circumference": self.circumference_cm > 0,
            "electrode_depth": self.electrode_depth_mm > 0,
            "e1_orientation": bool(self.e1_orientation.strip()),
            "dac_code": 0 <= self.dac_code <= 4095,
            "settle_ms": self.settle_ms >= 1,
            "samples_per_reading": self.samples_per_reading >= 1,
            "frames_to_average": self.frames_to_average >= 1,
        }
        for name, valid in checks.items():
            if not valid:
                raise ValueError(f"Invalid {name}")

    @property
    def electrode_spacing_cm(self):
        return self.circumference_cm / 12.0

    def to_dict(self):
        result = asdict(self)
        result["sample_type"] = self.sample_type.value
        result["pattern"] = self.pattern.value
        return result
```

- [ ] **Step 4: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_models -v`

Expected: PASS.

Commit: `git commit -am "feat: add validated ERT experiment model"`

### Task 2: Experiment Storage

**Files:**
- Create: `tree_ert/storage.py`
- Test: `tests/test_tree_ert_storage.py`

- [ ] **Step 1: Write tests for folder creation and bounded raw storage**

```python
def test_create_run_writes_metadata_and_unique_folder(self):
    with TemporaryDirectory() as root:
        store = ExperimentStore(Path(root), max_frames=5)
        run = store.create_run(make_config(), now=datetime(2026, 6, 19, 9, 30, 0))
        self.assertTrue((run / "metadata.json").exists())
        self.assertIn("banana-001", run.name)

def test_writer_rejects_more_than_max_frames(self):
    with TemporaryDirectory() as root:
        store = ExperimentStore(Path(root), max_frames=1)
        run = store.create_run(make_config())
        store.write_frame(run, "baseline", 0, make_records())
        with self.assertRaisesRegex(ValueError, "frame limit"):
            store.write_frame(run, "baseline", 1, make_records())
```

- [ ] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_storage -v`

Expected: FAIL because `ExperimentStore` is undefined.

- [ ] **Step 3: Implement atomic metadata and CSV writes**

Implement `ExperimentStore.create_run`, `write_frame`, and `write_summary` using
temporary files followed by `Path.replace()`. Use columns `capture`,
`frame_index`, `pattern`, `polarity`, `i_plus`, `i_minus`, `v_plus`, `v_minus`,
`voltage_mv`, `current_ua`, and `flags`. Sanitize experiment IDs to ASCII
letters, numbers, `_`, and `-`.

- [ ] **Step 4: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_storage -v`

Expected: PASS.

Commit: `git commit -am "feat: add traceable experiment storage"`

### Task 3: Acquisition Interface and Workflow Controller

**Files:**
- Create: `tree_ert/acquisition.py`
- Create: `tree_ert/controller.py`
- Test: `tests/test_tree_ert_controller.py`

- [ ] **Step 1: Write controller tests with a fake acquisition source**

```python
class FakeAcquisition:
    def __init__(self, pattern, frames):
        self.pattern = pattern
        self.frames = iter(frames)
        self.stopped = False

    def configure(self, config):
        if config.pattern != self.pattern:
            raise ProtocolMismatch(config.pattern, self.pattern)

    def capture_frame(self):
        return next(self.frames)

    def stop(self):
        self.stopped = True


def test_controller_blocks_pattern_mismatch(self):
    source = FakeAcquisition(Pattern.OPPOSITE, [])
    with self.assertRaises(ProtocolMismatch):
        ExperimentController(source, store).start(make_config(pattern=Pattern.ADJACENT))

def test_anomaly_capture_requires_baseline(self):
    controller = ExperimentController(FakeAcquisition(Pattern.ADJACENT, []), store)
    controller.start(make_config())
    with self.assertRaisesRegex(RuntimeError, "baseline"):
        controller.capture_anomaly()
```

- [ ] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_controller -v`

Expected: FAIL because controller and acquisition abstractions do not exist.

- [ ] **Step 3: Implement acquisition protocol and state machine**

Define an `Acquisition` protocol with `configure`, `capture_frame`, and `stop`.
Implement `DemoAcquisition` using deterministic seeded vectors and
`LegacySerialAcquisition` using the current `s` / `FRAME:` / `END` contract.
Implement controller states `DISCONNECTED`, `READY`, `BASELINE_CAPTURED`,
`ANOMALY_CAPTURED`, and `FAILED`. Always call `stop()` after exceptions.

- [ ] **Step 4: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_controller -v`

Expected: PASS.

Commit: `git commit -am "feat: add safe acquisition workflow"`

### Task 4: Protocol Mapping, Averaging, and Reconstruction

**Files:**
- Create: `tree_ert/protocols.py`
- Create: `tree_ert/reconstruction.py`
- Modify: `phase3a_reconstruct.py`
- Test: `tests/test_tree_ert_reconstruction.py`
- Modify: `tests/test_phase3a_reconstruct.py`

- [ ] **Step 1: Write tests for mode selection and compatibility**

```python
def test_protocol_for_pattern_has_expected_measurements(self):
    adjacent = protocol_for(Pattern.ADJACENT)
    opposite = protocol_for(Pattern.OPPOSITE)
    self.assertEqual(adjacent.ex_mat.shape, (12, 2))
    self.assertEqual(adjacent.meas_mat.shape, (12, 9, 2))
    self.assertEqual(opposite.meas_mat.shape, (12, 8, 2))

def test_reconstruction_rejects_config_mismatch(self):
    with self.assertRaisesRegex(ValueError, "configuration"):
        prepare_difference(baseline_capture, anomaly_with_other_pattern)
```

- [ ] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_reconstruction -v`

Expected: FAIL because protocol and reconstruction services do not exist.

- [ ] **Step 3: Extract existing proven protocol code**

Move `build_protocol`, `build_adjacent_protocol`, `build_opposite_protocol`,
`identify_drive_pattern`, and `records_to_vector` into `tree_ert.protocols`.
Re-export them from `phase3a_reconstruct.py` to preserve current imports and
tests. Add robust frame averaging, RMS drift, forward/reverse disagreement,
and a `ReconstructionResult` containing element values and quality metrics.

- [ ] **Step 4: Run old and new tests and commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_phase3a_reconstruct tests.test_tree_ert_reconstruction -v`

Expected: all tests PASS with unchanged legacy behavior.

Commit: `git commit -am "refactor: share ERT protocol and reconstruction services"`

### Task 5: Tkinter Windows Application

**Files:**
- Create: `tree_ert/ui.py`
- Create: `tree_ert_app.py`
- Test: `tests/test_tree_ert_ui.py`

- [ ] **Step 1: Write tests for form-to-config conversion**

```python
def test_form_values_create_valid_config(self):
    values = valid_form_values()
    config = config_from_form(values)
    self.assertEqual(config.pattern, Pattern.ADJACENT)
    self.assertEqual(config.frames_to_average, 3)

def test_form_reports_all_invalid_fields(self):
    with self.assertRaisesRegex(ValueError, "experiment_id.*circumference"):
        config_from_form({**valid_form_values(), "experiment_id": "", "circumference_cm": "0"})
```

- [ ] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tree_ert_ui -v`

Expected: FAIL because UI helpers do not exist.

- [ ] **Step 3: Implement the application**

Create a two-column Tkinter window. The left side contains connection,
experiment, acquisition, and baseline/anomaly controls. The right side embeds
Matplotlib plots for reconstruction, current by injection pair, and frame
quality. Run serial capture on a worker thread and send immutable events to
the Tk main loop through `queue.Queue`; never update widgets from the worker.
Disable incompatible buttons based on controller state and provide a large
red `STOP / CURRENT IDLE` button that calls `Acquisition.stop()` immediately.

- [ ] **Step 4: Add demo launch and smoke verification**

Run: `.\.venv\Scripts\python.exe tree_ert_app.py --demo`

Expected: window opens, metadata can be entered, baseline and anomaly demo
captures complete, plots update, and an experiment folder is created.

- [ ] **Step 5: Run full test suite and commit**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all old and new tests PASS.

Commit: `git commit -am "feat: add Windows tree ERT experiment app"`

### Task 6: User Documentation

**Files:**
- Create: `docs/first-working-prototype/11-windows-app-user-guide.md`
- Modify: `docs/first-working-prototype/README.md`

- [ ] **Step 1: Document demo and hardware workflows**

Include exact launch commands, required metadata, baseline/anomaly sequence,
pattern-mismatch errors, data-folder contents, plot interpretation, and the
stop procedure.

- [ ] **Step 2: Verify commands**

Run:

```powershell
.\.venv\Scripts\python.exe tree_ert_app.py --help
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: help exits successfully and all tests PASS.

- [ ] **Step 3: Commit documentation**

Commit: `git commit -am "docs: add tree ERT app user guide"`
