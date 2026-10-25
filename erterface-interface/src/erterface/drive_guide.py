"""DriveSetupGuideDialog — step-by-step Google Cloud Console setup
for the OAuth Desktop client. Shown when the user taps "Show me how" in
DriveSetupDialog.
"""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import paths


CONSOLE_URL = "https://console.cloud.google.com/"
APIS_LIBRARY_URL = "https://console.cloud.google.com/apis/library"
CONSENT_URL = "https://console.cloud.google.com/apis/credentials/consent"
CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"


class DriveSetupGuideDialog(QDialog):
    def __init__(self, is_dark_mode=False, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.setWindowTitle("How to get the OAuth JSON")
        self.setMinimumSize(680, 600)
        self.setModal(True)

        bg = "#1e1e1e" if is_dark_mode else "#fafbfc"
        text = "#f5f5f5" if is_dark_mode else "#1a202c"
        sub = "#a0aec0" if is_dark_mode else "#5a6b7e"
        accent = "#1e8e3e"
        panel_bg = "#1e1e1e" if is_dark_mode else "#ffffff"
        panel_border = "#3a3a3a" if is_dark_mode else "#cbd5e0"

        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; color: {text}; }}"
            f"QLabel {{ color: {text}; font-size: 14px; background: transparent; border: none; }}"
            f"QLabel#guideStep {{ color: {accent}; font-size: 18px; font-weight: 700; "
            f"background: transparent; border: none; }}"
            f"QLabel#guideBody {{ color: {text}; font-size: 13px; background: transparent; border: none; }}"
            f"QLabel#guideSubtle {{ color: {sub}; font-size: 12px; background: transparent; border: none; }}"
            f"QLabel#guidePath {{ color: {text}; font-size: 12px; "
            f"font-family: 'Geist', monospace; background: {panel_bg}; "
            f"border: 1px solid {panel_border}; border-radius: 5px; padding: 8px; }}"
            f"QFrame#stepPanel {{ background-color: {panel_bg}; "
            f"border: 1px solid {panel_border}; border-radius: 10px; }}"
            f"QPushButton {{ font-size: 13px; font-weight: 600; min-height: 36px; "
            f"padding: 4px 14px 4px 14px; border-radius: 5px; "
            f"border: 1px solid {panel_border}; background-color: {panel_bg}; color: {text}; }}"
            f"QPushButton:pressed {{ background-color: {panel_border}; }}"
            f"QPushButton#primary {{ background-color: {accent}; color: white; "
            f"border: 1px solid {accent}; }}"
            f"QPushButton#primary:pressed {{ background-color: #166b2e; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 12)
        header_layout.setSpacing(4)

        title = QLabel("Get your Google OAuth client JSON")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        header_layout.addWidget(title)

        intro = QLabel(
            "Google needs a one-time OAuth client config so this app can sign "
            "in to your Drive. You create it in Google's Cloud Console, "
            "download the JSON, drop it at the path below. After that, every "
            "Sync is one click."
        )
        intro.setWordWrap(True)
        header_layout.addWidget(intro)

        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        cv = QVBoxLayout(content)
        cv.setContentsMargins(20, 8, 20, 12)
        cv.setSpacing(10)

        steps = [
            (
                "1. Open Google Cloud Console",
                "Click the button below. Sign in with the Google account that owns the Drive folder.",
                CONSOLE_URL,
            ),
            (
                "2. Create a project (or pick existing)",
                "Top-left: project dropdown → New Project. Name it e.g. \"ERTERFACE\". Create. Wait for it to become active.",
                CONSOLE_URL,
            ),
            (
                "3. Enable Google Drive API",
                "Left menu → APIs & Services → Library. Search \"Google Drive API\" → Enable.",
                APIS_LIBRARY_URL,
            ),
            (
                "4. Configure OAuth consent screen",
                "Left menu → APIs & Services → OAuth consent screen. Choose External (or Internal for Workspace). Fill app name + support email. Add scope: ../auth/drive.file. Save.",
                CONSENT_URL,
            ),
            (
                "5. Create OAuth Client ID",
                "Left menu → APIs & Services → Credentials → Create Credentials → OAuth client ID. Application type: Desktop app. Name it e.g. \"ERTERFACE Desktop\". Create.",
                CREDENTIALS_URL,
            ),
            (
                "6. Download the JSON",
                "In the credentials list, click the download icon (⬇) next to your new client. Save the .json file.",
                CREDENTIALS_URL,
            ),
            (
                "7. Place the JSON in this folder",
                f"Move the downloaded file to:",
                None,
            ),
        ]

        for title_text, body, url in steps:
            panel = QFrame()
            panel.setObjectName("stepPanel")
            pv = QVBoxLayout(panel)
            pv.setContentsMargins(14, 12, 14, 12)
            pv.setSpacing(6)

            step_label = QLabel(title_text)
            step_label.setObjectName("guideStep")
            pv.addWidget(step_label)

            body_label = QLabel(body)
            body_label.setObjectName("guideBody")
            body_label.setWordWrap(True)
            pv.addWidget(body_label)

            if "JSON" in title_text and "Place" in title_text:
                path_label = QLabel(paths.DRIVE_CLIENT_SECRET_FILE)
                path_label.setObjectName("guidePath")
                path_label.setWordWrap(True)
                path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                pv.addWidget(path_label)
                copy_btn = QPushButton("Copy path")
                copy_btn.clicked.connect(lambda: self._copy(paths.DRIVE_CLIENT_SECRET_FILE))
                pv.addWidget(copy_btn)
            elif url is not None:
                open_btn = QPushButton(f"Open: {url[:50]}{'...' if len(url) > 50 else ''}")
                open_btn.clicked.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
                pv.addWidget(open_btn)

            cv.addWidget(panel)

        cv.addStretch(1)
        root.addWidget(scroll, stretch=1)

        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 16)
        footer_layout.setSpacing(8)

        done_btn = QPushButton("Done — back to setup")
        done_btn.setObjectName("primary")
        done_btn.clicked.connect(self.accept)
        footer_layout.addStretch()
        footer_layout.addWidget(done_btn)
        root.addWidget(footer)

    def _copy(self, text):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
