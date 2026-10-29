import sys, json, csv; sys.path.insert(0,"D:/Here/asd")
import numpy as np
from pathlib import Path
import ssim_eval, phase3a_reconstruct as base
from tree_ert import ssim
from tree_ert.reconstruction import reconstruct
from tree_ert.survey import load_frames
from verify_device import BLOCK_CONTRAST
R=[Path("D:/Here/asd/scans/runs"),Path("D:/Here/asd/ssim/saline-tank-2026-10-02/runs")]
find=lambda r:next(p/r for p in R if (p/r).is_dir())
W=lambda x:(x+180)%360-180
RING=ssim.ELECTRODE_RING_RADIUS_MM
mesh,solver=base.create_solver(base.build_adjacent_protocol())
el=[np.degrees(np.arctan2(mesh.node[i][1],mesh.node[i][0])) for i in mesh.el_pos]
cent=np.mean(mesh.node[mesh.element],axis=1)[:,:2]; _,_,inside=ssim.grid_coordinates()
homog=solver.fwd.solve_eit(perm=1.0)
def template(blocks,t_mm,r_mm):
    tot=np.zeros(len(mesh.element))
    for x,y in blocks:
        rr=np.hypot(x,y); ur=np.array([x,y])/rr if rr>0 else np.array([1.0,0]); ut=np.array([-ur[1],ur[0]])
        dx,dy=cent[:,0]-x,cent[:,1]-y
        ins=(np.abs(dx*ur[0]+dy*ur[1])<=r_mm/2/RING)&(np.abs(dx*ut[0]+dy*ut[1])<=t_mm/2/RING)
        p=np.ones(len(mesh.element)); p[ins]=BLOCK_CONTRAST
        tot+=base.reconstruct_difference(homog,solver.fwd.solve_eit(perm=p),solver,None)
    return ssim.resistive_image(ssim.rasterise(tot,mesh))
def xy(e,r):
    if e is None: return (0.0,0.0)
    k=int(e)-1; t=e-int(e); a=np.radians(el[k%12]+t*W(el[(k+1)%12]-el[k%12])); return (r*np.cos(a),r*np.sin(a))
gt=json.load(open("ground_truth.json")); truth={}
for g in gt: truth.setdefault(g["photo"],[]).append((None if g["target"]=="centre" else g["electrode_pos"],g["radius"],None if g["target"]=="centre" else int(g["target"][1:])))
truth["wood8"]=[(7.97,0.648,8)]; truth["wood5&11"]=[(4.88,0.691,5),(10.85,0.655,11)]
runs={r["photo"]:r["run_1"] for r in csv.DictReader(open("D:/Here/asd/saline/run_map.csv")) if r["photo"]}
runs["wood8"]="20261014-191430-saline-e8-adjacent-dac400-st10-n16"; base_of={"wood8":"20261014-200326-saline-empty-adjacent-dac400-st10-n16"}
SIZES={"23x22 (code)":(23,22),"30x22":(30,22),"22x30":(22,30),"23x30":(23,30),"30x23":(30,23)}  # tangential x radial
NOM=ssim.NEAR_RADIUS_MM/RING
out=[]
for photo,blk in truth.items():
    rid=runs[photo]; d=find(rid); bid=base_of.get(photo) or (d/"reconstruction.txt").read_text(encoding="utf-8").split()[1]
    st=ssim_eval._recorded_settings(json.loads((d/"conditions.json").read_text(encoding="utf-8"))["settings"])
    img=ssim.resistive_image(ssim.rasterise(reconstruct(load_frames(find(bid)),load_frames(d),st).values,mesh))
    ctrl=None
    if (d/"reconstruction.npz").is_file():
        with np.load(d/"reconstruction.npz",allow_pickle=True) as h:
            if "control_values" in h.files: ctrl=ssim.resistive_image(ssim.rasterise(h["control_values"],mesh))
    for pos in ("measured","nominal"):
        pts=[xy(e, r if pos=="measured" else (0 if k is None else NOM)) for e,r,k in blk] if pos=="measured" else [xy(None if k is None else float(k),0 if k is None else NOM) for e,r,k in blk]
        for name,(t,r) in SIZES.items():
            tm=template(pts,t,r)
            out.append(dict(photo=photo,run=rid,position=pos,size_txr=name,ncc=round(ssim.ncc(img,tm,inside),3),
                            control=None if ctrl is None else round(ssim.ncc(ctrl,tm,inside),3)))
    best=max((o for o in out if o["photo"]==photo),key=lambda o:o["ncc"])
    print(photo, best["position"], best["size_txr"], best["ncc"], "| user orientation:",
          [ (o["position"],o["ncc"]) for o in out if o["photo"]==photo and o["size_txr"]==("30x22" if "&" in photo else "22x30")], flush=True)
with open("D:/Here/asd/saline/ncc_block_size.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
