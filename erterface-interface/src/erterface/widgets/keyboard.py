"""TouchLineEdit + VirtualKeyboard for touch-driven text input.
The keyboard is shown inside the host dialog (as a child of a
keyboard_holder slot) so clicks route normally through the dialog's
event chain. Size scales to the primary screen so it stays usable on
any monitor. Optional preset buttons appear above the keys.
"""

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QScrollArea,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def key_height_for(window_height):
    """Key height for the window the keyboard docks into: as large as fits with
    the field still visible above it. ~8% of the window: 38 px at 480 px,
    48 px at 600 px, 56 px from ~700 px."""
    return max(36, min(int(window_height * 0.08), 56))


def _find_host(widget):
    """Nearest ancestor offering a ``keyboard_holder`` slot (AddEntityDialog,
    or CardApp for the search box)."""
    p = widget.parent()
    while p is not None:
        if hasattr(p, "keyboard_holder"):
            return p
        p = p.parent()
    return None


class VirtualKeyboard(QWidget):
    text_committed = pyqtSignal(str)
    text_cancelled = pyqtSignal()

    def __init__(self, current_text="", is_dark_mode=False, presets=None, parent=None, key_h=48):
        """Every key is written straight into ``target_edit``, which is always
        visible above the keyboard; Cancel restores the text it started with.
        No echo row: 480 px has no room for a second copy of the text."""
        super().__init__(parent)
        self.text_value = current_text
        self._original = current_text
        self.shift_active = False
        self.is_dark_mode = is_dark_mode
        self.presets = list(presets or [])
        self.target_edit = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if is_dark_mode:
            bg = "#1a1a1a"
            text = "#ffffff"
            btn_bg = "#262626"
            btn_pressed = "#3a3a3a"
            preset_bg = "#262626"
            preset_text = "#a0aec0"
            preset_border = "#3a3a3a"
        else:
            bg = "#eef0f3"
            text = "#1a202c"
            btn_bg = "#ffffff"
            btn_pressed = "#cbd5e0"
            preset_bg = "#ffffff"
            preset_text = "#1a365d"
            preset_border = "#cbd5e0"

        self.setStyleSheet(
            f"VirtualKeyboard {{ background-color: {bg}; border: 1px solid {preset_border}; border-radius: 8px; }}"
            f"QPushButton#keyBtn {{ font-size: 20px; font-weight: 700; min-height: {key_h}px; "
            f"background-color: {btn_bg}; color: {text}; border: 1px solid {preset_border}; "
            f"border-radius: 5px; padding: 0px 0px 0px 0px; }}"
            f"QPushButton#keyBtn:pressed {{ background-color: {btn_pressed}; }}"
            f"QPushButton#keyBtn[active=\"true\"] {{ background-color: #1e73be; color: #ffffff; "
            f"border-color: #1e73be; }}"
            f"QPushButton#presetBtn {{ font-size: 15px; font-weight: 700; min-height: {key_h - 6}px; "
            f"padding: 0px 8px 0px 8px; background-color: {preset_bg}; color: {preset_text}; "
            f"border: 1px solid {preset_border}; border-radius: 5px; }}"
            f"QPushButton#presetBtn:pressed {{ background-color: {btn_pressed}; }}"
            f"QPushButton#doneBtn {{ font-size: 18px; font-weight: 800; min-height: {key_h}px; "
            f"background-color: #1e8e3e; color: #ffffff; border: 1px solid #1e8e3e; "
            f"border-radius: 5px; }}"
            f"QPushButton#doneBtn:pressed {{ background-color: #166b2e; }}"
            f"QPushButton#cancelBtn {{ font-size: 18px; font-weight: 800; min-height: {key_h}px; "
            f"background-color: #c53030; color: #ffffff; border: 1px solid #c53030; "
            f"border-radius: 5px; }}"
            f"QPushButton#cancelBtn:pressed {{ background-color: #9b2c2c; }}"
            # A host dialog's own "QPushButton { min-width: 100px }" cascades
            # into the keys and makes them overlap; keys size from the grid.
            f"QPushButton#keyBtn, QPushButton#presetBtn, QPushButton#doneBtn, "
            f"QPushButton#cancelBtn {{ min-width: 0px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        if self.presets:
            preset_row = QHBoxLayout()
            preset_row.setSpacing(4)
            preset_label = QLabel("Quick:")
            preset_label.setStyleSheet(
                f"color: {preset_text}; font-size: 10px; font-weight: 600; "
                f"background: transparent; border: none;"
            )
            preset_row.addWidget(preset_label)
            for value in self.presets[:6]:
                btn = QPushButton(value)
                btn.setObjectName("presetBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, v=value: self._set_preset(v))
                preset_row.addWidget(btn)
            preset_row.addStretch()
            layout.addLayout(preset_row)

        grid = QGridLayout()
        grid.setSpacing(6)
        layout.addLayout(grid, stretch=1)

        keys = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
            ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
            ["a", "s", "d", "f", "g", "h", "j", "k", "l", "-"],
            ["Shift", "z", "x", "c", "v", "b", "n", "m", ".", "Bksp"],
        ]

        for row_idx, row in enumerate(keys):
            col_offset = 0
            for key in row:
                btn = QPushButton(key)
                btn.setObjectName("keyBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                # Type on press, not release: a fingertip that slides off a
                # key before lifting no longer loses the keystroke.
                btn.pressed.connect(lambda k=key: self.key_pressed(k))
                if key == "Bksp":
                    btn.setAutoRepeat(True)  # hold to delete
                    btn.setAutoRepeatDelay(450)
                    btn.setAutoRepeatInterval(70)
                if key == "Shift":
                    self.btn_shift = btn  # lit while the next letter is upper case
                grid.addWidget(btn, row_idx, col_offset, 1, 1)  # ten keys per row
                col_offset += 1

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_cancel.clicked.connect(self._on_cancel)
        action_row.addWidget(self.btn_cancel, stretch=1)

        self.btn_space = QPushButton("Space")
        self.btn_space.setObjectName("keyBtn")
        self.btn_space.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_space.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_space.pressed.connect(lambda: self.key_pressed("Space"))
        action_row.addWidget(self.btn_space, stretch=3)

        self.btn_done = QPushButton("Done")
        self.btn_done.setObjectName("doneBtn")
        self.btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_done.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_done.setDefault(True)
        self.btn_done.clicked.connect(self._on_done)
        action_row.addWidget(self.btn_done, stretch=1)
        layout.addLayout(action_row)

    def _set_preset(self, value):
        self.text_value = value
        self._write()

    def _write(self):
        if self.target_edit is not None:
            self.target_edit.setText(self.text_value)
            # setText does not count as typing; hosts that track typing (the
            # capture session's run label) listen for textEdited.
            self.target_edit.textEdited.emit(self.text_value)

    def key_pressed(self, key):
        if key == "Bksp":
            self.text_value = self.text_value[:-1]
        elif key == "Space":
            self.text_value += " "
        elif key == "Shift":
            self.shift_active = not self.shift_active
            self._light_shift()
            return
        else:
            if self.shift_active:
                key = key.upper()
            self.text_value += key

        self.shift_active = False
        self._light_shift()
        self._write()

    def _light_shift(self):
        self.btn_shift.setProperty("active", self.shift_active)
        self.btn_shift.style().unpolish(self.btn_shift)
        self.btn_shift.style().polish(self.btn_shift)

    def _on_done(self):
        spin = _spin_box_of(self.target_edit)
        if spin is not None:
            # The box shows a unit suffix (" g/L") the typed text lacks, so its
            # own parser rejects it; set the number directly. Not a number:
            # keep the old value and redraw it.
            try:
                spin.setValue(float(self.text_value))
            except ValueError:
                spin.setValue(spin.value())
        self.text_committed.emit(self.text_value)
        self.hide()

    def _on_cancel(self):
        if self.target_edit is not None:
            self.target_edit.setText(self._original)
            spin = _spin_box_of(self.target_edit)
            if spin is not None:
                spin.setValue(spin.value())  # redraw the untouched value
        self.text_cancelled.emit()
        self.hide()


class TouchLineEdit(QLineEdit):
    def __init__(self, is_dark_mode=False, presets=None, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self._presets = presets or []

    def setPresets(self, presets):
        self._presets = list(presets or [])

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        open_keyboard(self, self.is_dark_mode, self._presets)


class KeyboardOnTap(QObject):
    """Event filter that opens the on-screen keyboard when a plain QLineEdit
    (or a spin box's line edit) it watches is tapped, for widgets this app
    does not own, such as the embedded capture session's forms."""

    def __init__(self, is_dark_mode=False, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode

    def watch(self, root):
        for edit in root.findChildren(QLineEdit):
            if not isinstance(edit, TouchLineEdit):
                edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(obj, QLineEdit)
            and obj.isEnabled()
            and not obj.isReadOnly()
        ):
            open_keyboard(obj, self.is_dark_mode)
        return False


def _spin_box_of(edit):
    parent = edit.parent() if edit is not None else None
    return parent if isinstance(parent, QAbstractSpinBox) else None


def open_keyboard(edit, is_dark_mode=False, presets=()):
    """Dock a VirtualKeyboard for ``edit`` into its nearest keyboard_holder."""
    owner = _find_host(edit)
    if owner is None:
        return

    host = owner.keyboard_holder
    while host.layout().count():
        item = host.layout().takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    spin = _spin_box_of(edit)
    if spin is None:
        start = edit.text()
    elif spin.specialValueText() and spin.text() == spin.specialValueText():
        start = ""  # "not recorded": start from an empty number
    else:
        start = spin.cleanText()  # the number without its unit suffix
    # Size from the app window, not the dialog: a dialog is only as tall as
    # its form until the keyboard arrives.
    window = owner.window()
    if isinstance(owner, QDialog) and owner.parentWidget() is not None:
        window = owner.parentWidget().window()
    vk = VirtualKeyboard(
        start, is_dark_mode, presets, parent=host, key_h=key_height_for(window.height())
    )
    vk._original = edit.text()
    vk.target_edit = edit
    vk.text_committed.connect(lambda _text: host.setVisible(False))
    vk.text_cancelled.connect(lambda: host.setVisible(False))
    host.layout().addWidget(vk)
    host.setVisible(True)
    if isinstance(owner, QDialog):
        owner.adjustSize()
    # The keyboard takes the bottom of the screen; keep the field in view.
    QTimer.singleShot(0, lambda: _reveal(edit))


def _reveal(edit):
    parent = edit.parent()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parent()
    if parent is not None:
        parent.ensureWidgetVisible(edit, 0, 40)
