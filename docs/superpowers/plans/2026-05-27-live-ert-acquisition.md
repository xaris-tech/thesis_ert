# Live ERT Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live serial acquisition tool for the current 2-channel ERT setup that plots measurements and exports PyEIT-friendly scan vectors.

**Architecture:** Keep a single user-facing `ert.py` entrypoint, but separate parsing, state updates, and export logic into testable functions and lightweight data containers. The runtime loop will continue to drive the ESP32 over serial and update a Matplotlib view, while pure functions handle scan decoding and export packaging.

**Tech Stack:** Python, pyserial, numpy, matplotlib, pyeit-compatible measurement export, unittest

---

### Task 1: Define and test scan parsing

**Files:**
- Create: `C:\Users\Vidad\Documents\ERT\tests\test_ert.py`
- Modify: `C:\Users\Vidad\Documents\ERT\ert.py`

- [ ] **Step 1: Write the failing test**

```python
def test_parse_scan_lines_extracts_measurement_values(self):
    lines = ["0,E3,151.0", "1,E4,150.5"]
    parsed = ert.parse_scan_lines(lines)
    self.assertEqual(parsed.channels, ("E3", "E4"))
    self.assertTrue(np.allclose(parsed.values, np.array([151.0, 150.5])))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ert.TestScanParsing.test_parse_scan_lines_extracts_measurement_values -v`
Expected: FAIL because `parse_scan_lines` and the scan container do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class ParsedScan:
    channels: tuple[str, ...]
    values: np.ndarray


def parse_scan_lines(lines: list[str]) -> ParsedScan | None:
    channels = []
    values = []
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            values.append(float(parts[2]))
        except ValueError:
            continue
        channels.append(parts[1] or f"CH{len(channels)}")
    if not values:
        return None
    return ParsedScan(channels=tuple(channels), values=np.asarray(values, dtype=float))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ert.TestScanParsing.test_parse_scan_lines_extracts_measurement_values -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ert.py ert.py
git commit -m "test: add scan parsing coverage"
```

### Task 2: Define and test export packaging

**Files:**
- Modify: `C:\Users\Vidad\Documents\ERT\tests\test_ert.py`
- Modify: `C:\Users\Vidad\Documents\ERT\ert.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_export_payload_includes_delta_matrix(self):
    baseline = np.array([151.0, 150.5])
    scans = [
        ert.MeasurementRecord(timestamp="2026-05-27T13:00:00", channels=("E3", "E4"), values=np.array([156.5, 158.0]))
    ]
    payload = ert.build_export_payload(scans, baseline)
    self.assertEqual(payload["measurements"].shape, (1, 2))
    self.assertTrue(np.allclose(payload["delta"], np.array([[5.5, 7.5]])))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ert.TestExportPayload.test_build_export_payload_includes_delta_matrix -v`
Expected: FAIL because `MeasurementRecord` and `build_export_payload` do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class MeasurementRecord:
    timestamp: str
    channels: tuple[str, ...]
    values: np.ndarray


def build_export_payload(scans: list[MeasurementRecord], baseline: np.ndarray | None) -> dict[str, np.ndarray]:
    measurements = np.asarray([scan.values for scan in scans], dtype=float)
    delta = measurements - baseline if baseline is not None and len(measurements) else np.empty((0, 0))
    return {"measurements": measurements, "delta": delta}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ert.TestExportPayload.test_build_export_payload_includes_delta_matrix -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ert.py ert.py
git commit -m "feat: add export payload builder"
```

### Task 3: Refactor the live runtime and exports

**Files:**
- Modify: `C:\Users\Vidad\Documents\ERT\ert.py`

- [ ] **Step 1: Write the failing test**

```python
def test_apply_scan_updates_delta_against_baseline(self):
    session = ert.AcquisitionSession()
    baseline_scan = ert.ParsedScan(channels=("E3", "E4"), values=np.array([151.0, 150.5]))
    current_scan = ert.ParsedScan(channels=("E3", "E4"), values=np.array([156.5, 158.0]))
    session.apply_scan(baseline_scan)
    record = session.apply_scan(current_scan)
    self.assertTrue(np.allclose(record.delta, np.array([5.5, 7.5])))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ert.TestSessionState.test_apply_scan_updates_delta_against_baseline -v`
Expected: FAIL because the acquisition session model does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
class AcquisitionSession:
    def __init__(self) -> None:
        self.baseline = None
        self.records = []

    def apply_scan(self, scan: ParsedScan) -> MeasurementRecord:
        if self.baseline is None:
            self.baseline = scan.values.copy()
        delta = scan.values - self.baseline
        record = MeasurementRecord.from_scan(scan, delta=delta)
        self.records.append(record)
        return record
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ert.TestSessionState.test_apply_scan_updates_delta_against_baseline -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ert.py
git commit -m "feat: refactor live acquisition runtime"
```
