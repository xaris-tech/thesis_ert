"""Difference images: disc-01 / disc-05 runs against the intact disc-02 at matching settings."""
import csv
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, r"D:\Here\asd")
from tree_ert import reconstruction, survey  # noqa: E402
from tree_ert.settings import settings_from_dict  # noqa: E402

RUNS = Path(r"D:\Here\asd\scans\runs")
OUT = Path(r"D:\Here\asd\exports\disc-holes-vs-disc-02-exclE1E2")
EXCL = (1, 2)
from dataclasses import replace  # noqa: E402
from tree_ert import absolute  # noqa: E402
OUT.mkdir(parents=True, exist_ok=True)
KEY = ("dac", "settle_ms", "samples")
TARGETS = [  # (name, glob, expected angle of the defect, sector half-width)
    ("disc-01", "20261014-1*disc-01-matrix*", 45.0, 45.0),   # holes near E4-E7: 0-90 deg
    ("disc-05", "20261014-2*disc-05-adjacent*", 165.0, 15.0),  # hole between E1 and E2
]


def settings_of(d):
    return json.load(open(d / "conditions.json"))["settings"]


def angle_off(found, centre, half):
    err = (found - centre + 180.0) % 360.0 - 180.0
    return 0.0 if abs(err) <= half else (abs(err) - half) * (1 if err > 0 else -1)


baselines = {}
for d in sorted(RUNS.glob("2026101[6-9]-*disc-02-matrix*")):
    if not (d / "summary.txt").exists():
        continue
    s = settings_of(d)
    baselines[tuple(s[k] for k in KEY)] = d  # latest run at each setting (after the E2 fix where one exists)
print("baselines:", {k: v.name for k, v in baselines.items()}, flush=True)

rows = []
for name, pattern, centre, half in TARGETS:
    for d in sorted(RUNS.glob(pattern)):
        if not (d / "summary.txt").exists():
            continue
        ts = settings_of(d)
        key = tuple(ts[k] for k in KEY)
        if key not in baselines:
            print(name, d.name, "no disc-02 run at", key, flush=True)
            continue
        b = baselines[key]
        bs = settings_of(b)
        s = settings_from_dict(bs)
        bframes = absolute.exclude_electrodes(survey.load_frames(b), EXCL)
        tframes = absolute.exclude_electrodes(survey.load_frames(d), EXCL)
        sx = replace(s, absolute_exclude_electrodes=EXCL)
        res, noise, rep = absolute.evaluate(survey.load_frames(d), sx)
        astem = f"{name}-ABS-dac{key[0]}-st{key[1]}-n{key[2]}-{d.name[9:15]}"
        absolute.save_absolute(absolute.Attempt(sx, survey.load_frames(d), res, noise, rep),
            OUT / f"{astem}.png", OUT / f"{astem}.npz",
            title=f"{d.name} (absolute, E1/E2 excluded)", thickness_mm=None)
        abs_trough = res.trough_text()
        abs_gate = "PASS" if rep.passed else "; ".join(rep.reasons)
        try:
            result = reconstruction.reconstruct(bframes, tframes, s,
                                                baseline_settings=bs, target_settings=ts)
            control = reconstruction.split_half_control(bframes, s)
            sig = reconstruction.significance(result, control) if control else float("nan")
        except Exception as exc:  # noqa: BLE001
            print(name, d.name, "failed:", type(exc).__name__, exc, flush=True)
            continue
        stem = f"{name}-dac{key[0]}-st{key[1]}-n{key[2]}-{d.name[9:15]}"
        reconstruction.save_reconstruction(
            result, s, OUT / f"{stem}.png", OUT / f"{stem}.npz",
            title=f"{d.name} minus intact {b.name}",
            subtitle="CROSS-SPECIMEN BASELINE; E1/E2 records excluded from both runs (ADR-0064)",
            control=control)
        off = angle_off(result.peak_angle_deg, centre, half)
        rows.append({
            "specimen": name, "target_run": d.name, "baseline_run": b.name,
            "dac": key[0], "settle_ms": key[1], "samples": key[2],
            "peak_value": round(result.peak_value, 4),
            "peak_angle_deg": round(result.peak_angle_deg, 1),
            "defect_sector": f"{centre - half:.0f}-{centre + half:.0f}",
            "deg_outside_sector": round(off, 1),
            "significance": round(sig, 2),
            "absolute_gate": abs_gate, "absolute_trough": abs_trough,
        })
        print(name, stem, f"peak {result.peak_value:+.3g} at {result.peak_angle_deg:.0f} deg,"
              f" {sig:.1f}x noise, {off:+.0f} deg outside defect sector | ABS {abs_gate[:30]} {abs_trough}", flush=True)

if rows:
    with open(OUT / "summary.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
print("COMPARE DONE", OUT, flush=True)
