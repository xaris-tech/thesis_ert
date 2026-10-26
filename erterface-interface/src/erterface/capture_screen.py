"""CaptureScreen — the scan screen. Embeds the thesis repo's PyQt6 capture
session (``tree_ert.qt.main_window.MainWindow``, the "orig interface")
under a slim farm header with Back and Save to tree.

The capture window owns everything instrument-side: serial settings,
conditions, run recording under ``<thesis root>/scans`` and the
reconstruction gates. This screen only names the specimen after the tree
and, once a run has been recorded, turns it into a farm Measurement that
points at the run's image and folder.

The instrument reports images, not a health verdict, so the Measurement is
saved as UNCLASSIFIED with no impedance ratio rather than inventing one.
"""

import re
import sys
from pathlib import Path

from PyQt6.QtCore import QDateTime, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .models import Measurement
from .widgets.keyboard import KeyboardOnTap
from .paths import CLASSIFICATION_UNCLASSIFIED, THESIS_ROOT

SCANS_DIR = THESIS_ROOT / "scans"

# Difference image first (what changed against the baseline), else the
# run's absolute image; the tomogram-only display copy of each where it
# exists (ADR-0074), else the full figure (runs from before it).
RUN_IMAGES = (
    "reconstruction-image.png", "reconstruction.png",
    "absolute-image.png", "absolute.png",
)


def _import_capture_window():
    if str(THESIS_ROOT) not in sys.path:
        sys.path.insert(0, str(THESIS_ROOT))
    from tree_ert.qt.main_window import MainWindow
    return MainWindow


def create_session():
    """The capture session (the thesis repo's MainWindow, compact). Owned by
    CardApp for the app's lifetime and lent to each CaptureScreen."""
    MainWindow = _import_capture_window()
    session = MainWindow(log_dir=SCANS_DIR, demo=not _serial_port_present(), compact=True)
    session.setWindowFlags(Qt.WindowType.Widget)
    return session


def _serial_port_present():
    try:
        from serial.tools import list_ports
    except ImportError:
        return False
    # USB only: the Pi's own UARTs (ttyAMA0, ttyS0) are always listed.
    return any(port.vid is not None for port in list_ports.comports())


def specimen_id_for(tree):
    """``T002`` → ``coconut-tree-2``, matching run_record.SPECIMEN_ID_PATTERN."""
    digits = re.search(r"\d+", tree.tree_id or "")
    return f"coconut-tree-{int(digits.group())}" if digits else ""


def run_impedance_ratio(run_dir):
    """(p90/p10 impedance ratio, drive pattern) of a recorded run (ADR-0075),
    or (None, pattern) if it cannot be computed. Never raises: a ratio must not
    stop a scan being saved."""
    from tree_ert import capture_view, survey  # importable once the session is

    try:
        frames = survey.load_frames(Path(run_dir))
        pattern = frames[0].pattern.lower() if frames else ""
        return capture_view.impedance_ratio(frames), pattern
    except Exception:  # noqa: BLE001
        return None, ""


def run_image(run_dir):
    for name in RUN_IMAGES:
        path = Path(run_dir) / name
        if path.exists():
            return str(path)
    return ""


