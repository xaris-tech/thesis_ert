"""Score every candidate image metric on the 2026-10-22 saline position series.

For each run (difference vs empty-last 211625, and absolute E2-excluded) and each
reference (sharp mask, blurred mask, same-solver physics template) compute SSIM, NCC,
Dice, PSNR, MSE, MAE, lobe-centroid angle/position error and GREIT-style figures of
merit. Controls: no-target images (empty-first 134226 difference, split-half of the
reference, and both empty-tank absolute solves) scored against EVERY position's
reference, so each metric gets a null distribution. Separation = AUC (probability a
target run scores better than a control against the same reference) and a
standardised gap (mean difference / pooled SD); repeatability = SD across the three
repeats of each position. See docs/research-image-metrics-2026-10-22.md.

    .\\.venv\\Scripts\\python.exe exports\\position-series-20261022-contact-sheet\\metrics.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, r"D:\Here\asd")
import numpy as np
from scipy import ndimage

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as u
from tree_ert import reconstruction, survey, ssim
from tree_ert.settings import UiSettings
from verify_device import physics_template

ROOT = Path(r"D:\Here\asd\scans\runs")
OUT = Path(__file__).resolve().parent
REF = "20261022-211625-saline-pos-empty-last"
SKIP = {"20261022-212425-saline-pos-empty-last"}  # interrupted
s = UiSettings(port="x", pattern="adjacent", current_range="high", dac=400, settle_ms=10, samples=16)
protocol, _ = u.protocol_and_command("adjacent")
mesh, solver = base.create_solver(protocol)
N = ssim.GRID
xx, yy, inside = ssim.grid_coordinates(N)
ref_frames = survey.load_frames(ROOT / REF)
split = reconstruction.split_half_control(ref_frames, s)

runs = []
for run in sorted(ROOT.glob("20261022-*-saline-pos-*")):
    if run.name < "20261022-134226" or run.name in SKIP:
        continue
    pos = json.loads((run / "conditions.json").read_text(encoding="utf-8"))["conditions"]["extra"]["position"]
    runs.append((run, pos))

positions = [f"e{n}" for n in range(1, 13)] + ["centre"]
refs = {}
for p in positions:
    blocks = ssim.blocks_for(ssim.parse_target(f"wood at {p}"), mesh)
    mask = ssim.block_mask(blocks, N)
    refs[p] = dict(blocks=blocks, mask=mask, blurred=ssim.blur(mask, ssim.PSF_SIGMA, N),
                   physics=physics_template(blocks, mesh, solver), region=ssim.score_region(mask, N))


def psnr(mse):
    return float(10 * np.log10(1.0 / mse)) if mse > 0 else float("inf")


def greit(raw_grid, img, block):
    """GREIT-style figures of merit (Adler et al. 2009), adapted to the resistive lobe."""
    raw = np.nan_to_num(raw_grid)
    amp = float(np.clip(-raw, 0, None)[inside].sum() / inside.sum())   # AR: mean resistive amplitude
    hm = img >= 0.5                                                     # 1/2-max set (img is /peak)
    lab, _ = ndimage.label(hm)
    pk = np.unravel_index(int(np.argmax(img)), img.shape)
    lobe = (lab == lab[pk]) if lab[pk] else hm
    area = int(lobe.sum())
    res = float(np.sqrt(area / inside.sum()))                           # RES
    cx, cy = xx[lobe].mean(), yy[lobe].mean()
    pe = float(np.hypot(block.x, block.y) - np.hypot(cx, cy))           # PE (radial, signed)
    loc = float(np.hypot(cx - block.x, cy - block.y))                   # 2-D centroid error
    rad = np.sqrt(area / np.pi) * 2 / N
    circ = np.hypot(xx - cx, yy - cy) <= rad
    sd = float((lobe & ~circ).sum() / max(area, 1))                     # SD
    total = np.abs(raw)[inside].sum()
    rng = float(np.clip(raw, 0, None)[inside].sum() / total) if total else 0.0  # RNG: opposite-sign share
    return amp, res, pe, loc, sd, rng


def score(raw_vals, p, kind, run_id, role, extra):
    g = ssim.rasterise(raw_vals, mesh, N)
    img = ssim.resistive_image(g)
    R = refs[p]
    row = dict(kind=kind, run_id=run_id, role=role, position=p, **extra)
    for name in ("mask", "blurred", "physics"):
        t = R[name]
        reg = R["region"] if name != "physics" else inside
        mse = float(np.mean((img - t)[reg] ** 2))
        row[f"ssim_{name}"] = ssim.ssim(img, t, reg)
        row[f"ncc_{name}"] = ssim.ncc(img, t, reg)
        row[f"dice_{name}"] = ssim.dice(img, t, reg)
        row[f"mse_{name}"] = mse
        row[f"mae_{name}"] = float(np.mean(np.abs(img - t)[reg]))
        row[f"psnr_{name}"] = psnr(mse)
    b = ssim.score_blocks(g, R["blocks"], N)[0]
    row["angle_err_abs"] = abs(b.centroid_angle_error_deg) if b.centroid_angle_error_deg is not None else np.nan
    row["peak_angle_err_abs"] = abs(b.angle_error_deg) if b.angle_error_deg is not None else np.nan
    amp, res, pe, loc, sd, rng = greit(g, img, R["blocks"][0])
    row.update(greit_amp=amp, greit_res=res, greit_pe=pe, pos_err=loc, greit_sd=sd, greit_rng=rng,
               trough=float(-np.nanmin(raw_vals)))
    return row


rows = []
for run, pos in runs:
    d = np.load(run / "absolute.npz")
    absv = np.log10(d["sigma"] / d["sigma0"])
    passed = bool(d["passed"])
    if pos.startswith("empty"):
        if run.name != REF:
            diff = reconstruction.reconstruct(ref_frames, survey.load_frames(run), s)
            sig = reconstruction.significance(diff, split)
            for p in positions:
                rows.append(score(diff.values, p, "difference", run.name, "control", dict(source=pos, significance=sig)))
        for p in positions:
            rows.append(score(absv, p, "absolute", run.name, "control",
                              dict(source=pos, significance=float(d["significance"]), passed=passed)))
        continue
    diff = reconstruction.reconstruct(ref_frames, survey.load_frames(run), s)
    sig = reconstruction.significance(diff, split)
    rows.append(score(diff.values, pos, "difference", run.name, "target", dict(source=pos, significance=sig)))
    rows.append(score(absv, pos, "absolute", run.name, "target",
                      dict(source=pos, significance=float(d["significance"]), passed=passed)))
for p in positions:
    rows.append(score(split.values, p, "difference", REF + "/split-half", "control",
                      dict(source="split-half", significance=1.0)))

lead = ("kind", "run_id", "role", "position", "source")
keys = list(lead) + sorted({k for r in rows for k in r} - set(lead))
with (OUT / "metrics.csv").open("w", newline="", encoding="utf-8") as h:
    w = csv.DictWriter(h, keys)
    w.writeheader()
    w.writerows(rows)

# Direction: +1 higher is better, -1 lower is better, 0 = |value| lower is better.
METRICS = {}
for n in ("mask", "blurred", "physics"):
    METRICS.update({f"ssim_{n}": 1, f"ncc_{n}": 1, f"dice_{n}": 1, f"psnr_{n}": 1, f"mse_{n}": -1, f"mae_{n}": -1})
METRICS.update(angle_err_abs=-1, peak_angle_err_abs=-1, pos_err=-1, greit_amp=1, trough=1, significance=1,
               greit_res=-1, greit_sd=-1, greit_rng=-1, greit_pe=0)
summary = []
for kind in ("difference", "absolute"):
    T = [r for r in rows if r["kind"] == kind and r["role"] == "target"]
    C = [r for r in rows if r["kind"] == kind and r["role"] == "control"]
    for m, sgn in METRICS.items():
        f = (lambda r, m=m: abs(r[m])) if sgn == 0 else (lambda r, m=m: r[m])
        sgn = sgn or -1
        wins = ties = n = 0
        for t in T:
            for c in C:
                if c["position"] != t["position"]:
                    continue
                a, b = sgn * f(t), sgn * f(c)
                if not (np.isfinite(a) and np.isfinite(b)):
                    continue
                n += 1
                wins += a > b
                ties += a == b
        auc = (wins + 0.5 * ties) / n if n else np.nan
        tv = np.array([f(t) for t in T], float)
        cv = np.array([f(c) for c in C], float)
        tv, cv = tv[np.isfinite(tv)], cv[np.isfinite(cv)]
        pooled = np.sqrt((tv.var(ddof=1) + cv.var(ddof=1)) / 2) if len(tv) > 1 and len(cv) > 1 else np.nan
        gap = sgn * (tv.mean() - cv.mean()) / pooled if pooled else np.nan
        rep = []
        for p in positions:
            v = [x for x in (f(t) for t in T if t["position"] == p) if np.isfinite(x)]
            if len(v) > 1:
                rep.append(np.std(v, ddof=1))
        summary.append(dict(kind=kind, metric=m, target_median=float(np.median(tv)),
                            control_median=float(np.median(cv)), auc=auc, std_gap=gap,
                            repeat_sd_median=float(np.median(rep)) if rep else np.nan,
                            n_target=len(tv), n_control=len(cv)))
with (OUT / "metrics_summary.csv").open("w", newline="", encoding="utf-8") as h:
    w = csv.DictWriter(h, list(summary[0]))
    w.writeheader()
    w.writerows(summary)
for r in sorted(summary, key=lambda r: (r["kind"], -r["auc"])):
    print(f"{r['kind']:10s} {r['metric']:20s} T={r['target_median']:8.3f} C={r['control_median']:8.3f} "
          f"AUC={r['auc']:.3f} gap={r['std_gap']:6.2f} repSD={r['repeat_sd_median']:.3f} n={r['n_target']}/{r['n_control']}")
