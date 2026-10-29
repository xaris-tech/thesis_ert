import sys, json, csv; sys.path.insert(0,"D:/Here/asd")
import numpy as np
from pathlib import Path
import ssim_eval, phase3a_reconstruct as base, phase3a_unified_reconstruct as unified
from tree_ert import ssim
from tree_ert.reconstruction import reconstruct
from tree_ert.survey import load_frames
from verify_device import physics_template
R=[Path("D:/Here/asd/scans/runs"),Path("D:/Here/asd/ssim/saline-tank-2026-10-02/runs")]
find=lambda r:next(p/r for p in R if (p/r).is_dir())
W=lambda x:(x+180)%360-180
gt=json.load(open("ground_truth.json"))
truth={}
for g in gt:
    if g["target"]!="centre": truth.setdefault(g["photo"],[]).append((g["target"],g["electrode_pos"],g["radius"]))
    else: truth["center"]=[("centre",None,g["radius"])]
truth["wood8"]=[("E8",7.97,0.648)]; truth["wood5&11"]=[("E5",4.88,0.691),("E11",10.85,0.655)]
jobs=[]
for r in csv.DictReader(open("D:/Here/asd/saline/run_map.csv")):
    if r["photo"] and r["photo"] not in ("wood8","wood5&11"):
        d=find(r["run_1"]); jobs.append((r["photo"],r["run_1"],(d/"reconstruction.txt").read_text(encoding="utf-8").split()[1]))
for o in json.load(open("odd_scores.json")): jobs.append((o["photo"],o["run"],o["baseline"]))
mesh,solver=base.create_solver(base.build_adjacent_protocol())
el=[np.degrees(np.arctan2(mesh.node[i][1],mesh.node[i][0])) for i in mesh.el_pos]
_,_,inside=ssim.grid_coordinates()
out=[]
for photo,rid,bid in jobs:
    d,b=find(rid),find(bid)
    st=ssim_eval._recorded_settings(json.loads((d/"conditions.json").read_text(encoding="utf-8"))["settings"])
    assert st.pattern=="adjacent", st.pattern
    res=reconstruct(load_frames(b),load_frames(d),st)
    blocks=[]
    for lab,e,r in truth[photo]:
        if e is None: blocks.append(ssim.Block(lab,0.0,0.0)); continue
        k=int(e)-1; t=e-int(e); a=np.radians(el[k%12]+t*W(el[(k+1)%12]-el[k%12])); blocks.append(ssim.Block(lab,r*np.cos(a),r*np.sin(a)))
    nominal=ssim.blocks_for(ssim.parse_target(" and ".join("centre" if l=="centre" else "e"+l[1:] for l,_,_ in truth[photo]).join(["wood at ",""])),mesh)
    tmpl=physics_template(blocks,mesh,solver); tmpl_nom=physics_template(nominal,mesh,solver)
    mask=ssim.block_mask(blocks); reg=ssim.score_region(mask)
    img=ssim.resistive_image(ssim.rasterise(res.values,mesh))
    ctrl=None
    npz=d/"reconstruction.npz"
    if npz.is_file():
        with np.load(npz,allow_pickle=True) as h:
            if "control_values" in h.files: ctrl=ssim.resistive_image(ssim.rasterise(h["control_values"],mesh))
    row=dict(photo=photo,run=rid,
        ncc_mask_local=round(ssim.ncc(img,mask,reg),3),
        ncc_template_local=round(ssim.ncc(img,tmpl,reg),3),
        ncc_template_disc=round(ssim.ncc(img,tmpl,inside),3),
        ncc_template_disc_nominal=round(ssim.ncc(img,tmpl_nom,inside),3),
        ncc_mask_vs_template_disc=round(ssim.ncc(ssim.blur(mask),tmpl,inside),3),
        control_ncc_template_disc=None if ctrl is None else round(ssim.ncc(ctrl,tmpl,inside),3))
    out.append(row); print(json.dumps(row),flush=True)
with open("D:/Here/asd/saline/ncc_scores.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