class CaptureScreen(QWidget):
    back_requested = pyqtSignal()
    measurement_created = pyqtSignal(object)

    def __init__(self, tree, session, is_dark_mode=False, parent=None):
        super().__init__(parent)
        self.tree = tree
        self.measurement = None
        self.is_dark_mode = is_dark_mode
        self._run_dir = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame()
        top.setObjectName("captureTop")
        top.setFixedHeight(theme.TOUCH_MIN + 10)
        self._top = top
        bar = QHBoxLayout(top)
        bar.setContentsMargins(8, 4, 8, 4)
        bar.setSpacing(8)

        btn_back = QPushButton("← Back")
        btn_back.setObjectName("headerBtn")
        btn_back.setFixedHeight(theme.TOUCH_MIN)
        btn_back.clicked.connect(self._on_back)
        bar.addWidget(btn_back)

        title = QLabel(f"Scan · {tree.name}")
        self._title = title
        title.setObjectName("headerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(title, stretch=1)

        # Settings column toggle. The column hides itself when a capture
        # starts so the frames table and images get the full width.
        self.btn_settings = QPushButton("Hide settings")
        self.btn_settings.setObjectName("headerBtn")
        self.btn_settings.setFixedHeight(theme.TOUCH_MIN)
        self.btn_settings.clicked.connect(lambda: self._show_controls(not self._controls_shown))
        bar.addWidget(self.btn_settings)

        self.btn_save = QPushButton("Save to tree")
        self.btn_save.setFixedHeight(theme.TOUCH_MIN)
        self.btn_save.setEnabled(False)
        self.btn_save.setToolTip("Enabled once a run has been recorded")
        self.btn_save.setStyleSheet(
            "QPushButton { font-size: 15px; font-weight: 700; padding: 0 14px; "
            f"background-color: {theme.STATUS_HEALTHY}; color: #ffffff; border: none; border-radius: 8px; }}"
            "QPushButton:disabled { background-color: #6a7286; }"
        )
        self.btn_save.clicked.connect(self._on_save)
        bar.addWidget(self.btn_save)

        for btn in top.findChildren(QPushButton):  # touch UI: no focus rectangles
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(top)

        # The session is the app's (create_session), not this screen's: it
        # outlives Back, so its baseline does too. One session per screen made
        # every run after a Back the baseline of a new session, and nothing
        # was ever differenced (2026-10-26).
        self.session = session
        self.session.run_finished.connect(self._on_run_finished)
        self.session.running_changed.connect(self._on_running_changed)
        self._controls_shown = True
        self._show_controls(not self.session.stop_button.isEnabled())
        # Name the specimen after the tree, unless the operator typed their own
        # (e.g. disc-05): only replace blank or our own earlier pre-fill.
        panel = self.session.conditions_panel
        current = panel.specimen_id.text().strip()
        if not current or current == self.session.property("farm_prefill"):
            panel.specimen_id.setText(specimen_id_for(tree))
        self.session.setProperty("farm_prefill", specimen_id_for(tree))
        root.addWidget(self.session, stretch=1)
        self.session.show()

        # On-screen keyboard for the session's own text and number fields
        # (specimen, target, label, saline...): they are plain QLineEdits, so
        # on a touchscreen with no keyboard they could not be typed into.
        self.keyboard_holder = QWidget()
        self.keyboard_holder.setVisible(False)
        kb_layout = QVBoxLayout(self.keyboard_holder)
        kb_layout.setContentsMargins(6, 2, 6, 4)
        root.addWidget(self.keyboard_holder)
        taps = self.session.findChild(KeyboardOnTap)
        if taps is None:
            taps = KeyboardOnTap(parent=self.session)
            taps.watch(self.session)
        taps.is_dark_mode = is_dark_mode
        self.set_dark_mode(is_dark_mode)

    def set_dark_mode(self, dark):
        """Theme the header and the embedded session together. In place: a
        rebuild would hand the session back and stop a capture."""
        self.is_dark_mode = dark
        c = theme.palette(dark)
        self._top.setStyleSheet(
            f"QFrame#captureTop {{ background-color: {c['surface']}; "
            f"border-bottom: 1px solid {c['border']}; }}"
            f"QLabel#headerTitle {{ color: {c['text']}; font-size: 17px; font-weight: 700; "
            f"background: transparent; border: none; }}"
            f"QPushButton#headerBtn {{ font-size: 15px; font-weight: 700; padding: 0 14px; "
            f"background-color: {c['neutral']}; color: {c['neutral_text']}; "
            f"border: 1px solid {c['border']}; border-radius: 8px; }}"
            f"QPushButton#headerBtn:pressed {{ background-color: {c['pressed']}; }}"
        )
        self.setStyleSheet(f"CaptureScreen {{ background-color: {c['bg']}; }}")
        self.session.set_dark_mode(dark)
        keyboard_taps = self.session.findChild(KeyboardOnTap)
        if keyboard_taps is not None:
            keyboard_taps.is_dark_mode = dark

    def _on_running_changed(self, running):
        if running:
            self._show_controls(False)

    def _show_controls(self, shown):
        self._controls_shown = shown
        self.session.set_controls_visible(shown)
        self.btn_settings.setText("Hide settings" if shown else "Settings")

    def _on_run_finished(self, run_path):
        self._run_dir = run_path
        self._ratio, self._pattern = run_impedance_ratio(run_path)
        self.btn_save.setEnabled(True)
        if self._ratio is not None:
            self._title.setText(
                f"Scan · {self.tree.name} · ratio {self._ratio:.2f} ({self._pattern})"
            )

    def _on_save(self):
        if self._run_dir is None:
            return
        m = Measurement(
            self._ratio,
            CLASSIFICATION_UNCLASSIFIED,
            QDateTime.currentDateTime(),
            data_path=self._run_dir,
            image_path=run_image(self._run_dir),
            pattern=self._pattern,
        )
        self.measurement_created.emit(m)
        self._run_dir = None
        self.btn_save.setEnabled(False)

    def _on_back(self):
        self.back_requested.emit()

    def shutdown(self):
        """Hand the session back to the app window. A capture still running is
        stopped (cooperatively, after the current frame), as leaving always did."""
        if self.session.stop_button.isEnabled():
            self.session.stop_capture()
        self.session.run_finished.disconnect(self._on_run_finished)
        self.session.running_changed.disconnect(self._on_running_changed)
        self.session.hide()
        self.session.setParent(self.window())
