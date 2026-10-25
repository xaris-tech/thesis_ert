"""DriveSetupDialog — sign in to Google Drive.
Two paths: OAuth sign-in (if client secret present) or paste/pick JSON.
"""

import json as _json
import os
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import paths
from .drive_guide import DriveSetupGuideDialog


class DriveSetupDialog(QDialog):
    def __init__(self, is_dark_mode=False, on_signed_in=None, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.on_signed_in = on_signed_in
        self.setWindowTitle("Sign in to Google Drive")
        self.setMinimumSize(640, 520)
        self.setModal(True)

        bg = "#1e1e1e" if is_dark_mode else "#fafbfc"
        text = "#f5f5f5" if is_dark_mode else "#1a202c"
        sub = "#a0aec0" if is_dark_mode else "#5a6b7e"
        input_bg = "#2a2a2a" if is_dark_mode else "#ffffff"
        input_border = "#4a4a4a" if is_dark_mode else "#cbd5e0"
        accent = "#1e8e3e"
        warn = "#D4A017"
        ok_color = "#1e8e3e"

        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; color: {text}; }}"
            f"QLabel {{ color: {text}; font-size: 13px; background: transparent; border: none; }}"
            f"QLabel#setupSubtitle {{ color: {sub}; font-size: 12px; }}"
            f"QLabel#setupPath {{ color: {text}; font-size: 12px; "
            f"font-family: 'Geist', monospace; background: {input_bg}; "
            f"border: 1px solid {input_border}; border-radius: 5px; padding: 8px; }}"
            f"QLabel#setupStatusOk {{ color: {ok_color}; font-size: 13px; font-weight: 700; }}"
            f"QLabel#setupStatusBad {{ color: {warn}; font-size: 13px; font-weight: 700; }}"
            f"QPlainTextEdit {{ background-color: {input_bg}; color: {text}; "
            f"font-size: 12px; font-family: 'Geist', monospace; "
            f"border: 1px solid {input_border}; border-radius: 5px; padding: 6px; }}"
            f"QPushButton {{ font-size: 13px; font-weight: 600; min-height: 36px; "
            f"padding: 4px 14px 4px 14px; border-radius: 5px; "
            f"border: 1px solid {input_border}; background-color: {input_bg}; color: {text}; }}"
            f"QPushButton:pressed {{ background-color: {input_border}; }}"
            f"QPushButton#primary {{ background-color: {accent}; color: white; "
            f"border: 1px solid {accent}; font-size: 15px; min-height: 50px; }}"
            f"QPushButton#primary:pressed {{ background-color: #166b2e; }}"
            f"QPushButton#primary:disabled {{ background-color: #6a7286; "
            f"border: 1px solid #6a7286; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Google Drive sync")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Sync uploads each measurement + its .npy + .png + .json to a "
            "Google Drive folder. One-tap sign-in below."
        )
        subtitle.setObjectName("setupSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.btn_signin = QPushButton("Sign in with Google")
        self.btn_signin.setObjectName("primary")
        self.btn_signin.clicked.connect(self._on_signin)
        layout.addWidget(self.btn_signin)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        manual_label = QLabel("First time? Configure the OAuth client:")
        manual_label.setStyleSheet("font-weight: 600; margin-top: 8px;")
        layout.addWidget(manual_label)

        guide_row = QHBoxLayout()
        guide_row.setSpacing(8)
        self.btn_guide = QPushButton("Show me how (step-by-step guide)")
        self.btn_guide.clicked.connect(self._open_guide)
        guide_row.addWidget(self.btn_guide)
        guide_row.addStretch()
        layout.addLayout(guide_row)

        offline_row = QHBoxLayout()
        offline_row.setSpacing(8)
        self.btn_offline = QPushButton("Use offline mode (no setup)")
        self.btn_offline.clicked.connect(self._on_offline)
        offline_row.addWidget(self.btn_offline)
        offline_row.addStretch()
        layout.addLayout(offline_row)

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self.lbl_path = QLabel(paths.DRIVE_CLIENT_SECRET_FILE)
        self.lbl_path.setObjectName("setupPath")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_row.addWidget(self.lbl_path, stretch=1)
        layout.addLayout(path_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.btn_open = QPushButton("Open folder")
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_pick = QPushButton("Pick file…")
        self.btn_pick.clicked.connect(self._pick_file)
        self.btn_refresh = QPushButton("Refresh status")
        self.btn_refresh.clicked.connect(self._refresh_status)
        action_row.addWidget(self.btn_open)
        action_row.addWidget(self.btn_pick)
        action_row.addWidget(self.btn_refresh)
        action_row.addStretch()
        layout.addLayout(action_row)

        paste_label = QLabel("Or paste the OAuth JSON:")
        paste_label.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(paste_label)

        self.txt_json = QPlainTextEdit()
        self.txt_json.setPlaceholderText('{"installed": {"client_id": "...", ...}}')
        self.txt_json.setFixedHeight(100)
        layout.addWidget(self.txt_json)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("Save JSON")
        self.btn_save.clicked.connect(self._save_json)
        save_row.addWidget(self.btn_save)
        save_row.addStretch()
        layout.addLayout(save_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._refresh_status()

    def _open_folder(self):
        target_dir = os.path.dirname(paths.DRIVE_CLIENT_SECRET_FILE)
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError:
            pass
        try:
            if sys.platform == "win32":
                os.startfile(target_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target_dir])
            else:
                subprocess.Popen(["xdg-open", target_dir])
        except Exception:
            pass

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select OAuth client JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as src, open(
                paths.DRIVE_CLIENT_SECRET_FILE, "w", encoding="utf-8"
            ) as dst:
                dst.write(src.read())
            self._refresh_status()
        except OSError as e:
            self.lbl_status.setObjectName("setupStatusBad")
            self.lbl_status.setText(f"Could not copy file: {e}")

    def _save_json(self):
        text = self.txt_json.toPlainText().strip()
        if not text:
            self.lbl_status.setObjectName("setupStatusBad")
            self.lbl_status.setText("Paste the JSON content first.")
            return
        try:
            parsed = _json.loads(text)
            if not isinstance(parsed, dict) or "installed" not in parsed and "web" not in parsed:
                raise ValueError("JSON does not look like an OAuth client config.")
        except Exception as e:
            self.lbl_status.setObjectName("setupStatusBad")
            self.lbl_status.setText(f"Invalid JSON: {e}")
            return
        try:
            os.makedirs(os.path.dirname(paths.DRIVE_CLIENT_SECRET_FILE), exist_ok=True)
            with open(paths.DRIVE_CLIENT_SECRET_FILE, "w", encoding="utf-8") as f:
                f.write(text)
            self.txt_json.clear()
            self._refresh_status()
        except OSError as e:
            self.lbl_status.setObjectName("setupStatusBad")
            self.lbl_status.setText(f"Could not write file: {e}")

    def _refresh_status(self):
        if os.path.exists(paths.DRIVE_CLIENT_SECRET_FILE):
            self.lbl_status.setObjectName("setupStatusOk")
            self.lbl_status.setText("Ready — click Sign in with Google to authenticate.")
        else:
            self.lbl_status.setObjectName("setupStatusBad")
            self.lbl_status.setText("Not configured. Use Open folder, Pick file, or paste the JSON below.")

    def _on_signin(self):
        if not os.path.exists(paths.DRIVE_CLIENT_SECRET_FILE):
            self._prompt_setup_first()
            return
        if self.on_signed_in is not None:
            self.accept()
            self.on_signed_in()

    def _prompt_setup_first(self):
        mb = QMessageBox(self)
        mb.setWindowTitle("One-time setup required")
        mb.setIcon(QMessageBox.Icon.Information)
        mb.setText(
            "Sign in with Google needs a one-time OAuth setup before it can "
            "open the browser for you."
        )
        mb.setInformativeText(
            f"Place your Google OAuth Desktop client JSON at:\n"
            f"  {paths.DRIVE_CLIENT_SECRET_FILE}\n\n"
            f"Or click Pick file… below to choose one from disk, or paste "
            f"its content in the box below and click Save JSON."
        )
        open_btn = mb.addButton("Open folder…", QMessageBox.ButtonRole.ActionRole)
        pick_btn = mb.addButton("Pick file…", QMessageBox.ButtonRole.ActionRole)
        ok_btn = mb.addButton("Got it", QMessageBox.ButtonRole.AcceptRole)
        mb.setDefaultButton(pick_btn)
        mb.exec()
        clicked = mb.clickedButton()
        if clicked is open_btn:
            self._open_folder()
        elif clicked is pick_btn:
            self._pick_file()

    def _on_offline(self):
        self._offline_mode = True
        self.accept()

    def _open_guide(self):
        dlg = DriveSetupGuideDialog(is_dark_mode=self.is_dark_mode, parent=self)
        dlg.exec()

    def use_offline(self):
        return getattr(self, "_offline_mode", False)
