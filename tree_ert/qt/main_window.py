"""Session-driver window: configure, record conditions, capture, inspect raw values.

Scope is deliberately narrow (ADR-0024). This is the front-end for a saline-tank
titration session: pick a port, declare the instrument settings and the physical
conditions, capture N frames into a run folder, and watch the raw values and the
reciprocity number as they arrive. There is no reconstruction view -- during
titration the image is the least useful thing on screen, and the numbers that
decide whether a step landed are all scalar.

Widget code here stays thin. Everything worth testing lives in
``tree_ert.capture_view`` (pure) and ``run_record`` (pure), which is why this
module has no tests of its own beyond construction.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import run_record
from run_record import Conditions, SessionLog
from tree_ert import capture_view
from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.qt import theme
from tree_ert.qt.worker import (
    CaptureRequest,
    CaptureWorker,
    SessionBaseline,
    available_ports,
)
from tree_ert.settings import (
    SPECIMEN_PRESETS,
    VALID_CURRENT_RANGES,
    VALID_PATTERNS,
    SpecimenPreset,
    UiSettings,
    load_settings,
    matching_preset,
    preset_by_name,
    save_settings,
    settings_path,
)

CUSTOM_PRESET_LABEL = "Custom"

RAW_COLUMNS = ["#", "Pol", "I+", "I-", "V+", "V-", "V mV", "I uA", "R kohm", "Q"]

# Narrow columns are sized to their content; only the three measurement columns
# absorb the leftover width. Stretching all ten truncated the headers of the
# ones that actually carry numbers.
NARROW_COLUMNS = (0, 1, 2, 3, 4, 5, 9)

# Columns whose value is an electrode label rather than a measurement. Dimmed so
# the eye lands on the numbers, which is what changes between frames.
LABEL_COLUMNS = (0, 2, 3, 4, 5)

# How many times the noise image a difference must exceed before it is called
# anything other than noise. Two is deliberately modest: it is a floor below
# which a claim is certainly unsupportable, not a threshold above which one is
# established (ADR-0027).
SIGNIFICANCE_THRESHOLD = 2.0
from tree_ert.reconstruction import RECIPROCITY_GATE_PERCENT  # noqa: E402


def _tidy_form(layout: QFormLayout) -> None:
    """Make a form shrink gracefully instead of clipping its fields.

    Two settings, both needed. ``AllNonFixedFieldsGrow`` lets the field column
    give width back when the pane is narrow; without it the fields hold their
    size hint and the pane clips them. ``WrapLongRows`` drops the label above
    its field once the row will not fit, which is what makes the panel usable at
    Raspberry Pi display widths rather than merely not-broken.
    """
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(8)


class ConditionsPanel(QGroupBox):
    """Physical state of the specimen, recorded with every run (ADR-0023).

    Every field is optional, and an unfilled field is recorded as "not measured"
    rather than silently omitted. Grounding is the exception the operator is
    nudged about: it is the discriminator for the CMRR hypothesis behind the
    57.5 percent reciprocity violation, so an unset value costs the run its place
    in that comparison.
    """

    def __init__(self) -> None:
        super().__init__("Conditions")
        layout = QFormLayout(self)

        self.medium = QLineEdit("saline tank")
        self.saline = self._number(" g/L", maximum=500.0, step=0.1)
        self.fill_depth = self._number(" mm", maximum=1000.0, step=1.0)
        self.temperature = self._number(" C", minimum=-10.0, maximum=100.0, step=0.1)
        self.protrusion = self._number(" mm", maximum=200.0, step=0.5)

        self.grounding = QComboBox()
        self.grounding.addItems(["unknown", "floating", "grounded"])

        self.contents = QLineEdit()
        self.contents.setPlaceholderText("empty / steel rod at E3, r=0.6")
        self.target = QLineEdit()
        self.target.setPlaceholderText("blank for a baseline run")
        self.electrode_map = QLineEdit("E1 = marked nail, clockwise viewed from above")

        self.specimen_id = QLineEdit()
        self.specimen_id.setPlaceholderText("disc-03 / coconut-tree-1")
        self.circumference = self._number(" mm", maximum=5000.0, step=1.0)
        self.thickness = self._number(" mm", maximum=5000.0, step=1.0)
        self.major_diameter = self._number(" mm", maximum=2000.0, step=1.0)
        self.minor_diameter = self._number(" mm", maximum=2000.0, step=1.0)
        self.nail_arcs = QLineEdit()
        self.nail_arcs.setPlaceholderText("12 arc positions from E1, mm, comma separated")

        self.operator = QLineEdit()
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(60)
        self.notes.setPlaceholderText("anything the fields above do not cover")

        layout.addRow("Medium", self.medium)
        layout.addRow("Saline", self.saline)
        layout.addRow("Fill depth", self.fill_depth)
        layout.addRow("Water temp", self.temperature)
        layout.addRow("Electrode tip", self.protrusion)
        layout.addRow("Grounding", self.grounding)
        layout.addRow("Tank contents", self.contents)
        layout.addRow("Target", self.target)
        layout.addRow("Electrode map", self.electrode_map)
        layout.addRow("Specimen", self.specimen_id)
        layout.addRow("Circumference", self.circumference)
        layout.addRow("Thickness", self.thickness)
        layout.addRow("Major diameter", self.major_diameter)
        layout.addRow("Minor diameter", self.minor_diameter)
        layout.addRow("Nail arcs", self.nail_arcs)
        layout.addRow("Operator", self.operator)
        layout.addRow("Notes", self.notes)
        _tidy_form(layout)

    @staticmethod
    def _number(
        suffix: str, minimum: float = 0.0, maximum: float = 1000.0, step: float = 1.0
    ) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setSuffix(suffix)
        box.setDecimals(2)
        box.setSingleStep(step)
        box.setRange(minimum - 1.0, maximum)
        box.setSpecialValueText("not measured")
        box.setValue(minimum - 1.0)
        return box

    @staticmethod
    def _value(box: QDoubleSpinBox) -> float | None:
        """None when the box is at its "not measured" sentinel."""
        return None if box.value() < box.minimum() + 0.5 else box.value()

    def conditions(self) -> Conditions:
        return Conditions(
            medium=self.medium.text().strip() or "unknown",
            saline_g_per_l=self._value(self.saline),
            fill_depth_mm=self._value(self.fill_depth),
            water_temp_c=self._value(self.temperature),
            electrode_protrusion_mm=self._value(self.protrusion),
            grounding=self.grounding.currentText(),
            tank_contents=self.contents.text().strip(),
            target_description=self.target.text().strip(),
            electrode_map=self.electrode_map.text().strip(),
            specimen_id=self.specimen_id.text().strip(),
            circumference_mm=self._value(self.circumference),
            thickness_mm=self._value(self.thickness),
            major_diameter_mm=self._value(self.major_diameter),
            minor_diameter_mm=self._value(self.minor_diameter),
            operator=self.operator.text().strip(),
            notes=self.notes.toPlainText().strip(),
            extra=self._extra(),
        )

    def _extra(self) -> dict[str, object]:
        """Free-form conditions that have no column of their own.

        The twelve nail arc positions live here rather than as twelve fields:
        nothing sorts or filters by them, and a list is the shape the offline
        geometry check wants anyway.
        """
        text = self.nail_arcs.text().strip()
        if not text:
            return {}
        arcs: list[float] = []
        for part in text.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                arcs.append(float(part))
            except ValueError:
                # An unparseable entry is kept verbatim rather than dropped:
                # a capture already taken must always be recordable (ADR-0023).
                return {"nail_arc_mm_raw": text}
        return {"nail_arc_mm": arcs} if arcs else {"nail_arc_mm_raw": text}


class SettingsPanel(QGroupBox):
    """Instrument settings, a subset of :class:`UiSettings`.

    Only the fields a tank session actually changes are exposed. The rest keep
    their stored or default values and are still recorded in full with the run,
    so a setting that is not on screen is not therefore undocumented.
    """

    def __init__(self, settings: UiSettings) -> None:
        super().__init__("Instrument")
        self._base = settings
        # Guards the two-way binding between the preset combo and the fields it
        # drives: applying a preset must not read back as a manual edit.
        self._applying_preset = False
        layout = QFormLayout(self)

        self.port = QComboBox()
        self.port.setEditable(True)
        # Port descriptions can be long ("USB Serial Device (COM12)"), and by
        # default a combo demands enough width for its widest item, which drags
        # the whole settings pane wider than the window can spare.
        self.port.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.port.setMinimumContentsLength(12)
        self.refresh_ports(settings.port)

        # Sits beside the field it refreshes rather than on a row of its own:
        # a full-width button for a secondary action read as the primary one.
        # Plain text rather than a glyph: a refresh arrow is not guaranteed to
        # exist in the fonts a Raspberry Pi image ships, and a missing glyph
        # renders as an empty box.
        self.refresh = QPushButton("Rescan")
        self.refresh.setObjectName("Subtle")
        self.refresh.setToolTip("Rescan serial ports")
        self.refresh.clicked.connect(lambda: self.refresh_ports(self.port.currentText()))

        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(6)
        port_layout.addWidget(self.port, stretch=1)
        port_layout.addWidget(self.refresh)

        self.demo = QCheckBox("Demo mode (no hardware)")

        # Presets carry provenance rather than bare numbers, so an operator can
        # see what a profile actually measured before adopting it.
        self.preset = QComboBox()
        self.preset.addItem(CUSTOM_PRESET_LABEL)
        for preset in SPECIMEN_PRESETS:
            self.preset.addItem(preset.name)
        self.preset_note = QLabel()
        self.preset_note.setObjectName("Subtle")
        self.preset_note.setWordWrap(True)

        self.pattern = QComboBox()
        self.pattern.addItems(VALID_PATTERNS)
        self.pattern.setCurrentText(settings.pattern)

        self.current_range = QComboBox()
        self.current_range.addItems(VALID_CURRENT_RANGES)
        self.current_range.setCurrentText(settings.current_range)
        self.current_range.currentTextChanged.connect(self._apply_dac_ceiling)

        self.dac = QSpinBox()
        self.dac.setRange(0, 4095)
        self.dac.setValue(settings.dac)

        self.settle = QSpinBox()
        self.settle.setRange(1, 5000)
        self.settle.setSuffix(" ms")
        self.settle.setValue(settings.settle_ms)

        self.samples = QSpinBox()
        self.samples.setRange(1, 256)
        self.samples.setValue(settings.samples)

        self.warmup = QSpinBox()
        self.warmup.setRange(0, 100)
        self.warmup.setValue(settings.warmup_frames)

        self.frames = QSpinBox()
        self.frames.setRange(1, 500)
        self.frames.setValue(max(settings.frames, 1))

        layout.addRow("Port", port_row)
        layout.addRow("", self.demo)
        layout.addRow("Preset", self.preset)
        layout.addRow("", self.preset_note)
        layout.addRow("Pattern", self.pattern)
        layout.addRow("Current range", self.current_range)
        layout.addRow("DAC code", self.dac)
        layout.addRow("Settle", self.settle)
        layout.addRow("Samples", self.samples)
        layout.addRow("Warmup frames", self.warmup)
        layout.addRow("Capture frames", self.frames)
        _tidy_form(layout)

        self._apply_dac_ceiling(self.current_range.currentText())

        # Connected after the initial values are in place, so building the
        # panel does not read as the operator editing it.
        self.preset.currentTextChanged.connect(self._preset_chosen)
        for widget in (self.pattern, self.current_range):
            widget.currentTextChanged.connect(self._mark_custom)
        for widget in (self.dac, self.settle, self.samples, self.warmup, self.frames):
            widget.valueChanged.connect(self._mark_custom)
        self._show_matching_preset()

    def _preset_chosen(self, name: str) -> None:
        """Push a preset into the widgets, or do nothing for Custom."""
        preset = preset_by_name(name)
        if preset is None:
            return
        self._base = preset.apply_to(self._base)
        self._applying_preset = True
        try:
            self.pattern.setCurrentText(preset.pattern)
            self.current_range.setCurrentText(preset.current_range)
            self._apply_dac_ceiling(preset.current_range)
            self.dac.setValue(preset.dac)
            self.settle.setValue(preset.settle_ms)
            self.samples.setValue(preset.samples)
            self.warmup.setValue(preset.warmup_frames)
            self.frames.setValue(preset.frames)
        finally:
            self._applying_preset = False
        self._set_preset_note(preset)

    def _mark_custom(self, *_args: object) -> None:
        """An edited field means the profile is no longer the named preset.

        Left showing the preset's name, the panel would claim a provenance the
        settings no longer have. An edit that happens to land back on a preset
        re-selects it, which is why the match is recomputed rather than assumed.
        """
        if self._applying_preset:
            return
        self._show_matching_preset()

    def _show_matching_preset(self) -> None:
        preset = matching_preset(self.settings())
        self._applying_preset = True
        try:
            self.preset.setCurrentText(
                preset.name if preset else CUSTOM_PRESET_LABEL
            )
        finally:
            self._applying_preset = False
        self._set_preset_note(preset)

    def _set_preset_note(self, preset: SpecimenPreset | None) -> None:
        if preset is None:
            self.preset_note.setText("Custom profile - not from a recorded run.")
            return
        prefix = "" if preset.validated else "PROVISIONAL. "
        self.preset_note.setText(f"{prefix}{preset.provenance}")

    def refresh_ports(self, keep: str = "") -> None:
        current = keep or self.port.currentText()
        self.port.clear()
        for device, description in available_ports():
            self.port.addItem(f"{device}  ({description})", device)
        if current:
            self.port.setEditText(current)

    def _apply_dac_ceiling(self, range_name: str) -> None:
        """Clamp the DAC spinner to the selected range's ceiling.

        The firmware enforces this too (ADR-0011), but silently: a code above
        the ceiling is clipped, so the recorded setting would not match the
        current actually driven. Clamping here keeps the record honest.
        """
        ceiling = UiSettings(current_range=range_name).max_dac_code()
        self.dac.setMaximum(ceiling)
        self.dac.setToolTip(f"0-{ceiling} on the {range_name} current range")

    def selected_port(self) -> str:
        data = self.port.currentData()
        text = self.port.currentText()
        # An edited combo returns the typed text; a chosen item returns the
        # device, since the visible label carries a human description too.
        return data if data and text.startswith(str(data)) else text.split("  (")[0]

    def settings(self) -> UiSettings:
        from dataclasses import replace

        return replace(
            self._base,
            port=self.selected_port().strip(),
            pattern=self.pattern.currentText(),
            current_range=self.current_range.currentText(),
            dac=self.dac.value(),
            settle_ms=self.settle.value(),
            samples=self.samples.value(),
            warmup_frames=self.warmup.value(),
            frames=self.frames.value(),
        )


class MainWindow(QMainWindow):
    def __init__(self, log_dir: Path | None = None, demo: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Tree ERT - capture session")
        self.resize(1180, 820)

        self._log_dir = Path(log_dir or "phase3a_logs")
        self._settings = (
            load_settings(settings_path(self._log_dir)) or UiSettings.default()
        )
        # Opened before anything else can log. Everything the log pane shows is
        # mirrored here, so closing the window does not lose the session.
        self._session_log = SessionLog(self._log_dir)
        self._thread: QThread | None = None
        self._worker: CaptureWorker | None = None
        self._frames: list = []
        self._run_path: Path | None = None
        self._expected_frames = 0
        self._baseline: SessionBaseline | None = None
        """First run of the session. Every later run differences against it."""

        self.setStyleSheet(theme.stylesheet())

        self.settings_panel = SettingsPanel(self._settings)
        self.settings_panel.demo.setChecked(demo)
        self.conditions_panel = ConditionsPanel()

        self.label = QLineEdit("tank-baseline")
        self.start_button = QPushButton("Start capture")
        self.start_button.setObjectName("Primary")
        self.start_button.clicked.connect(self.start_capture)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("Danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_capture)
        self.photo_button = QPushButton("Attach photo")
        self.photo_button.setObjectName("Subtle")
        self.photo_button.setEnabled(False)
        self.photo_button.clicked.connect(self.attach_photo)
        self.open_button = QPushButton("Open run folder")
        self.open_button.setObjectName("Subtle")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_run_folder)
        self.scans_button = QPushButton("Open scans folder")
        self.scans_button.setObjectName("Subtle")
        self.scans_button.clicked.connect(self.open_scans_folder)
        self.clear_baseline_button = QPushButton("Clear baseline")
        self.clear_baseline_button.setObjectName("Subtle")
        self.clear_baseline_button.setEnabled(False)
        self.clear_baseline_button.clicked.connect(self.clear_baseline)
        self.baseline_label = QLabel("Next run becomes the session baseline.")
        self.baseline_label.setWordWrap(True)
        self.override_reciprocity = QCheckBox(
            "Image despite failed reciprocity (stamped NOT VALID)"
        )
        self.override_reciprocity.setToolTip(
            "Reciprocity must be under "
            f"{RECIPROCITY_GATE_PERCENT:.0f}% median before an image is made "
            "(ADR-0030). Ticking this images anyway and marks the image, its "
            "text file and the index row as overridden."
        )

        self.setCentralWidget(self._build_layout())

        self._session_log.banner(f"Session started ({'demo' if demo else 'hardware'})")
        existing = len(run_record.list_runs(self._log_dir))
        self._log(f"Scans folder: {self._log_dir.resolve()}")
        self._log(f"{existing} scan(s) already recorded here.")
        self._log("Ready. Settings are saved on exit.")

    # -- layout ----------------------------------------------------------

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("HeaderBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 12, 18, 12)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("Tree ERT")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Phase 3A capture session")
        subtitle.setObjectName("HeaderSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)

        self.run_status = QLabel("Idle")
        self.run_status.setObjectName("StatusPill")

        layout.addLayout(titles)
        layout.addStretch(1)
        layout.addWidget(self.run_status)
        return header

    def _build_left_column(self) -> QWidget:
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(14, 10, 14, 14)
        inner_layout.setSpacing(12)
        inner_layout.addWidget(self.settings_panel)
        inner_layout.addWidget(self.conditions_panel)

        run_box = QGroupBox("Run")
        run_layout = QVBoxLayout(run_box)
        run_layout.setSpacing(10)
        form = QFormLayout()
        form.addRow("Label", self.label)
        _tidy_form(form)
        run_layout.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, stretch=2)
        buttons.addWidget(self.stop_button, stretch=1)
        run_layout.addLayout(buttons)
        extras = QHBoxLayout()
        extras.addWidget(self.photo_button)
        extras.addWidget(self.open_button)
        run_layout.addLayout(extras)
        run_layout.addWidget(self.scans_button)
        run_layout.addWidget(self.baseline_label)
        run_layout.addWidget(self.clear_baseline_button)
        run_layout.addWidget(self.override_reciprocity)
        inner_layout.addWidget(run_box)
        inner_layout.addStretch(1)

        # The conditions form is tall, and a Raspberry Pi display is not. Scroll
        # the whole left column rather than letting the form dictate a minimum
        # window height the target hardware cannot satisfy.
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Floor the pane at the width the forms actually need, measured rather
        # than guessed. A constant here was wrong twice: with horizontal
        # scrolling off, a pane narrower than its content silently clips the
        # fields at the divider instead of scrolling to them.
        # Size from the *preferred* width, not the minimum. At the minimum every
        # row that does not quite fit wraps its label above its field, which
        # left the panel looking half-wrapped and half not. Clamped so a long
        # port description cannot run away with the window.
        scrollbar = scroll.verticalScrollBar().sizeHint().width()
        floor = inner.minimumSizeHint().width() + scrollbar + 4
        preferred = inner.sizeHint().width() + scrollbar + 4
        # The floor is the clipping threshold and is never traded away. The
        # preferred width only avoids wrapped labels, so it may be clamped: past
        # 520px the panel starts crowding the measurement table for no gain.
        self._left_width = max(floor, min(preferred, 520))
        scroll.setMinimumWidth(floor)
        return scroll

    def _build_right_column(self) -> QWidget:
        self.frame_status = QLabel("No frames captured yet")
        self.frame_status.setObjectName("StatusPill")
        self.frame_status.setWordWrap(True)

        self.session_status = QLabel("Reciprocity and noise floor appear from frame 2.")
        self.session_status.setObjectName("SessionPanel")
        self.session_status.setWordWrap(True)
        self.session_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.table = QTableWidget(0, len(RAW_COLUMNS))
        self.table.setHorizontalHeaderLabels(RAW_COLUMNS)
        header = self.table.horizontalHeader()
        for column in range(len(RAW_COLUMNS)):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents
                if column in NARROW_COLUMNS
                else QHeaderView.ResizeMode.Stretch,
            )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        self.log = QPlainTextEdit()
        self.log.setObjectName("LogConsole")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        # Reconstruction view. A QLabel holding a pixmap rather than an embedded
        # matplotlib canvas: the figure is already being rendered to a file for
        # the run record, so showing that same file guarantees the operator sees
        # exactly what was saved -- no second rendering path to diverge.
        self.image_label = QLabel(
            "No reconstruction yet.\n\n"
            "The first run of a session becomes its baseline.\n"
            "Every run after it is differenced against that baseline."
        )
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setObjectName("ImageCanvas")
        self.image_label.setMinimumHeight(320)
        self._image_path: Path | None = None

        self.image_status = QLabel("")
        self.image_status.setObjectName("StatusPill")
        self.image_status.setWordWrap(True)

        measurements = QWidget()
        measurements_layout = QVBoxLayout(measurements)
        measurements_layout.setContentsMargins(0, 8, 0, 0)
        measurements_layout.addWidget(self.table)

        image_tab = QWidget()
        image_layout = QVBoxLayout(image_tab)
        image_layout.setContentsMargins(0, 8, 0, 0)
        image_layout.setSpacing(8)
        image_layout.addWidget(self.image_status)
        image_layout.addWidget(self.image_label, stretch=1)

        self.tabs = QTabWidget()
        self.tabs.addTab(measurements, "Measurements")
        self.tabs.addTab(image_tab, "Reconstruction")

        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)
        layout.addWidget(self._section("Latest frame"))
        layout.addWidget(self.frame_status)
        layout.addWidget(self.tabs, stretch=3)
        layout.addWidget(self._section("Session"))
        layout.addWidget(self.session_status)
        layout.addWidget(self._section("Log"))
        layout.addWidget(self.log, stretch=1)
        return right

    def _build_layout(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_right_column())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([self._left_width, 1220 - self._left_width])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())
        layout.addWidget(splitter, stretch=1)
        return root

    # -- capture ---------------------------------------------------------

    def start_capture(self) -> None:
        try:
            settings = self.settings_panel.settings().validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Settings", str(exc))
            return

        conditions = self.conditions_panel.conditions()
        problems = conditions.validate()
        if problems:
            # A warning, never a block: a capture already worth taking must not
            # be refused over metadata, and the gaps are recorded in the run.
            answer = QMessageBox.question(
                self,
                "Incomplete conditions",
                "These will be recorded as not measured:\n\n"
                + "\n".join(f"  - {p}" for p in problems)
                + "\n\nCapture anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        acquisition = (
            DemoAcquisition() if self.settings_panel.demo.isChecked() else SerialAcquisition()
        )
        request = CaptureRequest(
            settings=settings,
            conditions=conditions,
            label=self.label.text().strip() or "run",
            frames=settings.frames,
            warmup_frames=settings.warmup_frames,
            baseline=self._baseline,
            override_reciprocity=self.override_reciprocity.isChecked(),
        )

        self._frames = []
        self._expected_frames = settings.frames
        self.table.setRowCount(0)
        self.session_status.setText("Capturing...")
        self.frame_status.setText("Waiting for the first frame")
        theme.apply_state(self.frame_status, "")
        self.photo_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self._set_running(True)

        self._thread = QThread(self)
        self._worker = CaptureWorker(acquisition, request, self._log_dir)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.started.connect(self._on_started)
        self._worker.progress.connect(self._log)
        self._worker.warmup_frame.connect(self._on_warmup)
        self._worker.frame_captured.connect(self._on_frame)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.reconstructed.connect(self._on_reconstructed)
        self._worker.reconstruction_skipped.connect(self._on_reconstruction_skipped)
        for signal in (self._worker.finished, self._worker.failed):
            signal.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def stop_capture(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._log("Stopping after the frame in flight...")
            self.stop_button.setEnabled(False)

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.settings_panel.setEnabled(not running)
        self.label.setEnabled(not running)
        if running:
            self._set_run_status("Capturing", "busy")

    def _set_run_status(self, text: str, state: str = "") -> None:
        self.run_status.setText(text)
        theme.apply_state(self.run_status, state)

    # -- worker signals --------------------------------------------------

    def _on_started(self, run_id: str) -> None:
        self._run_path = self._log_dir / run_record.RUNS_DIRNAME / run_id
        self._session_log.banner(f"Run {run_id}")
        conditions = self.conditions_panel.conditions()
        self._log(
            f"Conditions: medium={conditions.medium} "
            f"saline={conditions.saline_g_per_l} g/L "
            f"grounding={conditions.grounding} "
            f"fill={conditions.fill_depth_mm} mm "
            f"temp={conditions.water_temp_c} C"
        )

    def _on_warmup(self, done: int, total: int, text: str) -> None:
        self._log(f"[warmup {done}/{total}] {text}")

    def _on_frame(self, frame, index: int, text: str) -> None:
        self._frames.append(frame)
        summary = capture_view.frame_summary(frame)
        self.frame_status.setText(f"Frame {index + 1}  |  {text}")
        theme.apply_state(self.frame_status, theme.frame_state(summary))
        self._set_run_status(f"Capturing  {index + 1}/{self._expected_frames}", "busy")
        self._log(f"[frame {index + 1}] {text}")
        self._fill_table(frame)
        self.session_status.setText(
            capture_view.format_session_summary(
                capture_view.session_summary(self._frames)
            )
        )

    def _on_reconstructed(self, image_path: str, result, control=None) -> None:
        from tree_ert import reconstruction

        self._image_path = Path(image_path)
        self._render_image()
        message = (
            f"Peak {result.peak_value:+.3e} at {result.peak_angle_deg:.0f} deg  |  "
            f"pairs {result.kept_pairs}/{result.total_pairs} [{result.quality_label}]"
        )
        state = ""
        if control is None:
            # Without a control image the peak has nothing to be measured
            # against, and a drift image looks exactly like a real feature.
            message += "  |  NO CONTROL IMAGE - significance unknown"
            state = "warn"
        else:
            ratio = reconstruction.significance(result, control)
            if ratio < SIGNIFICANCE_THRESHOLD:
                message += f"  |  {ratio:.1f}x noise - INDISTINGUISHABLE FROM NOISE"
                state = "warn"
            else:
                message += f"  |  {ratio:.1f}x the noise image"
                state = "ok"
        self.image_status.setText(message)
        theme.apply_state(self.image_status, state)
        self._log(f"Reconstruction: {message}")
        self.tabs.setCurrentIndex(1)

    def _on_reconstruction_skipped(self, reason: str) -> None:
        self.image_status.setText(reason)
        theme.apply_state(
            self.image_status,
            "bad" if "reciprocity" in reason.lower()
            else "warn" if "failed" in reason.lower()
            else "",
        )
        self._log(f"No reconstruction: {reason}")

    def _render_image(self) -> None:
        """Draw the saved figure, scaled to the tab without distorting it."""
        if self._image_path is None or not self._image_path.is_file():
            return
        from PyQt6.QtGui import QPixmap

        pixmap = QPixmap(str(self._image_path))
        if pixmap.isNull():
            return
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._render_image()

    def clear_baseline(self) -> None:
        """Forget the session baseline so the next run becomes the new one.

        Needed whenever the specimen or the settings change mid-session: the
        old baseline would then be refused by the settings gate, or worse,
        accepted while describing a different specimen.
        """
        self._baseline = None
        self.clear_baseline_button.setEnabled(False)
        self.baseline_label.setText("Next run becomes the session baseline.")
        self._log("Baseline cleared; the next run will become the new baseline.")

    def _on_finished(self, run_path: str, summary: str) -> None:
        if self._baseline is None and self._frames:
            from tree_ert.settings import settings_to_dict

            self._baseline = SessionBaseline(
                run_id=Path(run_path).name,
                frames=list(self._frames),
                settings=settings_to_dict(self.settings_panel.settings()),
            )
            self.clear_baseline_button.setEnabled(True)
            self.baseline_label.setText(f"Baseline: {self._baseline.run_id}")
            self._log(f"This run is now the session baseline ({self._baseline.run_id}).")
        self._log(f"Finished. Run saved to {run_path}")
        for line in summary.splitlines():
            self._log(f"  {line}")
        self._log(f"Indexed in {self._log_dir / run_record.INDEX_FILENAME}")
        self.session_status.setText(summary)
        self._set_run_status(f"Done  {len(self._frames)} frames", "ok")
        self.photo_button.setEnabled(True)
        self.open_button.setEnabled(True)

    def _on_failed(self, message: str) -> None:
        self._log(f"FAILED: {message}")
        self._set_run_status("Failed", "bad")
        if self._run_path is not None:
            self._log(f"Partial run kept at {self._run_path}")
            self.photo_button.setEnabled(True)
            self.open_button.setEnabled(True)
        QMessageBox.critical(self, "Capture failed", message)

    def _on_thread_finished(self) -> None:
        self._set_running(False)
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    # -- rendering -------------------------------------------------------

    def _fill_table(self, frame) -> None:
        rows = capture_view.record_rows(frame)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            resistance = (
                "-" if row.resistance_kohm is None else f"{row.resistance_kohm:.4f}"
            )
            values = [
                str(index + 1),
                row.polarity,
                row.i_plus,
                row.i_minus,
                row.v_plus,
                row.v_minus,
                f"{row.voltage_mv:.4f}",
                f"{row.current_ua:.2f}",
                resistance,
                row.quality,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column >= 6:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not row.ok:
                    item.setBackground(theme.ROW_FLAGGED_BG)
                    item.setForeground(theme.ROW_FLAGGED_FG)
                elif column in LABEL_COLUMNS:
                    item.setForeground(theme.ROW_MUTED_FG)
                else:
                    item.setForeground(theme.ROW_OK_FG)
                self.table.setItem(index, column, item)

    def _log(self, message: str) -> None:
        self.log.appendPlainText(message)
        self._session_log.write(message)

    # -- run folder ------------------------------------------------------

    def attach_photo(self) -> None:
        """Copy a ground-truth photograph into the finished run (ADR-0020).

        Re-opens the run rather than holding the recorder, so a photograph taken
        after the capture still lands in the right folder.
        """
        if self._run_path is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach photo", "", "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)"
        )
        if not path:
            return
        import shutil

        media = self._run_path / "media"
        media.mkdir(parents=True, exist_ok=True)
        destination = media / Path(path).name
        shutil.copy2(path, destination)
        self._log(f"Attached {destination}")

    def open_run_folder(self) -> None:
        if self._run_path is not None:
            self._reveal(self._run_path)

    def open_scans_folder(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._reveal(self._log_dir)

    @staticmethod
    def _reveal(path: Path) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    # -- lifecycle -------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
        try:
            save_settings(self.settings_panel.settings(), settings_path(self._log_dir))
        except (OSError, ValueError):
            pass
        self._session_log.banner("Session ended")
        self._session_log.close()
        super().closeEvent(event)


def run_app(demo: bool = False, log_dir: Path | None = None) -> int:
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    # Fusion renders the stylesheet consistently across Windows and the Pi;
    # the native Windows style ignores several of the control rules.
    app.setStyle("Fusion")
    window = MainWindow(log_dir=log_dir, demo=demo)
    window.show()
    return app.exec()
