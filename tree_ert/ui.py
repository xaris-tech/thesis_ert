from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from phase3a_reconstruct import N_ELECTRODES
from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.controller import (
    ControllerState,
    DebugController,
    DriftTuneAttempt,
    DriftTuneResult,
)
from tree_ert.settings import LADDER_STAGES, VALID_STAGES, UiSettings

# ---------------------------------------------------------------------------
# Pure helpers. These have no GUI-toolkit dependency and are covered by
# tests/test_tree_ert_ui.py directly, so their names and behaviour must not
# change when the widget layer changes.
# ---------------------------------------------------------------------------


def average_reconstruction_vector(reconstructions: list[np.ndarray]) -> np.ndarray:
    if not reconstructions:
        return np.asarray([], dtype=float)
    return np.mean(np.stack(reconstructions), axis=0)


FACE = "#f4f5f7"
PANEL = "#ffffff"
TEXT = "#262a31"
GRID = "#d6dae1"
ACCENT = "#0f9488"
INPUT_BG = "#ffffff"
BUTTON_BG = "#eceef2"
BUTTON_HOVER = "#dfe2e8"
MUTED_TEXT = "#6b7280"


def build_reconstruction_figure() -> tuple[Figure, object, object, tuple[object, ...]]:
    figure = Figure(figsize=(10, 6.5), dpi=100, facecolor=FACE)
    grid = figure.add_gridspec(2, 4, height_ratios=(3.0, 1.15))
    map_ax = figure.add_subplot(grid[0, 0:2])
    vector_ax = figure.add_subplot(grid[0, 2:4])
    scan_axes = tuple(figure.add_subplot(grid[1, index]) for index in range(4))
    for axis in (map_ax, vector_ax, *scan_axes):
        axis.set_facecolor(FACE)
        axis.tick_params(colors=TEXT, labelsize=8)
        for spine in axis.spines.values():
            spine.set_color(GRID)
        axis.title.set_color(TEXT)
        axis.xaxis.label.set_color(TEXT)
        axis.yaxis.label.set_color(TEXT)
    map_ax.set_title("Average 2D map")
    map_ax.set_aspect("equal")
    map_ax.set_axis_off()
    vector_ax.set_title("Average reconstruction vector")
    vector_ax.set_xlabel("Vector index")
    vector_ax.set_ylabel("Difference")
    for index, axis in enumerate(scan_axes, start=1):
        axis.set_title(f"Scan {index}")
        axis.set_axis_off()
    figure.tight_layout()
    return figure, map_ax, vector_ax, scan_axes


def preview_scan_indices(scan_count: int, preview_count: int = 4) -> tuple[int, ...]:
    if scan_count <= 0:
        return ()
    if scan_count <= preview_count:
        return tuple(range(scan_count))
    return tuple(int(round(index)) for index in np.linspace(0, scan_count - 1, preview_count))


def debug_tab_titles() -> tuple[str, ...]:
    return ("Reconstruction", "Health", "Serial", "Files")


def format_control_drift_summary(report: unified.ControlDriftReport) -> str:
    if not report.frames:
        return "Control drift result: no frames analyzed"
    max_rms = max(frame.rms_kohm for frame in report.frames)
    max_relative = max(frame.relative_rms_percent for frame in report.frames)
    min_correlation = min(frame.correlation for frame in report.frames)
    summary = (
        "Control drift result: "
        f"frames={len(report.frames)} "
        f"max_rms={max_rms:.6f}kOhm "
        f"max_relative={max_relative:.2f}% "
        f"min_corr={min_correlation:.6f}"
    )
    if report.pairs:
        pair = report.pairs[0]
        summary += (
            " "
            f"worst_pair=I={base.index_to_electrode(pair.i_pair[0])}-"
            f"{base.index_to_electrode(pair.i_pair[1])} "
            f"V={base.index_to_electrode(pair.v_pair[0])}-"
            f"{base.index_to_electrode(pair.v_pair[1])} "
            f"pair_rms={pair.rms_kohm:.6f}kOhm"
        )
    if report.electrodes:
        electrode = report.electrodes[0]
        summary += (
            " "
            f"worst_electrode={base.index_to_electrode(electrode.electrode)} "
            f"electrode_mean_rms={electrode.mean_pair_rms_kohm:.6f}kOhm"
        )
    return summary


