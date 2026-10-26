#!/usr/bin/env python3
"""Rebuild plantation_data.json from the recorded scans in <thesis root>/scans.

    python import_scans.py            # replace plantation_data.json (old one backed up to data/)
    python import_scans.py --dry-run  # print what would be imported

Two plantations:
  Saline  - one tree per tank position: empty, e1..e12, the pairs (e1-e7 ..
            e6-e12), centre. Position from the position-series label, else
            from the target text ("wood at e6", "empty tank"), read with the
            parser ssim_eval.py uses.
  Discs   - one tree per cut disc: disc-01, disc-02, ...

Every run folder is considered, not only index.csv rows: some runs never got
an index row, and runs stopped early still hold real frames. A run is imported
if it has at least one complete frame. Each becomes an UNCLASSIFIED
measurement with its impedance ratio and pattern (ADR-0075), its run folder,
and a display image holding only the tomogram (ADR-0074) - for runs older than
the display copy, the left panel cut out of the run's saved figure into
data/views/ (never redrawn from the .npz: that has no mesh, see run_view).
Runs that are neither a saline position nor a disc are left out and counted.
"""

import argparse
import csv
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))  # the thesis repo: tree_ert, phase3a_*

from PyQt6.QtCore import QDateTime, Qt  # noqa: E402

from src.erterface import paths  # noqa: E402
from src.erterface.capture_screen import run_impedance_ratio  # noqa: E402
from src.erterface.models import Measurement, Plantation, Tree  # noqa: E402
from src.erterface.paths import CLASSIFICATION_UNCLASSIFIED  # noqa: E402

SCANS = paths.THESIS_ROOT / "scans"
VIEWS = Path(paths.DATA_DIRECTORY) / "views"

PAIRS = [f"e{i}-e{i + 6}" for i in range(1, 7)]
SALINE_ORDER = ["empty"] + [f"e{i}" for i in range(1, 13)] + PAIRS + ["centre"]

_SALINE_POS = re.compile(r"^saline-pos-(e\d+-e\d+|e\d+|centre|empty)(?:-|$)")
_SALINE_EARLY = re.compile(r"^saline-(e\d+|empty)-(?:adjacent|opposite|allel|clipswap|termswap|rpi)")
_BLANK_IS_EMPTY = ("ssim-saline", "saline-tank-wood-at", "saline-tank-baseline")
"""Series in which a blank target is the empty-tank baseline."""
_DISC = re.compile(r"\bdi?s[ck][-_ ]?0*(\d+)\b", re.I)
_DISC_INTACT = re.compile(r"\bdis[ck]-intact-0*(\d+)", re.I)


def saline_position(label, target=""):
    label, target = label.lower(), target.strip()
    for pattern in (_SALINE_POS, _SALINE_EARLY):
        match = pattern.match(label)
        if match:
            return match.group(1)
    if "empty" in target.lower() or (not target and label.startswith(_BLANK_IS_EMPTY)):
        return "empty"
    if "wood" not in target.lower() and "block" not in target.lower():
        return None  # a coconut sample or resistor in the tank, not a position
    if any(word in target.lower() for word in ("steel", "rod", "metal")):
        return None  # a conductor in the tank: not the same target as a wood position
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


