"""ScanView — read-only review of one saved measurement, pushed onto
CardApp's stack when a measurement card is tapped. Emits back_requested.

New scans are taken on CaptureScreen (the embedded capture session); this
screen only shows what was saved: the tomogram (``.npy`` when there is one,
else the run's image), timestamp, impedance ratio, classification and sync
state.

Sized for the 800x480 7" Raspberry Pi display: under the 48 px top bar
the view has 432 px of height, so chrome is kept compact.
"""

import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .paths import resolve_data_file


class ScanView(QWidget):
    back_requested = pyqtSignal()
    # Kept so CardApp can wire every pushed screen the same way.
    measurement_created = pyqtSignal(object)

    def __init__(self, tree, measurement, is_dark_mode=False, parent=None):
        super().__init__(parent)
        self.tree = tree
        self.measurement = measurement
        self.is_dark_mode = is_dark_mode
        self._is_fullscreen = False
        self._pixmap = None
        self._build_ui()

    def _build_ui(self):
        m = self.measurement
        c = theme.palette(self.is_dark_mode)
        bg, text, sub = c["bg"], c["text"], c["sub"]
        panel_bg, panel_border = c["surface"], c["border"]
        neutral, neutral_text = c["neutral"], c["neutral_text"]
        plot_bg = theme.TOMOGRAM_BG_DARK if self.is_dark_mode else theme.TOMOGRAM_BG_LIGHT
        self._colors = (sub, text, panel_bg, panel_border)

        self.setStyleSheet(
            f"ScanView {{ background-color: {bg}; color: {text}; }}"
            f"QLabel {{ color: {text}; background: transparent; border: none; "
            f"font-family: '{theme.HEADLINE_FONT}', sans-serif; }}"
            f"QLabel#scanSubLabel {{ color: {sub}; font-size: 12px; "
            f"font-weight: 600; letter-spacing: 0.05em; "
            f"font-family: '{theme.LABEL_FONT}', sans-serif; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)

        top = QFrame()
        top.setObjectName("scanTop")
        top.setFixedHeight(48)
        top.setStyleSheet(
            f"QFrame#scanTop {{ background-color: {panel_bg}; "
            f"border: 1px solid {panel_border}; border-radius: 10px; }}"
        )
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 4, 6, 4)
        top_layout.setSpacing(10)

        title = QLabel(f"Scan · {self.tree.name}")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(title, stretch=1)

        self.btn_fullscreen = QPushButton("⛶")
        self.btn_fullscreen.setFixedSize(44, 40)
        self.btn_fullscreen.setToolTip("Fullscreen tomogram")
        self.btn_fullscreen.setStyleSheet(
            f"QPushButton {{ font-size: 18px; font-weight: 700; "
            f"background-color: {neutral}; color: {neutral_text}; "
            f"border: 1px solid {panel_border}; border-radius: 8px; }}"
            f"QPushButton:pressed {{ background-color: {panel_border}; }}"
        )
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        top_layout.addWidget(self.btn_fullscreen)
        root.addWidget(top)

        plot_frame = QFrame()
        plot_frame.setObjectName("plotFrame")
        plot_frame.setStyleSheet(
            f"QFrame#plotFrame {{ border: 1px solid {panel_border}; border-radius: 10px; "
            f"background-color: {plot_bg}; }}"
        )
        plot_layout = QVBoxLayout(plot_frame)
        plot_layout.setContentsMargins(4, 4, 4, 4)
        plot_layout.addWidget(self._build_image())

        main = QHBoxLayout()
        main.setSpacing(8)
        main.addWidget(plot_frame, stretch=1)

        rail = QVBoxLayout()
        rail.setContentsMargins(0, 0, 0, 0)
        rail.setSpacing(6)
        pill = QLabel(m.classification)
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setFixedHeight(34)
        pill.setStyleSheet(theme.status_pill_style(m.classification, self.is_dark_mode))
        rail.addWidget(pill)
        rail.addWidget(self._readout("Timestamp", m.timestamp.toString("yyyy-MM-dd HH:mm:ss")))
        rail.addWidget(self._readout(
            "Impedance Ratio", "—" if m.imp_ratio is None else f"{m.imp_ratio:.4f}"
        ))
        rail.addWidget(self._readout("Classification", m.classification))
        rail.addWidget(self._readout(
            "Sync Status",
            "Synced to Drive" if m.synced else "Not synced yet",
            theme.STATUS_HEALTHY if m.synced else theme.STATUS_AT_RISK,
        ))
        rail.addStretch()
        self.rail_widget = QWidget()
        self.rail_widget.setFixedWidth(220)
        self.rail_widget.setLayout(rail)
        main.addWidget(self.rail_widget)
        root.addLayout(main, stretch=1)

        self.btn_back = QPushButton("Back")
        self.btn_back.setFixedHeight(50)
        self.btn_back.setStyleSheet(
            f"QPushButton {{ font-size: 17px; font-weight: 700; "
            f"background-color: {neutral}; color: {neutral_text}; "
            f"border: 1px solid {panel_border}; border-radius: 8px; }}"
            f"QPushButton:pressed {{ background-color: {panel_border}; }}"
        )
        self.btn_back.clicked.connect(self.back_requested.emit)
        root.addWidget(self.btn_back)

        for btn in self.findChildren(QPushButton):  # touch UI: no focus rectangles
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _build_image(self):
        """Saved .npy tomogram if present, else the run's image, else a note."""
        m = self.measurement
        data_path = resolve_data_file(m.data_path)
        if data_path.endswith(".npy"):
            try:
                matrix = np.load(data_path)
            except (OSError, ValueError):
                matrix = None
            if matrix is not None:
                from .widgets.plot import TomogramPlot  # matplotlib: load on demand

                plot = TomogramPlot(is_dark_mode=self.is_dark_mode, parent=self)
                plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                plot.plot_data(matrix)
                return plot

        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        image_path = resolve_data_file(m.image_path)
        pixmap = QPixmap(image_path) if image_path else None
        if pixmap is not None and not pixmap.isNull():
            self._pixmap = pixmap
            self._image_label = label
        else:
            self.btn_fullscreen.setEnabled(False)
            label.setText("No tomogram saved for this measurement")
            label.setStyleSheet("color: #888; font-size: 14px;")
        return label

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap is not None:
            self._image_label.setPixmap(self._pixmap.scaled(
                self._image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def _readout(self, label_text, value, value_color=None):
        sub, text, panel_bg, panel_border = self._colors
        container = QFrame()
        container.setObjectName("readout")
        container.setStyleSheet(
            f"QFrame#readout {{ background-color: {panel_bg}; "
            f"border: 1px solid {panel_border}; border-radius: 8px; }}"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(10, 5, 10, 5)
        v.setSpacing(2)
        lbl = QLabel(label_text)
        lbl.setObjectName("scanSubLabel")
        v.addWidget(lbl)
        val = QLabel(value)
        val.setStyleSheet(
            f"color: {value_color or text}; font-size: 16px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        v.addWidget(val)
        return container

    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        self.rail_widget.setVisible(not self._is_fullscreen)
        self.btn_back.setVisible(not self._is_fullscreen)
        self.btn_fullscreen.setText("✕" if self._is_fullscreen else "⛶")
        self.btn_fullscreen.setToolTip("Exit fullscreen" if self._is_fullscreen else "Fullscreen tomogram")

    def shutdown(self):
        """Nothing running on a review screen; matches CaptureScreen."""
