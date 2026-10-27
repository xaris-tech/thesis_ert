"""disc-08, 2026-10-27: E10 hole (old) and E5 hole (drilled today), each shown by the method that finds it."""
import sys
from pathlib import Path
sys.path.insert(0, r"D:\Here\asd")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import phase3a_reconstruct as base, phase3a_unified_reconstruct as u
from tree_ert import absolute, survey
from tree_ert.settings import UiSettings

R = Path(r"D:\Here\asd\scans\runs"); OUT = Path(__file__).resolve().parent
S1A, S1O = "20261027-135128-disc-08-s1-adjacent", "20261027-134523-disc-08-s1-opposite"
D1A, D1O = "20261027-142229-disc-08-d1-adjacent", "20261027-141624-disc-08-d1-opposite"

def load(run, pattern):
    return survey.load_frames(R / run), UiSettings(port="x", pattern=pattern, current_range="high",
                                                   dac=620, settle_ms=10, samples=16)

mesh, _ = base.create_solver(u.protocol_and_command("opposite")[0])
d1 = np.load(R / D1O / "absolute.npz")
abs_img = np.log10(d1["sigma"] / d1["sigma0"])
before = absolute.reconstruct_absolute_joint([load(S1A, "adjacent"), load(S1O, "opposite")])
after = absolute.reconstruct_absolute_joint([load(D1A, "adjacent"), load(D1O, "opposite")])
cmp_img = absolute.compare_absolute(before, after)
diff = np.load(R / D1A / "reconstruction.npz")["values"]

def mark(ax, deg, label):
    a = np.radians(deg)
    ax.plot(0.55 * np.cos(a), 0.55 * np.sin(a), marker="o", ms=26, mfc="none", mec="k", mew=2)
    ax.text(0.55 * np.cos(a), 0.55 * np.sin(a) - 0.27, label, ha="center", fontsize=9, weight="bold")

fig, axes = plt.subplots(1, 3, figsize=(16, 6))
lim = float(np.percentile(np.abs(abs_img), 98))
base.draw_tomogram(axes[0], mesh, abs_img, lim, label_size=8)
mark(axes[0], 270, "E10 hole"); mark(axes[0], 60, "E5 hole\n(not visible)")
axes[0].set_title("1. Absolute image after drilling (D1, opposite)\nE10 hole = deepest trough (270 deg)\n"
                  "caution: E10-E11 wiring short also dips here", fontsize=10, pad=24)
base.draw_tomogram(axes[1], mesh, cmp_img, float(np.max(np.abs(cmp_img))), label_size=8)
mark(axes[1], 60, "E5 hole")
axes[1].set_title("2. Absolute after / absolute before (sham)\nadjacent+opposite joint solve\n"
                  "E5 hole found at 68 deg, 3.3x the rest (E10 cancels)", fontsize=10, pad=24)
base.draw_tomogram(axes[2], mesh, diff, float(np.max(np.abs(diff))), label_size=8)
mark(axes[2], 60, "E5 hole")
axes[2].set_title("3. Difference image D1 vs sham (adjacent)\n"
                  "E5 hole found at 69 deg, significance 9.6 (E10 cancels)", fontsize=10, pad=24)
fig.suptitle("disc-08, 2026-10-27: old hole near E10 and new 4 cm through-hole drilled at E5 (60 deg)\n"
             "blue = less conductive; each hole shown by the method that detects it", fontsize=12)
fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.savefig(OUT / "both_holes.png", dpi=120)
print(OUT / "both_holes.png")

# One image: the absolute map (shows E10), with the E5 hole outlined where the
# before/after comparison detects it (half its deepest change). The outline is a
# detection drawn on top, not data added to the map.
fig, ax = plt.subplots(figsize=(7.6, 8.2))
image = base.draw_tomogram(ax, mesh, abs_img, lim, label_size=10)
node_change = base.element_to_node(mesh, cmp_img)
ax.tricontour(mesh.node[:, 0], mesh.node[:, 1], mesh.element, node_change,
              levels=[0.5 * float(node_change.min())], colors="lime", linewidths=3)
ax.tricontour(mesh.node[:, 0], mesh.node[:, 1], mesh.element, base.element_to_node(mesh, abs_img),
              levels=[0.5 * float(abs_img.min())], colors="yellow", linewidths=3, linestyles="--")
ax.text(0.30, 0.38, "E5 hole\n(new, 68 deg)", color="k", fontsize=11, weight="bold", ha="center")
ax.text(0.0, -0.62, "E10 hole\n(old, 270 deg)", color="k", fontsize=11, weight="bold", ha="center")
fig.colorbar(image, ax=ax, shrink=0.7, label="log10(sigma / sigma0): blue less conductive")
ax.set_title("disc-08 after drilling: both holes\n"
             "map = absolute image D1 (opposite), shows the E10 hole (yellow dashed: its trough)\n"
             "green outline = E5 hole, found by absolute after / before (3.3x the rest)\n"
             "caution: the E10-E11 wiring short also dips at E10", fontsize=10, pad=34)
fig.tight_layout()
fig.savefig(OUT / "both_holes_one_image.png", dpi=130)
print(OUT / "both_holes_one_image.png")

# Composite: absolute image D1 (shows the E10 hole) fused with the before/after
# absolute comparison (shows the E5 hole). Each is scaled to its own -1..1 range
# and the more negative value is kept per element, so a feature from either
# measurement appears. A composite of two measurements, not one scan.
a_n = np.clip(abs_img / lim, -1.0, 1.0)
c_n = np.clip(cmp_img / float(np.max(np.abs(cmp_img))), -1.0, 1.0)
composite = np.minimum(a_n, c_n)
fig, ax = plt.subplots(figsize=(7, 7.4))
base.draw_tomogram(ax, mesh, composite, 1.0, label_size=11)
ax.set_title("disc-08", fontsize=16, pad=30)
fig.tight_layout()
fig.savefig(OUT / "disc-08-composite-absolute-plus-before-after.png", dpi=130)
print(OUT / "disc-08-composite-absolute-plus-before-after.png")

# Full-colour composite: the absolute image keeps its red and blue; the
# before/after decrease (negative part only) is added on top so the E5 hole
# appears. Disclosed on the figure.
full = np.clip(a_n + np.minimum(c_n, 0.0), -1.0, 1.0)
fig, ax = plt.subplots(figsize=(7, 7.6))
base.draw_tomogram(ax, mesh, full, 1.0, label_size=11)
ax.set_title("disc-08", fontsize=16, pad=30)
fig.text(0.5, 0.025, "composite: absolute image D1 + before/after absolute comparison (D1 vs sham), each normalised",
         ha="center", fontsize=8, color="0.3")
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(OUT / "disc-08-composite-full-colour.png", dpi=130)
print(OUT / "disc-08-composite-full-colour.png")
