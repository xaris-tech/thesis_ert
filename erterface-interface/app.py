#!/usr/bin/env python3
"""ERTERFACE entrypoint. Run with: python app.py"""

import sys

from PyQt6.QtWidgets import QApplication

from src.erterface import theme
from src.erterface.app import CardApp


def main():
    app = QApplication(sys.argv)
    theme.load_fonts()
    app.setFont(theme.default_font())
    window = CardApp()
    # The 7" Raspberry Pi display is 800x480: fill it edge to edge with no
    # window decorations. Larger desktop screens keep a normal window.
    screen = app.primaryScreen().size()
    if screen.width() <= 800 or screen.height() <= 480 or "--fullscreen" in sys.argv:
        window.showFullScreen()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
