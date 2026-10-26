"""AddEntityDialog — Plantation / Tree add and edit.
Measurement CRUD is intentionally absent (measurements are created by
ScanView only — see SPEC.md).

Validation runs in `accept()`. If it fails, the dialog stays open and an
inline QLabel shows the first failing rule. Required fields are marked
with a trailing `*`.
"""

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .models import Plantation, Tree
from .widgets.keyboard import TouchLineEdit


ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,32}$")


class AddEntityDialog(QDialog):
    def __init__(
        self,
        level_name,
        existing_items,
        is_dark_mode,
        edit_mode=False,
        current_data=None,
        presets=None,
        parent=None,
    ):
        super().__init__(parent)
        self.level_name = level_name
        self.existing_items = existing_items or []
        self.is_dark_mode = is_dark_mode
        self.edit_mode = edit_mode
        self.current_data = current_data
        self._presets = presets or []

        mode_str = "Edit" if edit_mode else "Add"
        self.setWindowTitle(f"{mode_str} {level_name}")
        self.setMinimumWidth(540)
        self.setModal(True)
        self.inputs = {}

        bg = "#1e1e1e" if is_dark_mode else "#fafbfc"
        text = "#f5f5f5" if is_dark_mode else "#1a202c"
        sub = "#a0aec0" if is_dark_mode else "#5a6b7e"
        input_bg = "#2a2a2a" if is_dark_mode else "#ffffff"
        input_border = "#4a4a4a" if is_dark_mode else "#cbd5e0"
        accent = "#1e8e3e"
        error_color = "#DA3633"

        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; color: {text}; }}"
            f"QLabel {{ color: {text}; font-size: 14px; background: transparent; border: none; }}"
            f"QLabel#dialogSubtitle {{ color: {sub}; font-size: 12px; }}"
            f"QLabel#dialogError {{ color: {error_color}; font-size: 13px; "
            f"font-weight: bold; padding: 6px 0px 6px 0px; }}"
            f"QLabel#dialogRequired {{ color: {error_color}; font-weight: bold; }}"
            f"QLineEdit {{"
            f"background-color: {input_bg}; color: {text}; font-size: 15px;"
            f"padding: 8px 10px 8px 10px; border: 1px solid {input_border}; "
            f"border-radius: 6px;"
            f"}}"
            f"QLineEdit:focus {{ border: 1px solid {accent}; }}"
            f"QDialogButtonBox {{ padding-top: 8px; }}"
            f"QPushButton {{"
            f"font-size: 14px; font-weight: 600; min-height: 40px; "
            f"min-width: 100px; padding: 4px 16px 4px 16px; border-radius: 6px; "
            f"border: 1px solid {input_border}; background-color: {input_bg}; "
            f"color: {text};"
            f"}}"
            f"QPushButton:pressed {{ background-color: {input_border}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        subtitle = QLabel(self._subtitle_text())
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setVerticalSpacing(10)
        self.form.setHorizontalSpacing(12)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addLayout(self.form)

        self._build_fields()

        self.error_label = QLabel("")
        self.error_label.setObjectName("dialogError")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        self.keyboard_holder = QWidget()
        self.keyboard_holder.setVisible(False)
        self.keyboard_layout = QVBoxLayout(self.keyboard_holder)
        self.keyboard_layout.setContentsMargins(0, 8, 0, 0)
        self.keyboard_layout.setSpacing(0)
        layout.addWidget(self.keyboard_holder)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setText("Save")
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            f"QPushButton {{"
            f"font-size: 14px; font-weight: 700; min-height: 40px; "
            f"min-width: 110px; padding: 4px 16px 4px 16px; border-radius: 6px; "
            f"border: 1px solid {accent}; background-color: {accent}; color: white;"
            f"}}"
            f"QPushButton:pressed {{ background-color: #166b2e; }}"
        )
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _subtitle_text(self):
        if self.edit_mode:
            return f"Edit this {self.level_name.lower()}. Required fields marked with *."
        return f"Add a new {self.level_name.lower()}. Required fields marked with *."

    def _add_text(self, label, key, value="", required=False, presets=None):
        label_text = label + ":"
        lbl_widget = QLabel(label_text)
        lbl_widget.setStyleSheet("background: transparent; border: none;")
        if required:
            star = QLabel("*")
            star.setObjectName("dialogRequired")
            star.setStyleSheet(
                f"color: #DA3633; font-weight: bold; background: transparent; border: none;"
            )
            container = QWidget()
            container.setStyleSheet("background: transparent; border: none;")
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(2)
            h.addWidget(lbl_widget)
            h.addWidget(star)
            h.addStretch()
            row_label = container
        else:
            row_label = lbl_widget
        edit = TouchLineEdit(is_dark_mode=self.is_dark_mode, presets=presets or self._presets)
        edit.setText(value)
        edit.setPlaceholderText("Required" if required else "Optional")
        self.form.addRow(row_label, edit)
        self.inputs[key] = edit

    def _build_fields(self):
        if self.level_name == "Plantation":
            name = self.current_data.name if self.edit_mode else ""
            pid = self.current_data.plant_id if self.edit_mode else ""
            self._add_text("Name", "name", name, required=True)
            self._add_text("Plantation ID", "id", pid, required=True)
        elif self.level_name == "Tree":
            existing_ids = [t.tree_id for t in self.existing_items]
            suggested = self._suggest_next_id("T", existing_ids)
            tid = self.current_data.tree_id if self.edit_mode else suggested
            id_presets = self._id_presets("T", existing_ids, 3)
            self._add_text("Tree ID", "id", tid, required=True, presets=id_presets)
        else:
            raise ValueError(f"AddEntityDialog: unsupported level {self.level_name!r}")

    def _id_presets(self, prefix, existing, count):
        presets = []
        for i in range(1, count + 1):
            candidate = f"{prefix}{i:03d}"
            if candidate not in existing:
                presets.append(candidate)
        if not presets and existing:
            presets = [existing[0]]
        return presets

    @staticmethod
    def _suggest_next_id(prefix, existing):
        nums = []
        for eid in existing:
            if eid.startswith(prefix):
                tail = eid[len(prefix):]
                try:
                    nums.append(int(tail))
                except ValueError:
                    pass
        nxt = (max(nums) + 1) if nums else 1
        return f"{prefix}{nxt:03d}"

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def _clear_error(self):
        self.error_label.setVisible(False)
        self.error_label.setText("")

    def _existing_id_set(self, key):
        ids = set()
        for item in self.existing_items:
            v = getattr(item, key, None)
            if v is not None:
                ids.add(v)
        if self.edit_mode and self.current_data is not None:
            own = getattr(self.current_data, key, None)
            if own in ids:
                ids.discard(own)
        return ids

    def _validate(self):
        if self.level_name == "Plantation":
            name = self.inputs["name"].text().strip()
            pid = self.inputs["id"].text().strip()
            if not name:
                return False, "Name is required."
            if not pid:
                return False, "Plantation ID is required."
            if pid in self._existing_id_set("plant_id"):
                return False, f"Plantation ID '{pid}' already exists."
            return True, ""

        if self.level_name == "Tree":
            tid = self.inputs["id"].text().strip()
            if not tid:
                return False, "Tree ID is required."
            if not ID_PATTERN.match(tid):
                return False, "Tree ID must be 1-32 chars: letters, digits, _ or -."
            if tid in self._existing_id_set("tree_id"):
                return False, f"Tree ID '{tid}' already exists in this plantation."
            return True, ""

        return False, f"Unknown level: {self.level_name}"

    def accept(self):
        ok, msg = self._validate()
        if not ok:
            self._show_error(msg)
            return
        self._clear_error()
        super().accept()

    def get_data(self):
        out = {}
        for key, widget in self.inputs.items():
            out[key] = widget.text().strip()
        return out


def make_entity(level_name, data, parent_node=None):
    if level_name == "Plantation":
        return Plantation(data["name"], data["id"])
    if level_name == "Tree":
        return Tree(data["id"])
    return None
