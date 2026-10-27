"""disc-08 drill test 2026-10-27: absolute images compared before (S1) and after (D1-D3), per pattern and joint (ADR-0078)."""
import json, sys
from pathlib import Path
sys.path.insert(0, r"D:\Here\asd")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import phase3a_reconstruct as base, phase3a_unified_reconstruct as u
from tree_ert import absolute, survey
from tree_ert.settings import UiSettings

R = Path(r"D:\Here\asd\scans\runs"); OUT = Path(__file__).resolve().parent
STEPS = {"S1": ("20261027-135128-disc-08-s1-adjacent", "20261027-134523-disc-08-s1-opposite"),
         "D1": ("20261027-142229-disc-08-d1-adjacent", "20261027-141624-disc-08-d1-opposite"),
         "D2": ("20261027-143459-disc-08-d2-adjacent", "20261027-142850-disc-08-d2-opposite"),
         "D3": ("20261027-144739-disc-08-d3-adjacent", "20261027-144140-disc-08-d3-opposite")}

def load(run):
    st = json.loads((R / run / "conditions.json").read_text())["settings"]
    return survey.load_frames(R / run), UiSettings(port="x", pattern=st["pattern"], current_range="high",
                                                   dac=st["dac"], settle_ms=st["settle_ms"], samples=st["samples"])

solves = {}
for step, (adj, opp) in STEPS.items():
    A, O = load(adj), load(opp)
    solves[step] = {"adjacent": absolute.reconstruct_absolute(*A), "opposite": absolute.reconstruct_absolute(*O),
                    "joint": absolute.reconstruct_absolute_joint([A, O])}
mesh, _ = base.create_solver(u.protocol_and_command("adjacent")[0])
c = np.mean(mesh.node[mesh.element], axis=1)
ang = np.degrees(np.arctan2(c[:, 1], c[:, 0])) % 360; rad = np.hypot(c[:, 0], c[:, 1])
fig, axes = plt.subplots(3, 3, figsize=(12, 12.5))
rows = ["D1", "D2", "D3"]
with (OUT / "compare_absolute.csv").open("w") as h:
    h.write("step,solve,trough_deg,hole60_vs_rest\n")
    for i, step in enumerate(rows):
        for j, name in enumerate(("adjacent", "opposite", "joint")):
            d = absolute.compare_absolute(solves["S1"][name], solves[step][name])
            off = np.abs((ang - 60 + 180) % 360 - 180)
            ratio = d[(off <= 30) & (rad > 0.3)].min() / d[(off > 60) & (rad > 0.3)].min()
            k = np.argmin(np.where(rad > 0.3, d, 9.0))
            base.draw_tomogram(axes[i, j], mesh, d, 0.35)
            axes[i, j].set_title(f"{step} vs S1, {name}\ntrough {ang[k]:.0f} deg, hole/rest {ratio:.2f}", fontsize=9)
            h.write(f"{step},{name},{ang[k]:.0f},{ratio:.2f}\n")
fig.suptitle("disc-08: absolute after / absolute before (sham S1), log ratio; blue = less conductive after.\n"
             "New hole drilled at E5 (60 deg). D2 opposite and D3 adjacent were disturbed runs.", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(OUT / "compare_absolute.png", dpi=100)
print((OUT / "compare_absolute.csv").read_text())
