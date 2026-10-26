#!/usr/bin/env python3
"""Rebuild plantation_data.json from the recorded scans in <thesis root>/scans.

    python import_scans.py            # replace plantation_data.json (old one backed up to data/)
    python import_scans.py --dry-run  # print what would be imported

Two plantations:
  Saline  - one tree per tank position: empty, e1..e12, the pairs (e1-e7 ..
            e6-e12), centre. From the position series (label) and the SSIM /
            wood-at series (target text, as ssim_eval.py reads it).
  Discs   - one tree per cut disc: disc-01, disc-02, ...

Only complete runs with frames are imported. Each becomes an UNCLASSIFIED
measurement with its impedance ratio and pattern (ADR-0075), its tomogram and
its run folder. Runs that are neither a saline position nor a disc (resistor
belts, dummy loads, early coconut tests) are left out and counted.
"""

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))  # the thesis repo: tree_ert

from src.erterface import paths  # noqa: E402
from src.erterface.capture_screen import run_image, run_impedance_ratio  # noqa: E402
from src.erterface.models import Measurement, Plantation, Tree  # noqa: E402
from src.erterface.paths import CLASSIFICATION_UNCLASSIFIED  # noqa: E402

from PyQt6.QtCore import QDateTime, Qt  # noqa: E402

SCANS = paths.THESIS_ROOT / "scans"

PAIRS = [f"e{i}-e{i + 6}" for i in range(1, 7)]
SALINE_ORDER = ["empty"] + [f"e{i}" for i in range(1, 13)] + PAIRS + ["centre"]

_SALINE_POS = re.compile(r"^saline-pos-(e\d+-e\d+|e\d+|centre|empty)(?:-|$)")
_SALINE_EARLY = re.compile(r"^saline-(e\d+|empty)-(?:adjacent|opposite|allel|clipswap|termswap|rpi)")
_DISC = re.compile(r"\bdi?s[ck][-_ ]?0*(\d+)\b", re.I)
_DISC_INTACT = re.compile(r"\bdis[ck]-intact-0*(\d+)", re.I)


_TARGET_SERIES = ("ssim-saline", "saline-tank-wood-at")
"""Series whose position is in the target text ("wood at e5", "wood at e1 e7"),
not the label. A blank target in them is the empty-tank baseline."""


def saline_position(label, target=""):
    for pattern in (_SALINE_POS, _SALINE_EARLY):
        match = pattern.match(label.lower())
        if match:
            return match.group(1)
    if label.lower().startswith(_TARGET_SERIES):
        if not target.strip():
            return "empty"
        from tree_ert.ssim import parse_target  # same parser ssim_eval.py uses

        blocks = parse_target(target)
        if blocks == ["centre"]:
            return "centre"
        numbers = sorted(int(b[1:]) for b in blocks if b.startswith("E"))
        if len(numbers) == len(blocks) and 1 <= len(numbers) <= 2:
            return "-".join(f"e{n}" for n in numbers)
    return None


def disc_number(specimen, label):
    text = f"{specimen} {label}"
    match = _DISC_INTACT.search(text) or _DISC.search(text)
    return int(match.group(1)) if match else None


def specimen_of(run_dir):
    try:
        conditions = json.loads((run_dir / "conditions.json").read_text(encoding="utf-8"))
        return conditions["conditions"].get("specimen_id") or ""
    except (OSError, ValueError, KeyError):
        return ""


def measurement_for(row, run_dir):
    ratio, pattern = run_impedance_ratio(run_dir)
    timestamp = QDateTime.fromString(row["captured_at"], Qt.DateFormat.ISODate)
    if not timestamp.isValid():
        timestamp = QDateTime.fromString(row["run_id"][:15], "yyyyMMdd-HHmmss")
    return Measurement(
        ratio,
        CLASSIFICATION_UNCLASSIFIED,
        timestamp,
        data_path=str(run_dir),
        image_path=run_image(run_dir),
        pattern=pattern or row.get("pattern", ""),
    )


def build():
    saline = Plantation("Saline", "saline")
    discs = Plantation("Discs", "discs")
    saline_trees, disc_trees = {}, {}
    skipped = 0
    with open(SCANS / "index.csv", newline="", encoding="utf-8") as handle:
        rows = sorted(csv.DictReader(handle), key=lambda r: r["run_id"])
    for row in rows:
        run_dir = SCANS / "runs" / row["run_id"]
        if row["outcome"] != "complete" or not (run_dir / "frames.csv").is_file():
            skipped += 1
            continue
        medium = row["medium"].lower()
        label = row["label"]
        if "saline" in medium:
            position = saline_position(label, row["target"])
            if position is None:
                skipped += 1
                continue
            tree = saline_trees.setdefault(position, Tree(position))
        elif medium != "dummy load" and (number := disc_number(specimen_of(run_dir), label)):
            name = f"disc-{number:02d}"
            tree = disc_trees.setdefault(name, Tree(name))
        else:
            skipped += 1
            continue
        tree.measurements.append(measurement_for(row, run_dir))
    order = {name: i for i, name in enumerate(SALINE_ORDER)}
    saline.trees = sorted(saline_trees.values(), key=lambda t: order.get(t.tree_id, len(order)))
    discs.trees = sorted(disc_trees.values(), key=lambda t: t.tree_id)
    return [saline, discs], skipped


def _build_thumbnails(database):
    """Make every card thumbnail now (data/thumbs), so no tree is slow the
    first time it is opened in the app."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QGuiApplication

    from src.erterface.models import iter_all_measurements
    from src.erterface.paths import resolve_data_file
    from src.erterface.widgets.card import _thumbnail

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    made = 0
    for _, _, m in iter_all_measurements(database):
        path = resolve_data_file(m.image_path)
        if path and _thumbnail(path) is not None:
            made += 1
    print(f"thumbnails ready: {made}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    database, skipped = build()
    for plantation in database:
        print(f"{plantation.name}:")
        for tree in plantation.trees:
            print(f"  {tree.tree_id:8s} {len(tree.measurements):3d} scans")
    print(f"left out: {skipped} runs (incomplete, no frames, or neither saline position nor disc)")
    if args.dry_run:
        return 0

    data_file = Path(paths.DATA_FILE)
    if data_file.exists():
        paths.ensure_directories()
        backup = Path(paths.DATA_DIRECTORY) / (
            f"plantation_data.before-import-{datetime.now():%Y%m%d-%H%M%S}.json"
        )
        shutil.copy2(data_file, backup)
        print(f"previous data backed up to {backup}")
    _build_thumbnails(database)
    tmp = data_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps([p.to_dict() for p in database], indent=4), encoding="utf-8")
    tmp.replace(data_file)
    print(f"wrote {data_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
