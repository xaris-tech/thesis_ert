"""Contact sheet: absolute (E2 excluded) and difference (vs closing empty tank) for every run."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"D:\Here\asd")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as u
import position_series as ps
from tree_ert import reconstruction, survey
from tree_ert.settings import UiSettings

ROOT = Path(r"D:\Here\asd\scans\runs")
OUT = Path(r"D:\Here\asd\exports\position-series-20261022-contact-sheet")
OUT.mkdir(parents=True, exist_ok=True)
REF = "20261022-211625-saline-pos-empty-last"
SKIP = {"20261022-212425-saline-pos-empty-last"}  # interrupted

s = UiSettings(port="x", pattern="adjacent", current_range="high", dac=400, settle_ms=10, samples=16)
protocol, _ = u.protocol_and_command("adjacent")
mesh, _ = base.create_solver(protocol)
tri, pts = mesh.element, mesh.node[:, :2]
el = pts[mesh.el_pos]
ref_frames = survey.load_frames(ROOT / REF)
control = reconstruction.split_half_control(ref_frames, s)

runs = sorted(p for p in ROOT.glob("20261022-*-saline-pos-*")
              if p.name >= "20261022-132441" and p.name not in SKIP)
rows = {}
for run in runs:
    cond = json.loads((run / "conditions.json").read_text(encoding="utf-8"))
    pos = cond["conditions"]["extra"]["position"]
    nframes = cond["settings"].get("frames")
    key = f"{pos} ({nframes} fr)" if pos in ("e1", "e2") else pos
    rows.setdefault(key, []).append(run)

order = ["empty-first", "e1 (10 fr)", "e1 (20 fr)", "e2 (10 fr)", "e2 (20 fr)"] + \
        [f"e{n}" for n in range(3, 13)] + ["centre", "empty-last"]
order = [k for k in order if k in rows]
expected = {f"e{n}": (7 - n) * 30 % 360 for n in range(1, 13)}

fig, axes = plt.subplots(len(order), 6, figsize=(15, 2.6 * len(order)))
ABS_SCALE, DIFF_SCALE = 0.35, 0.3
summary = []
for r, key in enumerate(order):
    pos = key.split(" ")[0]
    for c in range(3):
        for half, ax in ((0, axes[r, c]), (1, axes[r, c + 3])):
            ax.set_aspect("equal"); ax.axis("off")
            if c >= len(rows[key]):
                continue
            run = rows[key][c]
            if half == 0:
                d = np.load(run / "absolute.npz")
                v = np.log10(d["sigma"] / d["sigma0"])
                ax.tripcolor(pts[:, 0], pts[:, 1], tri, facecolors=v, cmap="RdBu_r", vmin=-ABS_SCALE, vmax=ABS_SCALE)
                gate = "PASS" if float(d["significance"]) >= 2.0 and float(d["residual_percent"]) <= 15 else "refused"
                ang = float(d["trough_angle_deg"]) if np.isfinite(d["trough_angle_deg"]) else float("nan")
                label = f"abs {gate}\ntrough {ang:.0f}°"
            else:
                if run.name == REF:
                    ax.text(0, 0, "reference", ha="center", va="center", fontsize=8)
                    continue
                diff = reconstruction.reconstruct(ref_frames, survey.load_frames(run), s)
                sig = reconstruction.significance(diff, control)
                ang = ps.resistive_trough_deg(diff.values, mesh)
                ax.tripcolor(pts[:, 0], pts[:, 1], tri, facecolors=diff.values, cmap="RdBu_r", vmin=-DIFF_SCALE, vmax=DIFF_SCALE)
                label = f"diff sig {sig:.1f}\ntrough {ang:.0f}°"
                summary.append((key, run.name, ang, sig, diff.limit))
            ax.plot(el[:, 0], el[:, 1], "k.", ms=3)
            ax.text(el[0, 0] * 1.18, el[0, 1] * 1.18, "E1", fontsize=6, ha="center", va="center")
            ax.text(el[1, 0] * 1.18, el[1, 1] * 1.18, "E2", fontsize=6, ha="center", va="center", color="grey")
            if pos in expected:
                a = np.radians(expected[pos]); ax.plot(0.75 * np.cos(a), 0.75 * np.sin(a), "kx", ms=8, mew=2)
            elif pos == "centre":
                ax.plot(0, 0, "kx", ms=8, mew=2)
            ax.set_title(f"{run.name[9:15]}  {label}", fontsize=7)
    axes[r, 0].text(-1.45, 0, key, rotation=90, va="center", ha="center", fontsize=10, weight="bold")

fig.suptitle("Saline position series 2026-10-22 — left: absolute (E2 excluded, log10 σ/σ0, ±0.35); "
             "right: difference vs closing empty tank 211625 (±0.3)\n"
             "x = block position; blue = less conductive. Drift (opening vs closing empty tank) peak 0.090; "
             "blocks ≈0.23–0.29", fontsize=10)
fig.tight_layout(rect=(0.02, 0, 1, 0.97))
fig.savefig(OUT / "contact_sheet.png", dpi=110)
with (OUT / "difference_vs_empty_last.csv").open("w", encoding="utf-8") as h:
    h.write("position,run_id,trough_deg,significance,peak\n")
    for k, rid, ang, sig, lim in summary:
        h.write(f"{k},{rid},{ang:.1f},{sig:.2f},{lim:.4f}\n")
print(OUT / "contact_sheet.png", len(summary))