def read_conditions(run_dir):
    try:
        return json.loads((run_dir / "conditions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# -- display image: the tomogram alone ---------------------------------------

def run_view(run_dir):
    """Path of a tomogram-only image for this run, making one if needed.

    The run's own display copy (ADR-0074) when it has one. Otherwise the left
    panel is cut out of the run's saved figure into data/views/ (derived,
    git-ignored; the run folder is never written to). It is cut, not redrawn:
    the .npz holds one value per mesh element but not the mesh, and a mesh
    rebuilt today orders its elements differently, which scrambled the image.
    Difference image first, else absolute.
    """
    for name in ("reconstruction-image.png", "absolute-image.png"):
        if (run_dir / name).is_file():
            return str(run_dir / name)
    label = run_dir.name.split("-", 2)[-1]
    for kind, title in (("reconstruction", f"{label} vs baseline"), ("absolute", f"{label} (absolute)")):
        figure = run_dir / f"{kind}.png"
        if not figure.is_file():
            continue
        view = VIEWS / f"{run_dir.name}-{kind}-image.png"
        if not view.is_file():
            try:
                left_panel(figure, view, title)
            except Exception as exc:  # noqa: BLE001 - one odd figure must not stop the import
                # An early figure style with no colour to find: show it whole.
                print(f"  could not cut {figure} ({exc}); showing the full figure")
                return str(figure)
        if view.is_file():
            return str(view)
    return ""


def left_panel(figure, out, title):
    """Cut the left tomogram out of a two-panel run figure, keep its pixels
    exactly, blank everything outside the disc and redraw E1..E12 and a title.

    The labels are redrawn rather than cut because the panel title touches the
    E4 label. Every recorded run uses the default electrode mapping (offset 0,
    not reversed), so the labels sit where the mesh's el_pos puts them: E1 at
    180 degrees, clockwise on screen, radius 1.12 (electrode_label_positions).
    """
    import math

    import numpy as np
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    img = QImage(str(figure)).convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    a = np.frombuffer(img.constBits().asstring(img.sizeInBytes()), np.uint8)
    a = a.reshape(h, img.bytesPerLine())[:, : w * 3].reshape(h, w, 3).astype(int)

    colour = (a.max(2) - a.min(2)) > 40  # coolwarm pixels, not text or grey
    # The left disc is the first band of columns holding colour; in some
    # figures the right panel starts before the halfway line.
    cols = np.flatnonzero(colour.sum(0) > 2)
    if cols.size == 0:
        raise ValueError("no tomogram found")
    breaks = np.flatnonzero(np.diff(cols) > 12)
    last_col = cols[breaks[0]] if breaks.size else cols[-1]
    colour[:, last_col + 1:] = False
    colour[:, : cols[0]] = False
    ys, xs = np.nonzero(colour)
    if ys.size < 500:
        raise ValueError("no tomogram found in the left half")
    xlo, xhi = np.percentile(xs, [0.2, 99.8])
    ylo, yhi = np.percentile(ys, [0.2, 99.8])
    cx, cy = (xlo + xhi) / 2, (ylo + yhi) / 2
    r0 = max(xhi - xlo, yhi - ylo) / 2

    # Disc edge along 180 rays: outward to the first white run. Rays that run
    # into a label can only overestimate, so take a low percentile.
    disc = (a.min(2) < 246) & (a.max(2) > 140)  # the tomogram incl. its grey
    edges = []
    for t in np.linspace(0, 2 * math.pi, 180, endpoint=False):
        last, white = None, 0
        for r in np.arange(0.8 * r0, 1.15 * r0, 0.5):
            x, y = int(round(cx + r * math.cos(t))), int(round(cy + r * math.sin(t)))
            if not (0 <= x < w and 0 <= y < h):
                break
            if disc[y, x]:
                last, white = r, 0
            else:
                white += 1
                if white >= 3:
                    break
        if last:
            edges.append(last)
    radius = float(np.percentile(edges, 30))

    pad, band = int(radius * 0.30), int(radius * 0.30)
    size = int(2 * radius) + 2 * pad
    out_a = np.full((size + band, size, 3), 255, np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    keep_y, keep_x = np.nonzero((xx - cx) ** 2 + (yy - cy) ** 2 <= (radius - 1.5) ** 2)
    x0, y0 = int(cx - radius) - pad, int(cy - radius) - pad
    inside = (keep_y - y0 + band < size + band) & (keep_x - x0 < size) & (keep_x - x0 >= 0)
    out_a[keep_y[inside] - y0 + band, keep_x[inside] - x0] = a[keep_y[inside], keep_x[inside]]
    canvas = QImage(out_a.tobytes(), size, size + band, size * 3, QImage.Format.Format_RGB888).copy()

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont()
    font.setPixelSize(int(radius * 0.11))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    ccx, ccy = cx - x0, cy - y0 + band
    for i in range(12):
        t = math.radians(180 - 30 * i)
        lx, ly = ccx + 1.14 * radius * math.cos(t), ccy - 1.14 * radius * math.sin(t)
        painter.drawText(
            QRectF(lx - radius * 0.15, ly - radius * 0.08, radius * 0.3, radius * 0.16),
            Qt.AlignmentFlag.AlignCenter, f"E{i + 1}",
        )
    font = QFont()
    pixel = int(band * 0.42)
    font.setPixelSize(pixel)
    while pixel > 8 and QFontMetrics(font).horizontalAdvance(title) > size * 0.94:
        pixel -= 1  # long run names shrink to fit rather than being cut off
        font.setPixelSize(pixel)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, band), Qt.AlignmentFlag.AlignCenter, title)
    painter.end()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(out)):
        raise OSError(f"could not write {out}")


