"""Collect the 2026-10-14 saline position series into exports/saline-absolute-2026-10-14/."""
import csv
import json
import shutil
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, r"D:\Here\asd")
import numpy as np  # noqa: E402
import phase3a_unified_reconstruct as unified  # noqa: E402
from tree_ert import absolute, survey  # noqa: E402
from tree_ert import reconstruction  # noqa: E402
from tree_ert.settings import settings_from_dict  # noqa: E402

RUNS = Path(r"D:\Here\asd\scans\runs")
OUT = Path(r"D:\Here\asd\exports\saline-absolute-2026-10-14")
GROUPS = [  # (folder, glob, expected trough angle in degrees or None)
    ("1-wood-e6", "20261014-1*saline-matrix-adjacent*", 30.0),
    ("2-wood-e4", "20261014-18*saline-e4*", 90.0),
    ("3-wood-e8", "20261014-19*saline-e8*", 330.0),
    ("4-wood-e10", "20261014-19*saline-e10*", 270.0),
    ("5-no-wood", "20261014-2*saline-empty*", None),
]


def angle_error(found, expected):
    return (found - expected + 180.0) % 360.0 - 180.0


OUT.mkdir(parents=True, exist_ok=True)
rows = []
empties = {}
for folder, pattern, expected in GROUPS:
    target = OUT / folder
    target.mkdir(exist_ok=True)
    for d in sorted(RUNS.glob(pattern)):
        if not (d / "summary.txt").exists() or not (d / "absolute.png").exists():
            continue
        s = settings_from_dict(json.load(open(d / "conditions.json"))["settings"])
        frames = survey.load_frames(d)
        res, noise, rep = absolute.evaluate(frames, s)
        tag = f"dac{s.dac}-st{s.settle_ms}-n{s.samples}-{d.name[9:15]}"
        shutil.copy2(d / "absolute.png", target / f"absolute-{tag}.png")
        trough_deg = None
        text = res.trough_text()
        if "lobe at " in text:
            trough_deg = float(text.split("lobe at ")[1].split(" deg")[0])
        rows.append({
            "position": folder, "run_id": d.name, "dac": s.dac, "settle_ms": s.settle_ms,
            "samples": s.samples, "gate": "PASS" if rep.passed else "; ".join(rep.reasons),
            "misfit_percent": round(res.residual_percent, 2),
            "reciprocity_percent": round(rep.reciprocity_percent, 2),
            "noise_percent": round(rep.noise_relative_percent, 3),
            "significance": round(rep.significance, 1) if rep.significance else "",
            "sigma0_ms": round(res.sigma0, 3),
            "trough_deg": trough_deg if trough_deg is not None else "",
            "expected_deg": expected if expected is not None else "",
            "angle_error_deg": round(angle_error(trough_deg, expected), 1)
            if (trough_deg is not None and expected is not None) else "",
            "trough": text,
        })
        if folder == "5-no-wood":
            empties.setdefault((s.dac, s.settle_ms, s.samples), (d, s, frames))
        print(folder, tag, rows[-1]["gate"], text, flush=True)

with open(OUT / "summary.csv", "w", newline="", encoding="utf-8") as h:
    w = csv.DictWriter(h, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# Difference images: each wood run against the no-wood run at the same settings.
diff_dir = OUT / "difference-vs-no-wood"
diff_dir.mkdir(exist_ok=True)
for row in rows:
    if row["position"] == "5-no-wood":
        continue
    key = (row["dac"], row["settle_ms"], row["samples"])
    if key not in empties:
        continue
    bd, bs, bframes = empties[key]
    d = RUNS / row["run_id"]
    s = settings_from_dict(json.load(open(d / "conditions.json"))["settings"])
    try:
        result = reconstruction.reconstruct(bframes, survey.load_frames(d), s)
        control = reconstruction.split_half_control(bframes, s)
        sig = reconstruction.significance(result, control) if control else float("nan")
        name = f"{row['position']}-dac{s.dac}-st{s.settle_ms}-{row['run_id'][9:15]}"
        reconstruction.save_reconstruction(
            result, s, diff_dir / f"{name}.png", diff_dir / f"{name}.npz",
            title=f"{row['run_id']} minus {bd.name}", control=control)
        print("diff", name, f"peak {result.peak_value:+.3g} at {result.peak_angle_deg:.0f} deg, {sig:.1f}x noise", flush=True)
    except Exception as exc:  # noqa: BLE001
        print("diff failed", row["run_id"], type(exc).__name__, exc, flush=True)
print("WROTE", OUT, flush=True)
