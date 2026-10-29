import sys, json, csv, re
sys.path.insert(0, "D:/Here/asd")
import numpy as np
from pathlib import Path
import ssim_eval, phase3a_reconstruct as base, phase3a_unified_reconstruct as unified
from tree_ert import ssim
from tree_ert.reconstruction import reconstruct
from tree_ert.survey import load_frames
RUNS = Path("D:/Here/asd/scans/runs")
gt = json.load(open("ground_truth.json"))
rmap = list(csv.DictReader(open("D:/Here/asd/saline/run_map.csv")))
def epos(angle, el_ang):
    w = lambda x: (x + 180) % 360 - 180
    for k in range(12):
        d = w(el_ang[(k+1)%12]-el_ang[k]); t = w(angle-el_ang[k]) / d
        if 0 <= t <= 1: return (k + t) % 12 + 1
def lobes(values, mesh, n):
    grid = ssim.rasterise(values, mesh)
    res = np.clip(np.nan_to_num(-grid, nan=0.0), 0, None)
    xx, yy, inside = ssim.grid_coordinates()
    ang = np.degrees(np.arctan2(yy, xx)) % 360
    out = []; region = inside.copy()
    for _ in range(n):
        c = ssim._lobe_centroid(res, region, region)
        if c is None: break
        out.append(c)
        region &= np.abs(ssim._angle_diff(ang, c[0])) > 60
    return out
cache = {}
results = []
for row in rmap:
    if not row["photo"]: continue
    for rid in (row["run_1"], row["run_2"], row["run_3"]):
        d = RUNS / rid; bid = (d/"reconstruction.txt").read_text(encoding="utf-8").splitlines()[0].split()[1]
        run = json.loads((d/"conditions.json").read_text(encoding="utf-8"))
        st = ssim_eval._recorded_settings(run["settings"])
        res = reconstruct(load_frames(RUNS/bid), load_frames(d), st)
        proto, _ = unified.protocol_and_command(st.pattern)
        mesh, _ = base.create_solver(proto)
        el = [float(np.degrees(np.arctan2(mesh.node[i][1], mesh.node[i][0])) % 360) for i in mesh.el_pos]
        n = 2 if "&" in row["photo"] else 1
        found = [(round(epos(a, el), 2), round(r, 2)) for a, r in lobes(res.values, mesh, n)]
        results.append(dict(photo=row["photo"], run=rid, baseline=bid, lobes=found))
        print(row["photo"], rid[:15], bid[:15], found, flush=True)
json.dump(results, open("recon_lobes.json", "w"), indent=1)