# -- import --------------------------------------------------------------------

def measurement_for(run_dir, frames_pattern, created_at):
    ratio, pattern = run_impedance_ratio(run_dir)
    timestamp = QDateTime.fromString(created_at or "", Qt.DateFormat.ISODate)
    if not timestamp.isValid():
        timestamp = QDateTime.fromString(run_dir.name[:15], "yyyyMMdd-HHmmss")
    return Measurement(
        ratio,
        CLASSIFICATION_UNCLASSIFIED,
        timestamp,
        data_path=str(run_dir),
        image_path=run_view(run_dir),
        pattern=pattern or frames_pattern,
    )


def build():
    from tree_ert import survey

    index = {}
    with open(SCANS / "index.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            index[row["run_id"]] = row

    saline_trees, disc_trees = {}, {}
    skipped = 0
    for run_dir in sorted(p for p in (SCANS / "runs").iterdir() if p.is_dir()):
        record = read_conditions(run_dir)
        row = index.get(run_dir.name, {})
        if record is None:
            skipped += 1
            continue
        conditions = record.get("conditions", {})
        try:
            frames = survey.load_frames(run_dir)
        except Exception:  # noqa: BLE001 - unreadable frames: nothing to show
            frames = []
        if not frames:
            skipped += 1
            continue
        medium = (conditions.get("medium") or row.get("medium") or "").lower()
        label = record.get("label") or row.get("label") or ""
        target = conditions.get("target_description") or row.get("target") or ""
        if "saline" in medium:
            position = saline_position(label, target)
            if position is None:
                skipped += 1
                continue
            tree = saline_trees.setdefault(position, Tree(position))
        elif medium != "dummy load" and (
            number := disc_number(conditions.get("specimen_id") or "", label)
        ):
            name = f"disc-{number:02d}"
            tree = disc_trees.setdefault(name, Tree(name))
        else:
            skipped += 1
            continue
        tree.measurements.append(
            measurement_for(run_dir, frames[0].pattern.lower(), record.get("created_at"))
        )

    order = {name: i for i, name in enumerate(SALINE_ORDER)}
    saline = Plantation("Saline", "saline")
    saline.trees = sorted(saline_trees.values(), key=lambda t: order.get(t.tree_id, len(order)))
    discs = Plantation("Discs", "discs")
    discs.trees = sorted(disc_trees.values(), key=lambda t: t.tree_id)
    return [saline, discs], skipped


def _build_thumbnails(database):
    """Make every card thumbnail now (data/thumbs), so no tree is slow the
    first time it is opened in the app."""
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

    if args.dry_run:
        global run_view  # list only: render nothing

        def run_view(run_dir):  # noqa: F811
            return ""

    database, skipped = build()
    for plantation in database:
        total = sum(len(t.measurements) for t in plantation.trees)
        print(f"{plantation.name}: {len(plantation.trees)} trees, {total} scans")
        for tree in plantation.trees:
            shown = sum(1 for m in tree.measurements if m.image_path)
            print(f"  {tree.tree_id:8s} {len(tree.measurements):3d} scans  ({shown} with a tomogram)")
    print(f"left out: {skipped} run folders (no frames, or neither a saline position nor a disc)")
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
