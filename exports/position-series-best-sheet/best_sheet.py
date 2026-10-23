"""Best absolute and best difference image for every saline position, 2026-10-22/23.

For each position, every run is scored by block contrast: the deepest dip
within 20 deg of each block (r > 0.4) divided by the deepest dip in the rest of
the tank (more than 45 deg from any block, r > 0.4). For the centre, the dip
inside r < 0.3 over the deepest dip at r > 0.5. Above 1 means the block is the
deepest feature. A run's score is its weakest block, so a pair counts only as
well as the block it shows worst.

Absolute: both the all-electrode solve and the E2-excluded solve are scored;
only solves that pass the ADR-0041 gates are eligible. Difference: against the
quietest closing empty-tank run of the same day (smallest split-half control).
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, r"D:\Here\asd")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as u
from tree_ert import absolute, reconstruction, survey
from tree_ert.settings import UiSettings

ROOT = Path(r"D:\Here\asd\scans\runs")
OUT = Path(__file__).resolve().parent
# Superseded or invalid runs: miswired leads, interrupted, 10-frame repeats of e1/e2.
SKIP_BEFORE = {"20261022": "20261022-132441"}
SKIP = {"20261022-212425-saline-pos-empty-last"}

s = UiSettings(port="x", pattern="adjacent", current_range="high", dac=400, settle_ms=10, samples=16)
sx = replace(s, absolute_exclude_electrodes=(2,))
protocol, _ = u.protocol_and_command("adjacent")
mesh, _ = base.create_solver(protocol)
tri, pts = mesh.element, mesh.node[:, :2]
el = pts[mesh.el_pos]
centres = np.mean(mesh.node[mesh.element], axis=1)
ang = np.degrees(np.arctan2(centres[:, 1], centres[:, 0])) % 360
rad = np.hypot(centres[:, 0], centres[:, 1])


def block_angles(pos):
    return [(7 - int(x[1:])) * 30 % 360 for x in pos.split("+")] if pos.startswith("e") else []


def contrast(values, pos):
    if pos == "centre":
        return values[rad < 0.3].min() / values[rad > 0.5].min()
    blocks = block_angles(pos)
    off = lambda b: np.abs((ang - b + 180) % 360 - 180)
    background = np.ones(len(values), bool)
    for b in blocks:
        background &= off(b) > 45
    floor = values[background & (rad > 0.4)].min()
    return min(values[(off(b) <= 20) & (rad > 0.4)].min() / floor for b in blocks)


def runs_by_position():
    found = {}
    for run in sorted(ROOT.glob("2026102[23]-*-saline-pos-*")):
        day = run.name[:8]
        if run.name in SKIP or run.name < SKIP_BEFORE.get(day, ""):
            continue
        cond = json.loads((run / "conditions.json").read_text(encoding="utf-8"))
        pos = cond["conditions"]["extra"]["position"]
        if pos in ("e1", "e2") and cond["settings"].get("frames") != 20:
            continue
        found.setdefault(pos, []).append(run)
    return found


def quietest_empty(day):
    best = None
    for run in sorted(ROOT.glob(f"{day}-*-saline-pos-empty-last")):
        if run.name in SKIP:
            continue
        frames = survey.load_frames(run)
        control = reconstruction.split_half_control(frames, s)
        if best is None or control.limit < best[2].limit:
            best = (run, frames, control)
    return best


refs = {day: quietest_empty(day) for day in ("20261022", "20261023")}
order = [f"e{n}" for n in range(1, 13)] + [f"e{n}+e{n + 6}" for n in range(1, 7)] + ["centre"]
rows, table = [], []
for pos, runs in ((p, runs_by_position().get(p, [])) for p in order):
    if not runs:
        continue
    best_abs = best_diff = None
    for run in runs:
        frames = survey.load_frames(run)
        for label, settings in (("all electrodes", s), ("E2 excluded", sx)):
            result, _, report = absolute.evaluate(frames, settings)
            if result is None or not report.passed:
                continue
            score = contrast(np.log(result.sigma / result.sigma0), pos)
            if best_abs is None or score > best_abs[0]:
                best_abs = (score, run, label, result, report)
        ref_run, ref_frames, control = refs[run.name[:8]]
        diff = reconstruction.reconstruct(ref_frames, frames, s)
        score = contrast(diff.values, pos)
        if best_diff is None or score > best_diff[0]:
            best_diff = (score, run, diff, reconstruction.significance(diff, control), ref_run)
    rows.append((pos, best_abs, best_diff))
    table.append({
        "position": pos,
        "absolute_run": best_abs[1].name if best_abs else "",
        "absolute_solve": best_abs[2] if best_abs else "none passed",
        "absolute_contrast": round(best_abs[0], 2) if best_abs else "",
        "absolute_misfit_percent": round(best_abs[3].residual_percent, 1) if best_abs else "",
        "difference_run": best_diff[1].name,
        "difference_reference": best_diff[4].name,
        "difference_contrast": round(best_diff[0], 2),
        "difference_significance": round(best_diff[3], 1),
    })
    print(table[-1], flush=True)


def mark(ax, pos):
    ax.plot(el[:, 0], el[:, 1], "k.", ms=3)
    for i in range(12):
        ax.text(el[i, 0] * 1.17, el[i, 1] * 1.17, f"E{i + 1}", fontsize=6, ha="center", va="center")
    for b in block_angles(pos):
        a = np.radians(b)
        ax.plot(0.75 * np.cos(a), 0.75 * np.sin(a), "kx", ms=9, mew=2)
    if pos == "centre":
        ax.plot(0, 0, "kx", ms=9, mew=2)


cols = 4
pairs_per_row = cols // 2
nrows = -(-len(rows) // pairs_per_row)
fig, axes = plt.subplots(nrows, cols, figsize=(4 * cols, 4.1 * nrows))
for ax in axes.ravel():
    ax.set_aspect("equal")
    ax.axis("off")
for i, (pos, best_abs, best_diff) in enumerate(rows):
    r, c0 = divmod(i, pairs_per_row)
    a_ax, d_ax = axes[r, 2 * c0], axes[r, 2 * c0 + 1]
    if best_abs:
        score, run, label, result, report = best_abs
        v = np.log10(result.sigma / result.sigma0)
        lim = max(float(np.percentile(np.abs(v), 98)), 1e-6)
        a_ax.tripcolor(pts[:, 0], pts[:, 1], tri, facecolors=v, cmap="RdBu_r", vmin=-lim, vmax=lim)
        a_ax.set_title(f"{pos.upper()}  absolute ({label})\n{run.name[:15]}  contrast {score:.2f}  "
                       f"misfit {result.residual_percent:.1f}%", fontsize=8)
    else:
        a_ax.text(0, 0, f"{pos.upper()}\nno absolute solve passed", ha="center", va="center", fontsize=9)
    mark(a_ax, pos)
    score, run, diff, sig, ref = best_diff
    lim = max(float(np.max(np.abs(diff.values))), 1e-6)
    d_ax.tripcolor(pts[:, 0], pts[:, 1], tri, facecolors=diff.values, cmap="RdBu_r", vmin=-lim, vmax=lim)
    d_ax.set_title(f"{pos.upper()}  difference vs {ref.name[9:15]}\n{run.name[:15]}  contrast {score:.2f}  "
                   f"significance {sig:.1f}", fontsize=8)
    mark(d_ax, pos)

fig.suptitle("Saline position series, 2026-10-22 (single blocks, centre) and 2026-10-23 (pairs): best run per position\n"
             "Each pair of panels: absolute (log10 sigma/sigma0) | difference vs that day's quietest closing empty tank. "
             "Blue = less conductive; x = block. Contrast = weakest block's dip / deepest background dip (>1 = block is deepest).",
             fontsize=10)
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(OUT / "best_sheet.png", dpi=110)
with (OUT / "best_sheet.csv").open("w", encoding="utf-8") as handle:
    handle.write(",".join(table[0]) + "\n")
    for row in table:
        handle.write(",".join(str(v) for v in row.values()) + "\n")
print(OUT / "best_sheet.png")
