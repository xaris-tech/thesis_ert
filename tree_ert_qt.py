"""PyQt6 capture-session UI (ADR-0024).

    python tree_ert_qt.py --demo            # no hardware, deterministic frames
    python tree_ert_qt.py --port COM3       # real ESP32-S3
    python tree_ert_qt.py --port /dev/ttyUSB0

Runs on Windows and on Linux/Raspberry Pi. The Tkinter UI in ``tree_ert_app.py``
is frozen but still works; this does not replace it yet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_SCANS_DIR = Path("scans")
"""Scans recorded from 2026-09-16 onward live here (ADR-0025).

Deliberately not ``phase3a_logs``: that directory holds ~190 flat CSVs from the
legacy capture path, none of which records the conditions it was taken under. A
separate root keeps the documented series unambiguous -- everything under
``scans/`` has a conditions sheet, and that is checkable by looking.
"""

LEGACY_SCANS_DIR = Path("phase3a_logs")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--demo", action="store_true", help="run without hardware")
    parser.add_argument("--port", help="serial port to preselect")
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_SCANS_DIR,
        help=f"where scans are recorded (default: {DEFAULT_SCANS_DIR})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        from tree_ert.qt.main_window import run_app
    except ImportError as exc:
        # The most likely cause on a fresh Raspberry Pi, where PyQt6 comes from
        # apt rather than pip and a venv without --system-site-packages cannot
        # see it. Say so rather than showing a bare traceback.
        print(f"PyQt6 is not available: {exc}", file=sys.stderr)
        print("  Windows: .venv\\Scripts\\python.exe -m pip install PyQt6", file=sys.stderr)
        print("  Raspberry Pi / Debian: sudo apt install python3-pyqt6", file=sys.stderr)
        print("    (and create the venv with --system-site-packages)", file=sys.stderr)
        return 2

    migrate_settings(args.log_dir)

    if args.port:
        from dataclasses import replace

        from tree_ert.settings import (
            UiSettings,
            load_settings,
            save_settings,
            settings_path,
        )

        path = settings_path(args.log_dir)
        stored = load_settings(path) or UiSettings.default()
        save_settings(replace(stored, port=args.port), path)

    return run_app(demo=args.demo, log_dir=args.log_dir)


def migrate_settings(log_dir: Path) -> bool:
    """Seed a new scans folder with the settings from the legacy one.

    Settings live beside the data, so moving the scans root would otherwise
    silently reset the port, current range and DAC code the operator had already
    dialled in. Copies once, on first use of the new folder, and never
    overwrites settings that are already there.
    """
    from tree_ert.settings import load_settings, save_settings, settings_path

    target = settings_path(log_dir)
    if target.exists():
        return False
    stored = load_settings(settings_path(LEGACY_SCANS_DIR))
    if stored is None:
        return False
    try:
        save_settings(stored, target)
    except OSError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
