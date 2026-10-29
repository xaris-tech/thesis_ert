import sys, json, csv; sys.path.insert(0,"D:/Here/asd")
import numpy as np
from pathlib import Path
import ssim_eval, phase3a_reconstruct as base
from tree_ert import ssim
from tree_ert.reconstruction import reconstruct, average_frame_vectors
from tree_ert.survey import load_frames
from verify_device import BLOCK_CONTRAST
R=[Path("D:/Here/asd/scans/runs"),Path("D:/Here/asd/ssim/saline-tank-2026-10-02/runs")]
find=lambda r:next(p/r for p in R if (p/r).is_dir())
W=lambda x:(x+180)%360-180
RING=50.0
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

import collections
idx=[r["run_id"] for r in csv.DictReader(open("D:/Here/asd/scans/index.csv",encoding="utf-8")) if "saline-pos" in r["run_id"] and r["run_id"]>="20261022"]
allruns=collections.defaultdict(list)
for r in idx: allruns[r.split("saline-pos-")[1]].append(r)
key=lambda p:{"center":"centre"}.get(p, "e"+p[4:].replace("&","-e"))
SIZES={"23x22":(23,22),"30x22":(30,22),"22x30":(22,30),"23x30":(23,30),"30x23":(30,23)}
NOM=ssim.NEAR_RADIUS_MM/ssim.ELECTRODE_RING_RADIUS_MM
extra={"wood8":[("20261014-191430-saline-e8-adjacent-dac400-st10-n16","20261014-200326-saline-empty-adjacent-dac400-st10-n16"),
                ("20261014-191843-saline-e8-adjacent-dac400-st10-n16","20261014-200739-saline-empty-adjacent-dac400-st10-n16"),
                ("20261014-192257-saline-e8-adjacent-dac400-st10-n16","20261014-201151-saline-empty-adjacent-dac400-st10-n16"),
                ("20261002-150425-ssim-saline","20261002-143242-ssim-saline")],
       "wood5&11":[("20261002-175516-ssim-saline","20261002-170541-ssim-saline")]}
tcache={}
out=[]
for photo,blk in truth.items():
    cand=[]
    for rid in allruns[key(photo)]:
        d=find(rid); cand.append((rid,(d/"reconstruction.txt").read_text(encoding="utf-8").split()[1]))
    cand+=extra.get(photo,[])
    spots={"measured":[xy(e,r) for e,r,k in blk],
           "assumed":[xy(None if k is None else float(k),0 if k is None else NOM) for e,r,k in blk],
           "photo angle + assumed radius":[xy(e,0 if k is None else NOM) for e,r,k in blk]}
    rows=[]
    for rid,bid in cand:
        d=find(rid)
        st=ssim_eval._recorded_settings(json.loads((d/"conditions.json").read_text(encoding="utf-8"))["settings"])
        if st.pattern!="adjacent": continue
        proto=base.build_adjacent_protocol()
        bv=average_frame_vectors(load_frames(find(bid)),proto,st); tv=average_frame_vectors(load_frames(d),proto,st)
        e2=np.array([(1 in proto.ex_mat[i]) or (1 in proto.meas_mat[i][j]) for i in range(12) for j in range(9)])
        miss=np.isnan(bv)|np.isnan(tv)|e2
        vals=base.reconstruct_difference(np.where(miss,0,bv),np.where(miss,0,tv),solver,dropped_indexes=[int(i) for i in np.flatnonzero(miss)])
        img=ssim.resistive_image(ssim.rasterise(np.asarray(vals,float),mesh))
        for sp,pts in spots.items():
            for nm,(t,r) in SIZES.items():
                kk=(photo,sp,nm)
                if kk not in tcache: tcache[kk]=template(pts,t,r)
                rows.append(dict(photo=photo,run=rid,baseline=bid,spot=sp,size=nm,ncc=round(ssim.ncc(img,tcache[kk],inside),3)))
    out+=rows
    b=max(rows,key=lambda o:o["ncc"])
    print(f"{photo:9s} best {b['ncc']:.3f} {b['run'][:15]} {b['spot']} {b['size']}  (runs tried {len(cand)})",flush=True)
with open("D:/Here/asd/saline/ncc_ring50_search_e2_excluded.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
