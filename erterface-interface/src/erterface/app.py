"""CardApp — main window. Owns top bar, breadcrumb, search/sort, card
grid, FAB, scan view push/pop, export/sync triggers.
"""

import json
import os
import shutil
import threading
import time

from PyQt6.QtCore import QDateTime, QEvent, Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import export, paths, theme
from .dialogs import AddEntityDialog, make_entity
from .drive_setup import DriveSetupDialog
from .drive_sync import DriveClient, sync_unsynced
from .errors import status_toast
from .models import Measurement, Plantation, Tree, Zone
from .capture_screen import CaptureScreen, create_session
from .scan_view import ScanView
from .widgets.card import CARD_W, CardWidget, card_stylesheet
from .widgets.keyboard import TouchLineEdit


EMPTY_STATE = {
    "Plantation": "No plantations yet.\nTap + to add one.",
    "Zone": "No zones in this plantation.\nTap + to add one.",
    "Tree": "No trees in this zone.\nTap + to add one.",
    "Measurement": "No measurements yet.\nTap a tree's Scan button to capture one.",
}


class CardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ERTERFACE — Coconut Health Field Interface")
        self.resize(800, 480)

        paths.ensure_directories()
        self._init_drive_mode()
        theme.load_fonts()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setFont(theme.default_font())

        self.is_dark_mode = False
        self.database = []
        self.navigation_path = []

        self._scan_view = None
        self._capture_session = None  # created on first Scan, lives until close
        self._toast_timer = None
        self._active_keyboard = None

        self.load_data()
        self._build_ui()
        self.apply_theme()
        self.refresh_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time_label)
        self.timer.start(1000)
        self.update_time_label()

        # The first Scan tap imports the capture session (~0.6 s on a Pi 5).
        # Do that import on a background thread while the operator is still
        # navigating, so the tap itself is fast. Only module code runs there;
        # no widgets are created off the GUI thread.
        threading.Thread(target=self._prewarm_capture, daemon=True).start()

    @staticmethod
    def _prewarm_capture():
        try:
            from .capture_screen import _import_capture_window
            _import_capture_window()
        except Exception:
            pass  # the real import on Scan reports the error

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._build_top_bar()
        self.main_layout.addWidget(self.top_bar_container)

        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack, stretch=1)

        self.index_page = QWidget()
        ip_layout = QVBoxLayout(self.index_page)
        ip_layout.setContentsMargins(0, 0, 0, 0)
        ip_layout.setSpacing(0)

        self._build_breadcrumb_row(ip_layout)
        self._build_search_sort_row(ip_layout)
        self._build_card_grid(ip_layout)
        self._build_fab()

        # Docked on-screen keyboard for the search box (TouchLineEdit looks
        # for the nearest ancestor with a keyboard_holder).
        self.keyboard_holder = QWidget()
        self.keyboard_holder.setVisible(False)
        kb_layout = QVBoxLayout(self.keyboard_holder)
        kb_layout.setContentsMargins(6, 0, 6, 4)
        ip_layout.addWidget(self.keyboard_holder)
        self.keyboard_holder.installEventFilter(self)

        self.stack.addWidget(self.index_page)

        self._build_start_page()

    def _build_start_page(self):
        """Opening screen: the name and a Start button. The top bar stays
        hidden until Start, so nothing else competes for attention."""
        self.start_page = QWidget()
        self.start_page.setObjectName("startPage")
        layout = QVBoxLayout(self.start_page)
        layout.addStretch(3)
        title = QLabel("ERTERFACE")
        title.setObjectName("startTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("Coconut tree ERT field interface")
        subtitle.setObjectName("startSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(36)
        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("startButton")
        self.btn_start.setFixedSize(240, 72)
        self.btn_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_start.clicked.connect(self._leave_start_page)
        layout.addWidget(self.btn_start, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(4)
        self.stack.addWidget(self.start_page)
        self.stack.setCurrentWidget(self.start_page)
        self.top_bar_container.setVisible(False)

    def _leave_start_page(self):
        self.top_bar_container.setVisible(True)
        self.stack.setCurrentWidget(self.index_page)
        self.stack.removeWidget(self.start_page)
        self.start_page.deleteLater()
        self.start_page = None

    def _init_drive_mode(self):
        if "ERTERFACE_DRIVE_MODE" not in os.environ:
            os.environ["ERTERFACE_DRIVE_MODE"] = "local"
            self._drive_mode = "local"
        else:
            self._drive_mode = os.environ["ERTERFACE_DRIVE_MODE"].strip().lower()

    def _build_top_bar(self):
        self.top_bar_container = QWidget()
        self.top_bar_container.setFixedHeight(48)
        top_bar = QHBoxLayout(self.top_bar_container)
        top_bar.setContentsMargins(14, 4, 12, 4)
        top_bar.setSpacing(10)

        self.lbl_time = QLabel()
        self.lbl_time.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.lbl_time.setMinimumWidth(48)

        self.lbl_storage = QLabel()
        self.lbl_storage.setStyleSheet("font-size: 13px; color: #5a6b7e;")
        self.lbl_storage.setMinimumWidth(120)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #888888;")
        self.lbl_status.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_export = self._make_top_button("Export", "success", "Export all measurements to CSV")
        self.btn_export.clicked.connect(self.export_csv)

        self.btn_sync = self._make_top_button("Sync", "info", "Sync unsynced measurements")
        self.btn_sync.clicked.connect(self.sync_drive)

        self.btn_theme = self._make_top_button("Dark", "neutral", "Toggle light/dark theme")
        self.btn_theme.clicked.connect(self.toggle_theme)

        self.btn_exit = self._make_top_button("Exit", "danger", "Close the application")
        self.btn_exit.clicked.connect(self.close_app_safe)

        self.sync_indicator = QLabel("●")
        self.sync_indicator.setFixedWidth(12)
        self.sync_indicator.setStyleSheet("color: #8a94a6; font-size: 12px;")
        self.sync_indicator.setToolTip("Sync status: idle")

        self.btn_drive_mode = QPushButton(self._drive_mode_label())
        self.btn_drive_mode.setFixedHeight(40)
        self.btn_drive_mode.setMinimumWidth(86)
        self.btn_drive_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drive_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_drive_mode.setToolTip("Click to switch sync mode (offline / Google Drive)")
        self.btn_drive_mode.clicked.connect(self._open_drive_setup)
        self._style_drive_mode_button()

        left_cluster = QHBoxLayout()
        left_cluster.setContentsMargins(0, 0, 0, 0)
        left_cluster.setSpacing(14)
        left_cluster.addWidget(self.lbl_time)
        left_cluster.addWidget(self.lbl_storage)

        left_wrap = QWidget()
        left_wrap.setStyleSheet("background: transparent; border: none;")
        left_wrap.setLayout(left_cluster)

        self.lbl_title = QLabel("Plantations")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet(
            "font-size: 17px; font-weight: 700; "
            "background: transparent; border: none; color: inherit;"
        )

        top_bar.addWidget(left_wrap)
        top_bar.addWidget(self.sync_indicator)
        top_bar.addSpacing(8)
        top_bar.addWidget(self.lbl_title, stretch=1)
        top_bar.addSpacing(8)
        top_bar.addWidget(self.btn_drive_mode)
        top_bar.addWidget(self.btn_export)
        top_bar.addWidget(self.btn_sync)
        top_bar.addWidget(self.btn_theme)
        top_bar.addWidget(self.btn_exit)

    def _make_top_button(self, text, variant, tooltip):
        btn = QPushButton(text)
        btn.setFixedHeight(40)
        btn.setMinimumWidth(76)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # touch UI: no focus rectangles
        btn.setProperty("variant", variant)
        btn._variant = variant
        return btn

    def _drive_mode_label(self):
        return {"local": "●  Offline", "oauth": "●  Drive", "off": "●  Off"}.get(
            getattr(self, "_drive_mode", "local"), "●  ?"
        )

    def _style_drive_mode_button(self):
        colors = {
            "local": ("#1e73be", "#ffffff", "#1e73be", "#155a96"),
            "oauth": ("#1e8e3e", "#ffffff", "#1e8e3e", "#166b2e"),
            "off":    ("#6a7286", "#ffffff", "#6a7286", "#4a5568"),
        }
        bg, fg, border, pressed = colors.get(self._drive_mode, colors["local"])
        self.btn_drive_mode.setStyleSheet(
            f"QPushButton {{ font-size: 13px; font-weight: 700; "
            f"background-color: {bg}; color: {fg}; "
            f"border: 1px solid {border}; border-radius: 6px; "
            f"padding: 0px 8px 0px 8px; }}"
            f"QPushButton:pressed {{ background-color: {pressed}; }}"
        )
        self.btn_drive_mode.setText(self._drive_mode_label())

    def _build_breadcrumb_row(self, parent_layout):
        self.nav_container = QFrame()
        self.nav_container.setFixedHeight(46)
        self.nav_layout = QHBoxLayout(self.nav_container)
        self.nav_layout.setContentsMargins(16, 0, 16, 0)
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        self.nav_layout.setSpacing(4)
        parent_layout.addWidget(self.nav_container)

    def _build_search_sort_row(self, parent_layout):
        self.control_container = QWidget()
        self.control_container.setFixedHeight(56)
        self.control_layout = QHBoxLayout(self.control_container)
        self.control_layout.setContentsMargins(16, 8, 16, 8)
        self.control_layout.setSpacing(10)

        self.search_bar = TouchLineEdit(is_dark_mode=self.is_dark_mode)
        self.search_bar.setPlaceholderText("Search by name or ID…")
        self.search_bar.setFixedHeight(theme.TOUCH_MIN)
        # Debounced: rebuilding the grid on every keystroke stutters on a Pi.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.refresh_ui)
        self.search_bar.textChanged.connect(self._search_timer.start)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Sort: Manual", "Sort: Newest", "Sort: A–Z", "Sort: Z–A"])
        self.sort_combo.setFixedHeight(theme.TOUCH_MIN)
        self.sort_combo.setMinimumWidth(160)
        self.sort_combo.currentIndexChanged.connect(self.refresh_ui)

        self.control_layout.addWidget(self.search_bar, stretch=2)
        self.control_layout.addWidget(self.sort_combo, stretch=1)
        parent_layout.addWidget(self.control_container)

    def _build_card_grid(self, parent_layout):
        self.overlay_container = QWidget()
        self.overlay_layout = QGridLayout(self.overlay_container)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setMinimumHeight(0)  # yields to the search keyboard
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")
        QScroller.grabGesture(
            self.scroll_area.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture
        )
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.card_container = QWidget()
        self.card_container.setObjectName("cardContainer")
        self.card_layout = QGridLayout(self.card_container)
        self.card_layout.setContentsMargins(20, 8, 20, 16)
        self.card_layout.setSpacing(15)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setWidget(self.card_container)
        self.overlay_layout.addWidget(self.scroll_area, 0, 0)

        self.empty_label = QLabel("")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #8a94a6; font-size: 15px; background: transparent; "
            "border: none; padding: 32px;"
        )
        self.empty_label.setVisible(False)
        self.overlay_layout.addWidget(self.empty_label, 0, 0, Qt.AlignmentFlag.AlignCenter)

        parent_layout.addWidget(self.overlay_container, stretch=1)

    def _build_fab(self):
        self.btn_container = QWidget()
        self.btn_container.setStyleSheet("background-color: transparent;")
        btn_layout = QVBoxLayout(self.btn_container)
        btn_layout.setContentsMargins(0, 0, 20, 20)
        self.btn_add = QPushButton("+")
        self.btn_add.setFixedSize(60, 60)
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setToolTip("Add new entity")
        self.btn_add.clicked.connect(self._fab_clicked)
        btn_layout.addWidget(self.btn_add)
        self.overlay_layout.addWidget(
            self.btn_container, 0, 0,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
        )
        self._fab_mode = "add"

    def _fab_clicked(self):
        if self._fab_mode == "scan":
            last = self.navigation_path[-1] if self.navigation_path else None
            if isinstance(last, Tree):
                self.open_scan_view(last)
        else:
            self.add_new_entity()

    def _set_fab(self, label, mode, tooltip, color="#000000"):
        self.btn_add.setText(label)
        self.btn_add.setFixedSize(140 if mode == "scan" else 60, 60)
        self.btn_container.adjustSize()
        self._fab_mode = mode
        self.btn_add.setToolTip(tooltip)
        self.btn_add.setStyleSheet(
            f"QPushButton {{ font-weight: 800; font-size: {20 if mode == 'scan' else 32}px; "
            f"background-color: {color}; color: #ffffff; "
            f"border: 2px solid {color}; border-radius: 30px; "
            f"text-align: center; padding: 0px 0px {0 if mode == 'scan' else 6}px 0px; }}"
            f"QPushButton:pressed {{ background-color: #444444; border: 2px solid #444444; }}"
        )

    # ---------- data ----------

    def load_data(self):
        if os.path.exists(paths.DATA_FILE):
            try:
                with open(paths.DATA_FILE, "r") as f:
                    data = json.load(f)
                self.database = [Plantation.from_dict(p) for p in data]
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Could not load data: {e}")
                self.database = []
                self.navigation_path = []
                return
        self.navigation_path = []

    def save_data(self):
        try:
            tmp = paths.DATA_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump([p.to_dict() for p in self.database], f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, paths.DATA_FILE)
        except Exception as e:
            status_toast(self, f"Save failed: {e}", "error")

    # ---------- top-bar / theme ----------

    def update_time_label(self):
        try:
            self.lbl_time.setText(QDateTime.currentDateTime().toString("HH:mm"))
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2 ** 30)
            pct = (free / total) * 100 if total > 0 else 0
            self.lbl_storage.setText(f"{free_gb} GB free ({pct:.0f}%)")
        except (RuntimeError, AttributeError):
            pass
        except Exception:
            try:
                self.lbl_storage.setText("Storage n/a")
            except RuntimeError:
                pass

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
        self.refresh_ui()
        self._rebuild_scan_view()

    def apply_theme(self):
        if self.is_dark_mode:
            bg = theme.DARK_BG
            top_bg = "#1a1a1a"
            nav_bg = "#1a1a1a"
            text = "#f5f5f5"
            sub = "#a0aec0"
            btn_neutral_bg = "#2a2a2a"
            btn_neutral_text = "#f5f5f5"
            btn_neutral_border = "#3a3a3a"
            input_bg = "#2a2a2a"
            input_border = "#3a3a3a"
            empty_color = "#6a7286"
            fab_color = "#000000"
        else:
            bg = theme.LIGHT_BG
            top_bg = "#ffffff"
            nav_bg = "#ffffff"
            text = "#0b1220"
            sub = "#3d4b5c"
            btn_neutral_bg = "#e8edf2"
            btn_neutral_text = "#0b1220"
            btn_neutral_border = "#a9b4c0"
            input_bg = "#ffffff"
            input_border = "#a9b4c0"
            empty_color = "#3d4b5c"
            fab_color = "#000000"

        self.setStyleSheet(
            f"QMainWindow {{ background-color: {bg}; color: {text}; }}"
        )
        self.top_bar_container.setStyleSheet(
            f"QWidget {{ background-color: {top_bg}; color: {text}; border: none; }}"
        )
        self.lbl_time.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text}; background: transparent; border: none;")
        self.lbl_storage.setStyleSheet(f"font-size: 13px; color: {sub}; background: transparent; border: none;")
        self.lbl_title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {text}; background: transparent; border: none;")
        if not getattr(self, "_status_override", False):
            self.lbl_status.setStyleSheet(f"font-size: 12px; color: {sub}; background: transparent; border: none;")

        variant_styles = {
            "success": ("#1e8e3e", "#ffffff", "#1e8e3e", "#166b2e"),
            "info": ("#1e73be", "#ffffff", "#1e73be", "#155a96"),
            "danger": ("#c53030", "#ffffff", "#c53030", "#9b2c2c"),
            "neutral": (btn_neutral_bg, btn_neutral_text, btn_neutral_border, "#d9e2ec"),
        }
        for btn in (self.btn_export, self.btn_sync, self.btn_theme, self.btn_exit):
            v = getattr(btn, "_variant", "neutral")
            bg_c, fg_c, border_c, pressed_c = variant_styles.get(v, variant_styles["neutral"])
            btn.setStyleSheet(
                f"QPushButton {{"
                f"font-size: 14px; font-weight: 700;"
                f"background-color: {bg_c}; color: {fg_c};"
                f"border: 1px solid {border_c}; border-radius: 6px;"
                f"padding: 4px 12px;"
                f"}}"
                f"QPushButton:pressed {{ background-color: {pressed_c}; }}"
            )

        self.btn_theme.setText("Light" if self.is_dark_mode else "Dark")
        if getattr(self, "start_page", None) is not None:
            self.start_page.setStyleSheet(
                f"QWidget#startPage {{ background-color: {bg}; }}"
                f"QLabel#startTitle {{ font-size: 64px; font-weight: 900; color: {text}; "
                f"letter-spacing: 6px; background: transparent; }}"
                f"QLabel#startSubtitle {{ font-size: 18px; color: {sub}; background: transparent; }}"
                f"QPushButton#startButton {{ font-size: 26px; font-weight: 800; color: #ffffff; "
                f"background-color: {theme.STATUS_HEALTHY}; border: none; border-radius: 36px; }}"
                f"QPushButton#startButton:pressed {{ background-color: #12602a; }}"
            )

        self.nav_container.setStyleSheet(
            f"QFrame {{ background-color: {nav_bg}; border: none; }}"
        )
        control_style = (
            f"QLineEdit, QComboBox {{ font-size: 15px; border: 1px solid {input_border}; "
            f"border-radius: 8px; padding: 6px 12px; background-color: {input_bg}; color: {text}; }}"
            f"QLineEdit:focus {{ border: 1px solid #1e8e3e; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView::item {{ min-height: {theme.TOUCH_MIN}px; }}"
            f"QComboBox QAbstractItemView {{ background-color: {input_bg}; color: {text}; "
            f"selection-background-color: #1e8e3e; }}"
        )
        self.search_bar.setStyleSheet(control_style)
        self.search_bar.is_dark_mode = self.is_dark_mode
        self.sort_combo.setStyleSheet(control_style)

        self.update_add_button()
        self.card_container.setStyleSheet(
            "QWidget#cardContainer { background-color: transparent; }"
            + card_stylesheet(self.is_dark_mode)
        )

        self.empty_label.setStyleSheet(
            f"color: {empty_color}; font-size: 15px; background: transparent; "
            f"border: none; padding: 32px;"
        )

    # ---------- nav helpers ----------

    def get_current_list(self):
        if not self.navigation_path:
            return self.database
        last = self.navigation_path[-1]
        if isinstance(last, Plantation):
            return last.zones
        if isinstance(last, Zone):
            return last.trees
        if isinstance(last, Tree):
            return last.measurements
        return []

    def get_current_level_name(self, target_object=None):
        if target_object is not None:
            if isinstance(target_object, Plantation):
                return "Plantation"
            if isinstance(target_object, Zone):
                return "Zone"
            if isinstance(target_object, Tree):
                return "Tree"
            if isinstance(target_object, Measurement):
                return "Measurement"
        if not self.navigation_path:
            return "Plantation"
        last = self.navigation_path[-1]
        if isinstance(last, Plantation):
            return "Zone"
        if isinstance(last, Zone):
            return "Tree"
        if isinstance(last, Tree):
            return "Measurement"
        return ""

    # ---------- breadcrumbs ----------

    def update_breadcrumbs(self):
        while self.nav_layout.count():
            item = self.nav_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

        if self.is_dark_mode:
            text = "#f5f5f5"
            hover = "#2a2a2a"
            sep = "#5a6b7e"
            active_bg = "#2a2a2a"
        else:
            text = "#1a202c"
            hover = "#eef0f3"
            sep = "#8a94a6"
            active_bg = "#eef0f3"

        def btn_style(is_active=False):
            bg = active_bg if is_active else "transparent"
            return (
                f"QPushButton {{ background-color: {bg}; border: 1px solid transparent; "
                f"font-weight: 700; font-size: 15px; color: {text}; "
                f"padding: 4px 14px 4px 14px; border-radius: 8px; min-height: 36px; }}"
                f"QPushButton:pressed {{ background-color: {hover}; }}"
            )

        self.nav_layout.addStretch(1)

        home = QPushButton("Home")
        home.setStyleSheet(btn_style(is_active=not self.navigation_path))
        home.setCursor(Qt.CursorShape.PointingHandCursor)
        home.clicked.connect(lambda: self.navigate_to(-1))
        self.nav_layout.addWidget(home)

        for index, item in enumerate(self.navigation_path):
            sep_lbl = QLabel("›")
            sep_lbl.setStyleSheet(
                f"QLabel {{ font-weight: 700; font-size: 16px; color: {sep}; "
                f"background: transparent; border: none; padding: 0px 4px 0px 4px; }}"
            )
            self.nav_layout.addWidget(sep_lbl)

            is_last = index == len(self.navigation_path) - 1
            label = item.name.split("\n")[0]
            if is_last:
                lbl = QLabel(label)
                lbl.setStyleSheet(
                    f"QLabel {{ font-weight: 800; font-size: 15px; color: {text}; "
                    f"padding: 4px 10px 4px 10px; background: transparent; border: none; }}"
                )
                self.nav_layout.addWidget(lbl)
            else:
                path_btn = QPushButton(label)
                path_btn.setStyleSheet(btn_style(is_active=False))
                path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                path_btn.clicked.connect(lambda checked, idx=index: self.navigate_to(idx))
                self.nav_layout.addWidget(path_btn)

        self.nav_layout.addStretch(1)

    # ---------- cards ----------

    def clear_cards(self):
        # hide + deleteLater rather than setParent(None): reparenting each card
        # to a top-level window was the largest cost of a grid rebuild.
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

    def populate_cards(self):
        items = self.get_current_list()[:]
        q = self.search_bar.text().lower().strip()
        if q:
            items = [it for it in items if q in it.name.lower()]

        sort_mode = self.sort_combo.currentText()
        if sort_mode == "Sort: A–Z":
            items.sort(key=lambda x: x.name.lower())
        elif sort_mode == "Sort: Z–A":
            items.sort(key=lambda x: x.name.lower(), reverse=True)
        elif sort_mode == "Sort: Newest":
            items.reverse()

        reorder_enabled = sort_mode == "Sort: Manual" and not q

        if not items:
            self.empty_label.setText(EMPTY_STATE.get(self.get_current_level_name(), "Nothing here."))
            self.empty_label.setVisible(True)
        else:
            self.empty_label.setVisible(False)

        self._cards = []
        for item in items:
            card = CardWidget(
                item.name,
                item,
                on_body_click=self.card_clicked,
                on_edit=self.edit_entity,
                on_delete=self.delete_entity,
                on_move_left=self.move_left,
                on_move_right=self.move_right,
                on_scan=None,
                is_dark_mode=self.is_dark_mode,
                reorder_enabled=reorder_enabled,
            )
            self._cards.append(card)
        self._layout_cards()

    def _column_count(self):
        spacing = self.card_layout.spacing()
        margins = self.card_layout.contentsMargins()
        usable = self.scroll_area.viewport().width() - margins.left() - margins.right()
        return max(1, (usable + spacing) // (CARD_W + spacing))

    def _layout_cards(self):
        """Place the built cards in as many columns as the width allows.
        Re-run on resize without rebuilding the cards."""
        cols = self._column_count()
        self._grid_cols = cols
        while self.card_layout.count():
            self.card_layout.takeAt(0)
        for i, card in enumerate(self._cards):
            self.card_layout.addWidget(card, i // cols, i % cols)

    def eventFilter(self, obj, event):
        # The + button floats over the card area; hide it while the search
        # keyboard has taken most of the screen.
        if obj is self.keyboard_holder and event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            if event.type() == QEvent.Type.Show:
                self.btn_container.setVisible(False)
            else:
                self.update_add_button()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # The viewport is resized by the layout after this event; check then.
        QTimer.singleShot(0, self._relayout_if_needed)

    def _relayout_if_needed(self):
        if getattr(self, "_cards", None) and self._column_count() != self._grid_cols:
            self._layout_cards()

    def update_add_button(self):
        last = self.navigation_path[-1] if self.navigation_path else None
        if isinstance(last, Tree):
            self._set_fab("Scan", "scan", "Start a scan on this tree", theme.STATUS_HEALTHY)
            self.btn_container.setVisible(True)
        elif isinstance(last, Measurement):
            self.btn_container.setVisible(False)
        else:
            self._set_fab("+", "add", "Add new entity", "#000000")
            self.btn_container.setVisible(True)
        if getattr(self, "keyboard_holder", None) is not None and self.keyboard_holder.isVisible():
            self.btn_container.setVisible(False)

    def update_top_bar_title(self):
        if not self.navigation_path:
            self.lbl_title.setText("Plantations")
            return
        last = self.navigation_path[-1]
        if isinstance(last, Plantation):
            text = last.name or last.plant_id
        elif isinstance(last, Zone):
            text = last.zone_id
        elif isinstance(last, Tree):
            text = last.tree_id
        else:
            text = last.name.splitlines()[0] if last.name else ""
        self.lbl_title.setText(text)

    def refresh_ui(self):
        self.update_breadcrumbs()
        self.clear_cards()
        self.populate_cards()
        self.update_add_button()
        self.update_top_bar_title()

    # ---------- card actions ----------

    def card_clicked(self, data_object):
        if isinstance(data_object, Measurement):
            self._review_measurement(data_object)
            return
        self.search_bar.clear()
        self.navigation_path.append(data_object)
        self.refresh_ui()

    def _review_measurement(self, m):
        # A measurement card is only shown inside its tree, so the tree is
        # the last navigation step. Review uses the scan screen itself.
        self.open_scan_view(self.navigation_path[-1], measurement=m)

    def navigate_to(self, index):
        self.search_bar.clear()
        if index == -1:
            self.navigation_path.clear()
        else:
            self.navigation_path = self.navigation_path[: index + 1]
        self.refresh_ui()

    def move_left(self, obj):
        lst = self.get_current_list()
        if obj in lst:
            i = lst.index(obj)
            if i > 0:
                lst[i], lst[i - 1] = lst[i - 1], lst[i]
                self.save_data()
                self.refresh_ui()

    def move_right(self, obj):
        lst = self.get_current_list()
        if obj in lst:
            i = lst.index(obj)
            if i < len(lst) - 1:
                lst[i], lst[i + 1] = lst[i + 1], lst[i]
                self.save_data()
                self.refresh_ui()

    # ---------- add / edit / delete ----------

    def add_new_entity(self):
        level = self.get_current_level_name()
        parent = self.navigation_path[-1] if self.navigation_path else None
        existing = self.get_current_list()
        dlg = AddEntityDialog(level, existing, is_dark_mode=self.is_dark_mode, parent=self)
        if dlg.exec() in (QDialog.DialogCode.Accepted, 2):
            data = dlg.get_data()
            entity = make_entity(level, data, parent)
            if entity is None:
                status_toast(self, f"Could not create {level}.", "error")
                return
            if isinstance(parent, Plantation) and isinstance(entity, Zone):
                parent.zones.append(entity)
            elif isinstance(parent, Zone) and isinstance(entity, Tree):
                parent.trees.append(entity)
            elif level == "Plantation" and isinstance(entity, Plantation):
                self.database.append(entity)
            else:
                status_toast(self, f"Cannot add {level} at this level.", "error")
                return
            self.save_data()
            self.refresh_ui()
            status_toast(self, f"{level} '{entity.name.splitlines()[0]}' created.", "info")

    def edit_entity(self, obj):
        if isinstance(obj, Measurement):
            self._review_measurement(obj)
            return
        level = self.get_current_level_name(obj)
        existing = self.get_current_list()
        dlg = AddEntityDialog(
            level, existing, is_dark_mode=self.is_dark_mode,
            edit_mode=True, current_data=obj, parent=self,
        )
        if dlg.exec() in (QDialog.DialogCode.Accepted, 2):
            data = dlg.get_data()
            if isinstance(obj, Plantation):
                obj.name = data["name"]
                obj.plant_id = data["id"]
            elif isinstance(obj, Zone):
                obj.zone_id = data["id"]
                obj.name = f"Zone {data['id']}"
            elif isinstance(obj, Tree):
                obj.tree_id = data["id"]
                obj.name = f"Tree {data['id']}"
            else:
                status_toast(self, "Measurement edit not supported.", "warn")
                return
            self.save_data()
            self.refresh_ui()
            status_toast(self, f"{level} updated.", "info")

    def delete_entity(self, obj):
        first_line = obj.name.splitlines()[0] if obj.name else "(unnamed)"
        mb = QMessageBox(self)
        mb.setWindowTitle("Confirm Deletion")
        mb.setText(f"Delete '{first_line}' and everything inside it?")
        mb.setInformativeText("This cannot be undone within this run.")
        mb.setIcon(QMessageBox.Icon.Warning)
        mb.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        mb.setDefaultButton(QMessageBox.StandardButton.Cancel)
        mb.setStyleSheet(
            "QMessageBox { min-width: 360px; } QLabel { font-size: 14px; } "
            "QPushButton { font-size: 14px; min-height: 40px; min-width: 100px; "
            "border-radius: 6px; padding: 4px 12px 4px 12px; }"
        )
        if mb.exec() == QMessageBox.StandardButton.Yes:
            lst = self.get_current_list()
            if obj in lst:
                lst.remove(obj)
                self.save_data()
                self.refresh_ui()
                status_toast(self, f"Deleted '{first_line}'.", "info")

    # ---------- scan view push/pop ----------

    def _rebuild_scan_view(self):
        # Only the review screen follows the theme. The capture screen is
        # left alone: rebuilding it would cancel a capture in progress.
        if not isinstance(self._scan_view, ScanView):
            return
        self._push_screen(ScanView(
            self._scan_view.tree, self._scan_view.measurement,
            is_dark_mode=self.is_dark_mode, parent=self,
        ))

    def open_scan_view(self, tree, measurement=None):
        """Scan a tree (CaptureScreen) or review one of its measurements (ScanView)."""
        if measurement is None:
            if self._capture_session is None:
                self._capture_session = create_session()
            screen = CaptureScreen(
                tree, self._capture_session, is_dark_mode=self.is_dark_mode, parent=self
            )
        else:
            screen = ScanView(tree, measurement, is_dark_mode=self.is_dark_mode, parent=self)
        self._push_screen(screen)
        self.btn_container.setVisible(False)

    def _push_screen(self, screen):
        self._drop_scan_view()
        self._scan_view = screen
        screen.back_requested.connect(self.pop_scan_view)
        screen.measurement_created.connect(self._on_measurement_created)
        self.stack.addWidget(screen)
        self.stack.setCurrentWidget(screen)

    def _drop_scan_view(self):
        if self._scan_view is None:
            return
        self._scan_view.shutdown()
        self.stack.removeWidget(self._scan_view)
        self._scan_view.deleteLater()
        self._scan_view = None

    def pop_scan_view(self):
        if self._scan_view is None:
            return
        self.stack.setCurrentWidget(self.index_page)
        self._drop_scan_view()
        self.refresh_ui()

    def _on_measurement_created(self, m):
        self._scan_view.tree.measurements.append(m)
        self.save_data()
        status_toast(self, "Scan saved to the tree.", "info")

    # ---------- export / sync ----------

    def export_csv(self):
        default = f"plantation_export_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", default, "CSV (*.csv)")
        if not path:
            return
        try:
            rows = export.export_measurements_csv(self.database, path)
            status_toast(self, f"Exported {rows} rows → {os.path.basename(path)}", "info")
        except Exception as e:
            status_toast(self, f"Export failed: {e}", "error")

    def _auto_export_csv(self):
        from .models import iter_all_measurements
        has_measurements = any(True for _ in iter_all_measurements(self.database))
        if not has_measurements:
            return None
        name = f"plantation_export_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.csv"
        path = os.path.join(paths.EXPORTS_DIR, name)
        try:
            rows = export.export_measurements_csv(self.database, path)
            return path, rows
        except Exception as e:
            status_toast(self, f"Auto-export failed: {e}", "error")
            return None

    def _count_unsynced(self):
        from .models import iter_all_measurements
        return sum(1 for m in iter_all_measurements(self.database) if not getattr(m, "synced", False))

    def _drive_preflight(self):
        """Returns (ok: bool, reason: str, mode: str). ok=False means we
        cannot even attempt Drive upload; the caller should warn the user
        and stop. ok=True means pre-flight passed; the caller proceeds
        with the upload and any per-item failure shows as status_toast.
        """
        mode = os.environ.get("ERTERFACE_DRIVE_MODE", "oauth").strip().lower()
        if mode == "off":
            return False, "Drive sync disabled (ERTERFACE_DRIVE_MODE=off).", mode
        if not os.path.exists(paths.DRIVE_CLIENT_SECRET_FILE):
            return (
                False,
                f"OAuth not configured. Place client secret at {paths.DRIVE_CLIENT_SECRET_FILE}, then retry.",
                mode,
            )
        return True, "", mode

    def sync_drive(self):
        ok, reason, mode = self._drive_preflight()
        if not ok:
            if "OAuth not configured" in reason:
                status_toast(self, "Drive sync not set up. Opening setup…", "warn")
                self._open_drive_setup()
            else:
                status_toast(self, reason, "warn")
            self.set_sync_indicator("idle")
            return

        if self._drive_mode != "local" and mode != "local":
            pending = self._count_unsynced()
            if pending == 0:
                status_toast(self, "Nothing to sync — all measurements already on Drive.", "info")
                self.set_sync_indicator("ok")
                return
            self.set_sync_indicator("syncing")
            status_toast(self, f"Syncing {pending} measurement{'s' if pending != 1 else ''} to Drive…", "info")
        else:
            self.set_sync_indicator("syncing")
            status_toast(self, "Syncing to local staging…", "info")
        try:
            client = DriveClient()
            uploaded, failed, skipped = sync_unsynced(self.database, client=client)
            self.save_data()
            if failed == 0:
                self.set_sync_indicator("ok")
                if self._drive_mode == "local" or mode == "local":
                    status_toast(
                        self,
                        f"Saved locally. ↑{uploaded} up · ={skipped} already staged.",
                        "info",
                    )
                else:
                    status_toast(
                        self,
                        f"Sync done. ↑{uploaded} up · ={skipped} already on Drive.",
                        "info",
                    )
            else:
                self.set_sync_indicator("error")
                status_toast(
                    self,
                    f"Sync finished with errors. ↑{uploaded} up · ✗{failed} failed · ={skipped}.",
                    "error",
                )
        except FileNotFoundError as e:
            self.set_sync_indicator("idle")
            QMessageBox.warning(
                self,
                "Drive setup required",
                f"{e}\n\nPlace your OAuth Desktop client JSON at:\n{paths.DRIVE_CLIENT_SECRET_FILE}\n\nThen click Sync again.",
            )
        except Exception as e:
            self.set_sync_indicator("error")
            status_toast(self, f"Sync failed: {e}", "error")

    def set_status(self, text):
        self.lbl_status.setText(text)
        self._status_override = bool(text)

    def _open_drive_setup(self):
        dlg = DriveSetupDialog(
            is_dark_mode=self.is_dark_mode,
            on_signed_in=self.sync_drive,
            parent=self,
        )
        if dlg.exec():
            if dlg.use_offline():
                os.environ["ERTERFACE_DRIVE_MODE"] = "local"
                self._drive_mode = "local"
                self._style_drive_mode_button()
                status_toast(self, "Offline mode on. Sync writes to ./drive_staging/.", "info")
            elif os.path.exists(paths.DRIVE_CLIENT_SECRET_FILE):
                os.environ["ERTERFACE_DRIVE_MODE"] = "oauth"
                self._drive_mode = "oauth"
                self._style_drive_mode_button()

    def set_sync_indicator(self, level):
        colors = {
            "idle": ("#8a94a6", "Sync status: idle"),
            "syncing": ("#1e73be", "Sync status: in progress"),
            "ok": ("#1e8e3e", "Sync status: up to date"),
            "error": ("#DA3633", "Sync status: error"),
        }
        color, tip = colors.get(level, colors["idle"])
        self.sync_indicator.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        self.sync_indicator.setToolTip(tip)

    # ---------- exit / close ----------

    def close_app_safe(self):
        mb = QMessageBox(self)
        mb.setWindowTitle("Exit Confirmation")
        mb.setText("Are you sure you want to exit?")
        mb.setInformativeText("Unsaved changes will be written. An auto-export and sync will run.")
        mb.setIcon(QMessageBox.Icon.Question)
        mb.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        mb.setDefaultButton(QMessageBox.StandardButton.No)
        mb.setStyleSheet(
            "QMessageBox { min-width: 360px; } QLabel { font-size: 14px; } "
            "QPushButton { font-size: 14px; min-height: 40px; min-width: 100px; "
            "border-radius: 6px; padding: 4px 12px; }"
        )
        if mb.exec() == QMessageBox.StandardButton.Yes:
            self.close()

    def closeEvent(self, event):
        self._drop_scan_view()
        if self._capture_session is not None:
            # Cancels a capture, saves instrument settings, ends the session log.
            self._capture_session.close()
            self._capture_session = None
        if self.timer.isActive():
            self.timer.stop()
        if hasattr(self, "_active_keyboard") and self._active_keyboard is not None:
            try:
                self._active_keyboard.deleteLater()
            except RuntimeError:
                pass
            self._active_keyboard = None
        try:
            self.save_data()
            status_toast(self, "Saved.", "info")
        except Exception as e:
            status_toast(self, f"Save failed on close: {e}", "error")

        result = self._auto_export_csv()
        if result is not None:
            path, rows = result
            status_toast(self, f"Auto-exported {rows} rows → {os.path.basename(path)}", "info")

        try:
            ok, reason, mode = self._drive_preflight()
            if not ok:
                self.set_sync_indicator("idle")
            elif self._count_unsynced() == 0:
                self.set_sync_indicator("ok")
                status_toast(self, "Auto-sync: nothing new to upload.", "info")
            else:
                self.set_sync_indicator("syncing")
                client = DriveClient()
                uploaded, failed, skipped = sync_unsynced(self.database, client=client)
                self.save_data()
                if failed:
                    self.set_sync_indicator("error")
                    status_toast(
                        self,
                        f"Auto-sync: ↑{uploaded} ✗{failed} ={skipped}",
                        "warn",
                    )
                else:
                    self.set_sync_indicator("ok")
                    status_toast(self, f"Auto-sync: ↑{uploaded} ={skipped}", "info")
        except FileNotFoundError as e:
            self.set_sync_indicator("idle")
            status_toast(self, f"Auto-sync skipped: OAuth not configured.", "warn")
        except Exception as e:
            self.set_sync_indicator("error")
            status_toast(self, f"Auto-sync failed: {e}", "error")

        super().closeEvent(event)