def format_drift_tune_summary(result: DriftTuneResult) -> str:
    if result.best is None:
        return f"Drift tuning result: no successful attempts out of {len(result.attempts)}"
    best = result.best
    return (
        "Drift tuning result: "
        f"best_settle={best.settings.settle_ms}ms "
        f"best_samples={best.settings.samples} "
        f"best_warmup={best.settings.warmup_frames} "
        f"best_baseline={best.settings.baseline_frames} "
        f"best_control_frames={best.settings.frames} "
        f"max_relative={best.max_relative_rms_percent:.2f}% "
        f"max_rms={best.max_rms_kohm:.6f}kOhm "
        f"min_corr={best.min_correlation:.6f}"
    )


def format_drift_tune_attempt(attempt: DriftTuneAttempt) -> str:
    settings = attempt.settings
    prefix = (
        f"Tune attempt settle={settings.settle_ms}ms samples={settings.samples} "
        f"warmup={settings.warmup_frames} baseline={settings.baseline_frames} "
        f"control_frames={settings.frames}"
    )
    if attempt.error:
        return f"{prefix}: failed {attempt.error}"
    return (
        f"{prefix}: max_relative={attempt.max_relative_rms_percent:.2f}% "
        f"max_rms={attempt.max_rms_kohm:.6f}kOhm "
        f"min_corr={attempt.min_correlation:.6f}"
    )


# Substrings that mark a port as a real USB serial adapter rather than a
# Bluetooth audio device or a system debug console. Matched case-insensitively
# against the whole device path, so they must not be short enough to appear
# inside unrelated words.
USB_SERIAL_HINTS = (
    "usbserial", "usbmodem", "wchusbserial", "slab", "cp210",
    "ttyusb", "ttyacm",
)

# Bluetooth devices expose serial ports and would otherwise be auto-selected.
EXCLUDED_PORT_HINTS = ("bluetooth", "debug-console")

# Windows ports are named COM1, COM2 and so on. Anchored, because the bare
# string "com" also appears inside names like "Bluetooth-Incoming-Port".
WINDOWS_PORT_PATTERN = re.compile(r"^COM\d+$", re.IGNORECASE)


def detect_serial_ports() -> tuple[str, ...]:
    """Serial ports the OS can currently see, likely USB devices first."""
    try:
        from serial.tools import list_ports
    except Exception:
        return ()
    try:
        ports = sorted(port.device for port in list_ports.comports())
    except Exception:
        return ()
    likely = [port for port in ports if is_likely_usb_serial(port)]
    return tuple(likely + [port for port in ports if port not in likely])


def is_likely_usb_serial(port: str) -> bool:
    lowered = port.lower()
    if any(hint in lowered for hint in EXCLUDED_PORT_HINTS):
        return False
    if WINDOWS_PORT_PATTERN.match(port.strip()):
        return True
    return any(hint in lowered for hint in USB_SERIAL_HINTS)


def preferred_port(ports: tuple[str, ...]) -> str | None:
    """The port worth auto-selecting, or None if nothing looks like hardware.

    Bluetooth headsets show up as serial ports too, so picking the first
    detected port would silently point the UI at a pair of earbuds.
    """
    for port in ports:
        if is_likely_usb_serial(port):
            return port
    return None


# ---------------------------------------------------------------------------
# Qt widget layer
# ---------------------------------------------------------------------------

STYLESHEET = f"""
QWidget {{
    background-color: {FACE};
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow {{
    background-color: {FACE};
}}
QGroupBox {{
    background-color: {PANEL};
    border: 1px solid {GRID};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: 600;
    color: {ACCENT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
QLabel {{
    color: {TEXT};
}}
QLabel[role="status"] {{
    color: {MUTED_TEXT};
    font-style: italic;
}}
QLabel[role="saved"] {{
    color: #157a4a;
    font-weight: 600;
}}
QLabel[role="notsaved"] {{
    color: #b5720a;
    font-weight: 600;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {INPUT_BG};
    border: 1px solid {GRID};
    border-radius: 5px;
    padding: 4px 6px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QComboBox::drop-down {{
    border: none;
}}
QPushButton {{
    background-color: {BUTTON_BG};
    border: 1px solid {GRID};
    border-radius: 6px;
    padding: 7px 10px;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: {BUTTON_HOVER};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {ACCENT};
    color: #ffffff;
}}
QPushButton#stopButton {{
    background-color: #c62828;
    border: none;
    color: white;
    font-weight: 700;
    padding: 10px;
}}
QPushButton#stopButton:hover {{
    background-color: #d84343;
}}
QPushButton#rescanButton {{
    padding: 4px 8px;
}}
QTabWidget::pane {{
    border: 1px solid {GRID};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background: {PANEL};
    padding: 7px 14px;
    border: 1px solid {GRID};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {FACE};
    color: {ACCENT};
}}
QTextEdit {{
    background-color: {INPUT_BG};
    border: 1px solid {GRID};
    border-radius: 6px;
    font-family: Menlo, Consolas, monospace;
    font-size: 12px;
}}
QFrame#readingStrip {{
    background-color: {PANEL};
    border: 1px solid {GRID};
    border-radius: 6px;
    padding: 6px;
}}
QLabel[role="reading"] {{
    font-weight: 600;
    font-size: 14px;
    color: {TEXT};
}}
QLabel[role="quality-pending"] {{
    font-weight: 600;
    color: {MUTED_TEXT};
}}
QLabel[role="quality-ok"] {{
    font-weight: 600;
    color: #157a4a;
}}
QLabel[role="quality-bad"] {{
    font-weight: 600;
    color: #c62828;
}}
QLabel[role="chip-pending"] {{
    background-color: {BUTTON_BG};
    color: {MUTED_TEXT};
    border: 1px solid {GRID};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
}}
QLabel[role="chip-current"] {{
    background-color: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[role="chip-done"] {{
    background-color: #e3f5ec;
    color: #157a4a;
    border: 1px solid #9fd9bb;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
"""


