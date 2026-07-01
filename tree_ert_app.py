from __future__ import annotations

import argparse

from tree_ert.ui import run_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3A ERT hybrid debug UI")
    parser.add_argument("--demo", action="store_true", help="Run without hardware using deterministic demo frames")
    parser.add_argument("--port", default="COM3", help="Serial port for ESP32-S3")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_app(demo=args.demo, port=args.port)


if __name__ == "__main__":
    main()