class CaptureThread(QThread):
    """Runs one controller action off the GUI thread.

    Qt automatically delivers a signal to a slot in a different thread via a
    queued connection, so status/result signals emitted from run() land safely
    back on the GUI thread without any manual queue or polling.
    """

    status = pyqtSignal(str)
    target_preview = pyqtSignal(list)
    metrics = pyqtSignal(dict)
    succeeded = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(self, name: str, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.name = name
        self.fn = fn

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(self.name, str(exc))
        else:
            self.succeeded.emit(self.name, result)


class DebugApp(QMainWindow):
    def __init__(self, demo: bool, port: str) -> None:
        super().__init__()
        self.setWindowTitle("Phase 3A ERT Hybrid Debug UI")
        self.resize(1240, 800)

        acquisition = DemoAcquisition() if demo else SerialAcquisition()
        self.controller = DebugController(
            acquisition,
            progress=self._on_status,
            target_preview=self._on_target_preview,
            frame_metrics=self._on_metrics,
        )
        self.demo = demo
        self._active_thread: CaptureThread | None = None
        self._settings_store = QSettings("thesis_ert", "TreeErtUI")
        # Which cut-trunk ladder stages have a saved target capture this
        # session, keyed by specimen. Not persisted: it is a reminder for the
        # current sitting, not a record - the CSVs are the record.
        self._ladder_done: dict[str, set[str]] = {}

        self._build_ui(port)
        self._restore_settings()
        self._sync_action_state()
        self._append(self.status_text, "Ready.\n")
        if self.demo:
            self._append(self.serial_text, "Demo acquisition selected; no serial port will be opened.\n")

    # -- layout ------------------------------------------------------

    def _build_ui(self, port: str) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        splitter = QSplitter()
        root.addWidget(splitter)

        sidebar = QWidget()
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(10)
        self._build_session_group(sidebar_layout)
        self._build_connection_group(sidebar_layout, port)
        self._build_acquisition_group(sidebar_layout)
        self._build_run_group(sidebar_layout)
        sidebar_layout.addStretch(1)
        splitter.addWidget(sidebar)

        tabs = self._build_tabs()
        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _build_session_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("1 · What are you scanning?")
        box = QVBoxLayout(group)

        form = QFormLayout()
        self.specimen_combo = QComboBox()
        self.specimen_combo.setEditable(True)
        self.specimen_combo.lineEdit().setPlaceholderText("e.g. trunk-a, phantom")
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(VALID_STAGES)
        self.stage_combo.setCurrentText(LADDER_STAGES[0])
        self.stage_combo.currentTextChanged.connect(self._refresh_ladder_chips)
        self.specimen_combo.currentTextChanged.connect(self._refresh_ladder_chips)
        form.addRow("Specimen", self.specimen_combo)
        form.addRow("Stage", self.stage_combo)
        box.addLayout(form)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(4)
        self.ladder_chips: dict[str, QLabel] = {}
        for stage in LADDER_STAGES:
            chip = QLabel(stage.split("-", 1)[1])
            chip.setProperty("role", "chip-pending")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chips_row.addWidget(chip)
            self.ladder_chips[stage] = chip
        box.addLayout(chips_row)

        layout.addWidget(group)

    def _build_connection_group(self, layout: QVBoxLayout, port: str) -> None:
        group = QGroupBox("2 · Connection")
        box = QVBoxLayout(group)
        self.status_label = QLabel("Demo mode" if self.demo else "Disconnected")
        self.status_label.setProperty("role", "status")
        box.addWidget(self.status_label)

        row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        detected = detect_serial_ports()
        self.port_combo.addItems(detected)
        # A Windows default on a Mac just guarantees a failed connect.
        initial_port = preferred_port(detected) if port == "COM3" else port
        self.port_combo.setCurrentText(initial_port or port)
        row.addWidget(self.port_combo)
        rescan = QPushButton("Rescan")
        rescan.setObjectName("rescanButton")
        rescan.clicked.connect(self.refresh_ports)
        row.addWidget(rescan)
        box.addLayout(row)
        layout.addWidget(group)

    def _build_acquisition_group(self, layout: QVBoxLayout) -> None:
        defaults = UiSettings.default()
        group = QGroupBox("3 · Acquisition")
        form = QFormLayout(group)

        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(("adjacent", "opposite", "skip-1", "skip-2"))
        self.pattern_combo.setCurrentText(defaults.pattern)
        form.addRow("Pattern", self.pattern_combo)

        self.dac_spin = self._int_spin(0, 620, defaults.dac)
        form.addRow("DAC code", self.dac_spin)
        self.settle_spin = self._int_spin(1, 10000, defaults.settle_ms)
        form.addRow("Settle ms", self.settle_spin)
        self.samples_spin = self._int_spin(1, 1000, defaults.samples)
        form.addRow("Samples", self.samples_spin)
        self.warmup_spin = self._int_spin(0, 1000, defaults.warmup_frames)
        form.addRow("Warmup frames", self.warmup_spin)
        self.baseline_spin = self._int_spin(1, 1000, defaults.baseline_frames)
        form.addRow("Baseline frames", self.baseline_spin)
        self.frames_spin = self._int_spin(1, 1000, defaults.frames)
        form.addRow("Run frames", self.frames_spin)

        self.diameter_spin = QDoubleSpinBox()
        self.diameter_spin.setRange(0.0, 500.0)
        self.diameter_spin.setSpecialValueText("(unset)")
        self.diameter_spin.setDecimals(1)
        self.diameter_spin.setSuffix(" cm")
        form.addRow("Diameter", self.diameter_spin)

        layout.addWidget(group)

    @staticmethod
    def _int_spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _build_run_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("4 · Run")
        box = QVBoxLayout(group)
        # Keyed by the same name passed to _run_with_settings, so
        # _sync_action_state can grey out whatever isn't valid yet.
        self.action_buttons: dict[str, QPushButton] = {}
        for name, label, action in (
            ("connect", "Connect", self.connect),
            ("configure", "Configure", self.configure),
            ("baseline", "Baseline", self.capture_baseline),
            ("control", "Control Drift", self.capture_control),
            ("tune", "Tune Drift", self.tune_drift),
            ("target", "Target Run", self.capture_target),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            box.addWidget(button)
            self.action_buttons[name] = button
        layout.addWidget(group)

        self.stop_button = QPushButton("STOP / CURRENT IDLE")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self.stop)
        layout.addWidget(self.stop_button)

        self.saved_label = QLabel("No scan saved yet")
        self.saved_label.setProperty("role", "notsaved")
        self.saved_label.setWordWrap(True)
        layout.addWidget(self.saved_label)

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        reconstruction_tab = QWidget()
        recon_layout = QVBoxLayout(reconstruction_tab)

        reading_frame = QFrame()
        reading_frame.setObjectName("readingStrip")
        reading_row = QHBoxLayout(reading_frame)
        self.current_reading_label = QLabel("Current: —")
        self.current_reading_label.setProperty("role", "reading")
        self.quality_reading_label = QLabel("Quality: —")
        self.quality_reading_label.setProperty("role", "quality-pending")
        self.frame_reading_label = QLabel("")
        self.frame_reading_label.setProperty("role", "status")
        reading_row.addWidget(self.current_reading_label)
        reading_row.addWidget(self.quality_reading_label)
        reading_row.addStretch(1)
        reading_row.addWidget(self.frame_reading_label)
        recon_layout.addWidget(reading_frame)

        self.figure, self.map_ax, self.vector_ax, self.scan_axes = build_reconstruction_figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        recon_layout.addWidget(self.canvas, stretch=1)

        status_group = QGroupBox("Live status stream")
        status_layout = QVBoxLayout(status_group)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        self.status_text.setMaximumHeight(240)
        status_layout.addWidget(self.status_text)
        recon_layout.addWidget(status_group)

        self.health_text = self._readonly_text()
        self.serial_text = self._readonly_text()
        self.files_text = self._readonly_text()

        for title, widget in zip(
            debug_tab_titles(),
            (reconstruction_tab, self.health_text, self.serial_text, self.files_text),
            strict=True,
        ):
            tabs.addTab(widget, title)
        return tabs

    @staticmethod
    def _readonly_text() -> QTextEdit:
        widget = QTextEdit()
        widget.setReadOnly(True)
        return widget

    # -- settings ------------------------------------------------------

    def refresh_ports(self) -> None:
        ports = detect_serial_ports()
        current = self.port_combo.currentText().strip()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        best = preferred_port(ports)
        if best is not None and not is_likely_usb_serial(current):
            self.port_combo.setCurrentText(best)
        else:
            self.port_combo.setCurrentText(current)
        self._append(self.status_text, f"Ports detected: {', '.join(ports) or 'none'}\n")
        if best is None:
            self._append(
                self.status_text,
                "No USB serial device found. Check the cable and that the ESP32-S3 is powered.\n",
            )

    def settings(self) -> UiSettings:
        diameter_value = self.diameter_spin.value()
        return UiSettings(
            port=self.port_combo.currentText().strip(),
            specimen=self.specimen_combo.currentText().strip(),
            stage=self.stage_combo.currentText().strip(),
            pattern=self.pattern_combo.currentText().strip(),
            dac=self.dac_spin.value(),
            settle_ms=self.settle_spin.value(),
            samples=self.samples_spin.value(),
            warmup_frames=self.warmup_spin.value(),
            baseline_frames=self.baseline_spin.value(),
            frames=self.frames_spin.value(),
            diameter_cm=diameter_value if diameter_value > 0 else None,
        ).validate()

    # -- actions ------------------------------------------------------

    def connect(self) -> None:
        self._run_with_settings("connect", self.controller.connect)

    def configure(self) -> None:
        self._run_with_settings("configure", self.controller.configure)

    def capture_baseline(self) -> None:
        self._run_with_settings("baseline", self.controller.capture_baseline)

    def capture_control(self) -> None:
        self._run_with_settings("control", self.controller.capture_control)

    def tune_drift(self) -> None:
        self._run_with_settings("tune", self.controller.tune_drift)

    def capture_target(self) -> None:
        self._run_with_settings("target", self.controller.capture_target)

    def stop(self) -> None:
        worker_was_active = self._active_thread is not None
        if worker_was_active:
            answer = QMessageBox.question(
                self,
                "Stop capture?",
                "A capture is running. Stop it now?\n\n"
                "Frames already written to the CSV stay on disk; the run will "
                "be marked stopped.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.controller.stop()
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText("Stop error")
            self._handle_error(f"stop: {exc}")
            return
        if worker_was_active:
            self.status_label.setText("STOP requested")
            self._append(
                self.status_text,
                "STOP requested; waiting for active capture to finish...\n",
            )
        else:
            self.status_label.setText("STOPPED / CURRENT IDLE")
            self._append(self.status_text, "STOP / CURRENT IDLE sent.\n")
        self._sync_action_state()

    def _run_with_settings(self, name: str, action: Callable[[UiSettings], Any]) -> None:
        try:
            settings = self.settings()
        except Exception as exc:  # noqa: BLE001
            self._handle_error(f"{name}: {exc}")
            return
        self._persist_settings(settings)
        self._run_worker(name, lambda: action(settings))

    def _run_worker(self, name: str, fn: Callable[[], Any]) -> None:
        if self._active_thread is not None:
            self._append(
                self.status_text,
                f"{name} skipped: active capture still finishing.\n",
            )
            return
        self.status_label.setText(f"{name} running")
        self._append(self.status_text, f"{name} started.\n")

        thread = CaptureThread(name, fn)
        thread.status.connect(self._append_status)
        thread.target_preview.connect(self._draw_average)
        thread.metrics.connect(self._update_reading)
        thread.succeeded.connect(self._on_worker_succeeded)
        thread.failed.connect(self._on_worker_failed)
        thread.finished.connect(lambda: self._on_thread_finished(thread))
        self._active_thread = thread
        self._sync_action_state()
        thread.start()

    def _on_thread_finished(self, thread: CaptureThread) -> None:
        if self._active_thread is thread:
            self._active_thread = None
        self._sync_action_state()

    def _append_status(self, message: str) -> None:
        self._append(self.status_text, f"{message}\n")

    def _on_worker_succeeded(self, name: str, payload: object) -> None:
        if "stopped" in str(payload).lower() and name in {"baseline", "control", "target"}:
            self.status_label.setText("STOPPED / CURRENT IDLE")
        else:
            self.status_label.setText(f"{name} complete")
        self._append(self.status_text, f"{name} complete.\n")
        if name == "baseline":
            self._draw_baseline_reference(payload.baseline)
            self._append(self.health_text, f"Baseline: {payload.stability}\n")
            self._note_saved(payload.log_path)
            self._remember_specimen()
        elif name == "control":
            summary = format_control_drift_summary(payload)
            self._append(self.status_text, f"{summary}\n")
            self._append(self.health_text, f"{summary}\n")
        elif name == "tune":
            self._handle_tune_result(payload)
        elif name == "target":
            self._draw_average(payload.reconstructions)
            self._append(self.health_text, f"Target frames: {len(payload.reconstructions)}\n")
            self._note_saved(payload.log_path)
            if payload.log_path is not None:
                self._remember_specimen()
                self._advance_ladder_stage()
        self._sync_action_state()

    def _on_worker_failed(self, name: str, message: str) -> None:
        self._sync_action_state()
        if message == "capture stopped":
            # A deliberate STOP, not a real fault - the operator just
            # confirmed this in the dialog from stop(), so a critical-error
            # popup here would contradict what they were told would happen.
            self.status_label.setText("STOPPED / CURRENT IDLE")
            self._append(self.status_text, f"{name} stopped.\n")
            return
        self.status_label.setText("Error")
        self._handle_error(f"{name}: {message}")

    def _note_saved(self, log_path: object) -> None:
        if log_path is None:
            self.saved_label.setProperty("role", "notsaved")
            self.saved_label.setText("NOT SAVED - logging is off")
            self._refresh_style(self.saved_label)
            self._append(self.files_text, "Capture finished but logging was disabled.\n")
            return
        self.saved_label.setProperty("role", "saved")
        self.saved_label.setText(f"Saved: {getattr(log_path, 'name', log_path)}")
        self._refresh_style(self.saved_label)
        self._append(self.files_text, f"{log_path}\n")

    @staticmethod
    def _refresh_style(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _handle_error(self, message: str) -> None:
        self._append(self.status_text, f"ERROR {message}\n")
        QMessageBox.critical(self, "ERT UI Error", message)

    def _handle_tune_result(self, result: DriftTuneResult) -> None:
        summary = format_drift_tune_summary(result)
        self._append(self.status_text, f"{summary}\n")
        self._append(self.health_text, f"{summary}\n")
        for attempt in result.attempts:
            self._append(self.health_text, f"{format_drift_tune_attempt(attempt)}\n")
        if result.best is not None:
            self._apply_settings_to_fields(result.best.settings)

    def _apply_settings_to_fields(self, settings: UiSettings) -> None:
        self.settle_spin.setValue(settings.settle_ms)
        self.samples_spin.setValue(settings.samples)
        self.warmup_spin.setValue(settings.warmup_frames)
        self.baseline_spin.setValue(settings.baseline_frames)
        self.frames_spin.setValue(settings.frames)

    # -- action availability ------------------------------------------------

    def _sync_action_state(self) -> None:
        """Grey out actions that would fail right now instead of popping an
        error after the click. Mirrors DebugController's own state machine:
        connect -> configure -> baseline -> {control, target}. Everything is
        disabled while a capture is in flight; STOP is the only exception.
        """
        busy = self._active_thread is not None
        state = self.controller.state
        configured = state in {
            ControllerState.CONFIGURED,
            ControllerState.BASELINE_READY,
            ControllerState.TARGET_READY,
        }
        connected = state != ControllerState.DISCONNECTED
        has_baseline = self.controller.baseline_result is not None

        self.action_buttons["connect"].setEnabled(not busy)
        self.action_buttons["configure"].setEnabled(not busy and connected)
        self.action_buttons["baseline"].setEnabled(not busy and configured)
        self.action_buttons["tune"].setEnabled(not busy and connected)
        self.action_buttons["control"].setEnabled(not busy and has_baseline)
        self.action_buttons["target"].setEnabled(not busy and has_baseline)

    # -- settings persistence ------------------------------------------------

    _PERSISTED_SPINS = (
        ("dac", "dac_spin"),
        ("settle_ms", "settle_spin"),
        ("samples", "samples_spin"),
        ("warmup_frames", "warmup_spin"),
        ("baseline_frames", "baseline_spin"),
        ("frames", "frames_spin"),
    )

    def _persist_settings(self, settings: UiSettings) -> None:
        store = self._settings_store
        store.setValue("port", settings.port)
        store.setValue("pattern", settings.pattern)
        for key, _ in self._PERSISTED_SPINS:
            store.setValue(key, getattr(settings, key))
        store.setValue("diameter_cm", settings.diameter_cm or 0.0)

    def _restore_settings(self) -> None:
        store = self._settings_store
        port = store.value("port", type=str)
        if port:
            self.port_combo.setCurrentText(port)
        pattern = store.value("pattern", type=str)
        if pattern:
            self.pattern_combo.setCurrentText(pattern)
        for key, attr in self._PERSISTED_SPINS:
            value = store.value(key, type=int)
            if value is not None:
                getattr(self, attr).setValue(value)
        diameter = store.value("diameter_cm", type=float)
        if diameter:
            self.diameter_spin.setValue(diameter)
        for specimen in store.value("specimen_history", type=list) or []:
            self.specimen_combo.addItem(specimen)

    def _remember_specimen(self) -> None:
        specimen = self.specimen_combo.currentText().strip()
        if not specimen:
            return
        history = [
            self.specimen_combo.itemText(index)
            for index in range(self.specimen_combo.count())
        ]
        history = [specimen] + [item for item in history if item != specimen]
        history = history[:20]
        current_text = self.specimen_combo.currentText()
        self.specimen_combo.blockSignals(True)
        self.specimen_combo.clear()
        self.specimen_combo.addItems(history)
        self.specimen_combo.setCurrentText(current_text)
        self.specimen_combo.blockSignals(False)
        self._settings_store.setValue("specimen_history", history)

    # -- cut-trunk ladder stepper --------------------------------------------

    def _advance_ladder_stage(self) -> None:
        """After a saved target capture, mark the stage done and, if this is
        one of the four ladder stages, move on to the next one. Auto-advancing
        is a convenience only - the operator can always pick a different stage
        from the dropdown, and nothing here writes to disk.
        """
        specimen = self.specimen_combo.currentText().strip()
        stage = self.stage_combo.currentText().strip()
        if not specimen or stage not in LADDER_STAGES:
            return
        self._ladder_done.setdefault(specimen, set()).add(stage)
        self._refresh_ladder_chips()
        position = LADDER_STAGES.index(stage)
        if position + 1 < len(LADDER_STAGES):
            self.stage_combo.setCurrentText(LADDER_STAGES[position + 1])

    def _refresh_ladder_chips(self) -> None:
        specimen = self.specimen_combo.currentText().strip()
        done = self._ladder_done.get(specimen, set())
        current_stage = self.stage_combo.currentText().strip()
        for stage, chip in self.ladder_chips.items():
            if stage in done:
                role = "chip-done"
            elif stage == current_stage:
                role = "chip-current"
            else:
                role = "chip-pending"
            chip.setProperty("role", role)
            self._refresh_style(chip)

    # -- plotting ------------------------------------------------------

    def _on_status(self, message: str) -> None:
        # Called from the controller, which may run on the worker thread; the
        # active CaptureThread relays it via its own status signal instead so
        # emission always happens from the thread that owns the connection.
        if self._active_thread is not None:
            self._active_thread.status.emit(message)
        else:
            self._append_status(message)

    def _on_target_preview(self, reconstructions: list[np.ndarray]) -> None:
        if self._active_thread is not None:
            self._active_thread.target_preview.emit(list(reconstructions))
        else:
            self._draw_average(reconstructions)

    def _on_metrics(self, payload: dict) -> None:
        if self._active_thread is not None:
            self._active_thread.metrics.emit(payload)
        else:
            self._update_reading(payload)

    def _update_reading(self, payload: dict) -> None:
        self.current_reading_label.setText(
            f"Current: {payload['current_median_ua']:.1f} µA "
            f"(spread {payload['current_spread_ua']:.1f} µA)"
        )
        quality = payload["quality"]
        self.quality_reading_label.setText(f"Quality: {quality}")
        role = "quality-ok" if quality.upper() in {"OK", ""} else "quality-bad"
        self.quality_reading_label.setProperty("role", role)
        self._refresh_style(self.quality_reading_label)
        self.frame_reading_label.setText(
            f"{payload['phase']} frame {payload['frame']}/{payload['total']}"
        )

    def _draw_average(self, reconstructions: list[np.ndarray]) -> None:
        average = average_reconstruction_vector(reconstructions)
        self._draw_average_map(average)
        self._draw_average_vector(average)
        self._draw_scan_previews(reconstructions)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _draw_baseline_reference(self, baseline: np.ndarray) -> None:
        self.map_ax.clear()
        self.map_ax.set_facecolor(FACE)
        self.map_ax.set_title("Baseline reference", color=TEXT)
        self.map_ax.set_aspect("equal")
        self.map_ax.set_axis_off()
        self.map_ax.text(
            0.5,
            0.5,
            "Baseline vs itself = zero difference\nUse this as reference, not target image",
            ha="center",
            va="center",
            color=TEXT,
            transform=self.map_ax.transAxes,
        )
        self.vector_ax.clear()
        self.vector_ax.set_facecolor(FACE)
        self.vector_ax.set_title("Baseline measurement vector", color=TEXT)
        self.vector_ax.set_xlabel("Measurement index", color=TEXT)
        self.vector_ax.set_ylabel("Transfer resistance", color=TEXT)
        self.vector_ax.tick_params(colors=TEXT)
        if baseline.size:
            self.vector_ax.plot(baseline, color=ACCENT)
            self.vector_ax.axhline(0.0, color=GRID, linewidth=0.8, alpha=0.8)
        else:
            self.vector_ax.text(0.5, 0.5, "No baseline data", ha="center", va="center", color=TEXT)
        for axis in self.scan_axes:
            axis.clear()
            axis.set_facecolor(FACE)
            axis.set_axis_off()
            axis.text(0.5, 0.5, "Run target\nto compare scans", ha="center", va="center", color=TEXT)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _draw_average_map(self, average: np.ndarray) -> None:
        self.map_ax.clear()
        self.map_ax.set_facecolor(FACE)
        self.map_ax.set_title("Average 2D map", color=TEXT)
        self.map_ax.set_aspect("equal")
        self.map_ax.set_axis_off()
        mesh = self.controller.mesh
        if average.size == 0:
            self.map_ax.text(0.5, 0.5, "No reconstruction data", ha="center", va="center", color=TEXT)
            return
        if mesh is None or len(average) != len(mesh.element):
            self.map_ax.text(0.5, 0.5, "Map unavailable", ha="center", va="center", color=TEXT)
            return
        limit = max(float(np.max(np.abs(average))), np.finfo(float).eps)
        self.map_ax.tripcolor(
            mesh.node[:, 0],
            mesh.node[:, 1],
            mesh.element,
            average,
            shading="flat",
            cmap="coolwarm",
            vmin=-limit,
            vmax=limit,
        )
        for index in range(N_ELECTRODES):
            angle = 2.0 * np.pi * index / N_ELECTRODES
            self.map_ax.text(
                1.12 * np.cos(angle),
                1.12 * np.sin(angle),
                f"E{index + 1}",
                ha="center",
                va="center",
                fontsize=7,
                fontweight="bold",
                color=TEXT,
            )

    def _draw_average_vector(self, average: np.ndarray) -> None:
        self.vector_ax.clear()
        self.vector_ax.set_facecolor(FACE)
        self.vector_ax.set_title("Average reconstruction vector", color=TEXT)
        self.vector_ax.set_xlabel("Vector index", color=TEXT)
        self.vector_ax.set_ylabel("Difference", color=TEXT)
        self.vector_ax.tick_params(colors=TEXT)
        if average.size:
            self.vector_ax.plot(average, color=ACCENT)
            self.vector_ax.axhline(0.0, color=GRID, linewidth=0.8, alpha=0.8)
        else:
            self.vector_ax.text(0.5, 0.5, "No reconstruction data", ha="center", va="center", color=TEXT)

    def _draw_scan_previews(self, reconstructions: list[np.ndarray]) -> None:
        indices = preview_scan_indices(len(reconstructions), len(self.scan_axes))
        values = [reconstructions[index] for index in indices]
        limit = max(
            [float(np.max(np.abs(value))) for value in values if value.size] or [np.finfo(float).eps],
        )
        mesh = self.controller.mesh
        for preview_position, axis in enumerate(self.scan_axes):
            axis.clear()
            axis.set_facecolor(FACE)
            axis.set_axis_off()
            if preview_position >= len(indices):
                axis.set_title("Scan", color=TEXT)
                axis.text(0.5, 0.5, "No scan", ha="center", va="center", color=TEXT)
                continue
            scan_index = indices[preview_position]
            value = reconstructions[scan_index]
            axis.set_title(f"Scan {scan_index + 1}", color=TEXT)
            if mesh is None or len(value) != len(mesh.element):
                axis.text(0.5, 0.5, "Map unavailable", ha="center", va="center", color=TEXT)
                continue
            axis.tripcolor(
                mesh.node[:, 0],
                mesh.node[:, 1],
                mesh.element,
                value,
                shading="flat",
                cmap="coolwarm",
                vmin=-limit,
                vmax=limit,
            )

    # -- lifecycle ------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if self._active_thread is not None:
            self.controller.stop()
            self._active_thread.wait(2000)
        try:
            self.controller.close()
        except Exception as exc:  # noqa: BLE001
            self._append(self.status_text, f"ERROR close: {exc}\n")
        event.accept()

    @staticmethod
    def _append(widget: QTextEdit, text: str) -> None:
        widget.moveCursor(widget.textCursor().MoveOperation.End)
        widget.insertPlainText(text)
        widget.moveCursor(widget.textCursor().MoveOperation.End)


def run_app(demo: bool = False, port: str = "COM3") -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    window = DebugApp(demo=demo, port=port)
    window.show()
    app.exec()
