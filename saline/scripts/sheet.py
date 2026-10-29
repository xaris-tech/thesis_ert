import sys, json, csv; sys.path.insert(0,"D:/Here/asd")
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from PIL import Image, ImageOps
from pathlib import Path
import ssim_eval, phase3a_reconstruct as base
from tree_ert import ssim
from tree_ert.reconstruction import average_frame_vectors
from tree_ert.survey import load_frames
exec(open("measure.py").read().split("rows=[]")[0])          # T landmarks, fit_ellipse, unit
T["wood8"]=([(728,440),(838,447),(910,508),(938,615),(902,712),(842,795),(740,825),(638,795),(572,728),(535,622),(545,523),(612,432)],[(662,505)],[8])
T["wood5&11"]=([(745,458),(865,452),(952,510),(988,625),(960,732),(905,828),(793,868),(683,845),(600,800),(557,665),(555,560),(625,462)],[(650,735),(895,565)],[5,11])
MIRROR={"wood8","wood5&11"}   # labels run opposite: target = 8 - label
R=[Path("D:/Here/asd/scans/runs"),Path("D:/Here/asd/ssim/saline-tank-2026-10-02/runs")]
find=lambda r:next(p/r for p in R if (p/r).is_dir())
W=lambda x:(x+180)%360-180
mesh,solver=base.create_solver(base.build_adjacent_protocol()); proto=base.build_adjacent_protocol()
elv=np.array([mesh.node[i][:2] for i in mesh.el_pos],float); elv/=np.linalg.norm(elv,axis=1)[:,None]
el=np.degrees(np.arctan2(elv[:,1],elv[:,0]))
cent=np.mean(mesh.node[mesh.element],axis=1)[:,:2]; _,_,inside=ssim.grid_coordinates()
homog=solver.fwd.solve_eit(perm=1.0); RING=ssim.ELECTRODE_RING_RADIUS_MM; NOM=ssim.NEAR_RADIUS_MM/RING
from verify_device import BLOCK_CONTRAST
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
# best config per photo from the 98 mm searches
best={}
for fn,e2 in (("ncc_best_search",False),("ncc_best_search_e2_excluded",True)):
    for r in csv.DictReader(open(f"D:/Here/asd/saline/{fn}.csv")):
        if r["photo"]=="wood8" and "20261014" not in r["run"]: continue
        if r["photo"]=="wood5&11" and "20261023" not in r["run"]: continue
        if r["photo"] not in best or float(r["ncc"])>float(best[r["photo"]]["ncc"]): best[r["photo"]]=dict(r,e2=e2)
gt={}
for g in json.load(open("ground_truth.json")): gt.setdefault(g["photo"],[]).append(g)
gt["wood8"]=[dict(target="E8",electrode_pos=7.97,radius=0.648)]
gt["wood5&11"]=[dict(target="E5",electrode_pos=4.88,radius=0.691),dict(target="E11",electrode_pos=10.85,radius=0.655)]
SIZES={"23x22":(23,22),"30x22":(30,22),"22x30":(22,30),"23x30":(23,30),"30x23":(30,23)}
ORDER=["center"]+[f"wood{k}" for k in range(1,13)]+["wood1&7","wood2&8","wood3&9","wood4&10","wood5&11","wood6&12"]
def rectify(photo):
    tips,blocks,_=T[photo]; off=np.array([0,0]) if photo in MIRROR else np.array([150,250])
    tips=np.array(tips,float)+off
    c,w,U=fit_ellipse(tips); tu=unit(tips,c,w,U); tu[:,1]*=-1        # y up
    lab=np.arange(12)
    if photo in MIRROR: lab=(8-(lab+1))%12  # label k -> target index
    tgt=np.zeros((12,2)); tgt[lab]=tu
    # orthogonal Procrustes (rotation or reflection) photo-unit -> mesh electrode directions
    u,_,vt=np.linalg.svd(tgt.T@elv); Q=u@vt
    im=ImageOps.exif_transpose(Image.open(f"D:/Here/asd/saline/{photo}.jpg")).convert("RGB")
    N=420; g=np.linspace(-1.35,1.35,N); X,Y=np.meshgrid(g,-g)
    m=np.stack([X.ravel(),Y.ravel()],1)@Q.T                           # mesh -> photo-unit (y up)
    m[:,1]*=-1; A=U@np.diag(1/np.sqrt(w))@U.T; P=m@A.T+c
    a=np.asarray(im); xi=np.clip(P[:,0].round().astype(int),0,a.shape[1]-1); yi=np.clip(P[:,1].round().astype(int),0,a.shape[0]-1)
    return a[yi,xi].reshape(N,N,3), (g[0],g[-1])
def grid(vals): 
    gv=ssim.rasterise(np.asarray(vals,float),mesh); return gv
rows=[]
for photo in ORDER:
    b=best[photo]; d=find(b["run"]); bd=find(b["baseline"])
    st=ssim_eval._recorded_settings(json.loads((d/"conditions.json").read_text(encoding="utf-8"))["settings"])
    bv=average_frame_vectors(load_frames(bd),proto,st); tv=average_frame_vectors(load_frames(d),proto,st)
    miss=np.isnan(bv)|np.isnan(tv)
    if b["e2"]: miss|=np.array([(1 in proto.ex_mat[i]) or (1 in proto.meas_mat[i][j]) for i in range(12) for j in range(9)])
    diff=np.asarray(base.reconstruct_difference(np.where(miss,0,bv),np.where(miss,0,tv),solver,dropped_indexes=[int(i) for i in np.flatnonzero(miss)]),float)
    pts={"measured":[xy(None if g["target"]=="centre" else g["electrode_pos"],g["radius"]) for g in gt[photo]],
         "assumed":[xy(None if g["target"]=="centre" else float(g["target"][1:]),0 if g["target"]=="centre" else NOM) for g in gt[photo]],
         "photo angle + assumed radius":[xy(None if g["target"]=="centre" else g["electrode_pos"],0 if g["target"]=="centre" else NOM) for g in gt[photo]]}[b["spot"]]
    tm=template(pts,*SIZES[b["size"]])
    s_diff=ssim.ncc(ssim.resistive_image(grid(diff)),tm,inside)
    absv=None; s_abs=None
    if (d/"absolute.npz").is_file():
        with np.load(d/"absolute.npz",allow_pickle=True) as h: absv=np.log(h["sigma"]/float(h["sigma0"]))
        s_abs=ssim.ncc(ssim.resistive_image(grid(absv)),tm,inside)
    rows.append((photo,b["run"],diff,absv,s_diff,s_abs,pts))
    print(photo, round(s_diff,3), None if s_abs is None else round(s_abs,3), flush=True)
fig,axs=plt.subplots(len(rows),5,figsize=(15,3*len(rows)),gridspec_kw=dict(width_ratios=[1,1,1,1,0.7]))
t=np.linspace(0,2*np.pi,200)
for i,(photo,run,diff,absv,sd,sa,pts) in enumerate(rows):
    im=ImageOps.exif_transpose(Image.open(f"D:/Here/asd/saline/{photo}.jpg")); im.thumbnail((500,500))
    axs[i,0].imshow(im); axs[i,0].set_title(f"{photo}  (original)",fontsize=10)
    rect,(lo,hi)=rectify(photo); axs[i,1].imshow(rect,extent=[lo,hi,lo,hi])
    axs[i,1].plot(np.cos(t),np.sin(t),"y-",lw=1)
    for k,(ux,uy) in enumerate(elv): axs[i,1].text(1.18*ux,1.18*uy,f"E{k+1}",color="yellow",fontsize=7,ha="center",va="center",weight="bold")
    axs[i,1].set_title("processed (rectified to ring)",fontsize=10)
    for j,(v,name,sc) in enumerate(((diff,"difference",sd),(absv,"absolute",sa))):
        ax=axs[i,2+j]
        if v is None: ax.text(.5,.5,"no absolute solve",ha="center",transform=ax.transAxes); ax.axis("off"); continue
        gv=grid(v); lim=np.nanmax(np.abs(gv))
        ax.imshow(gv,origin="upper",extent=[-1,1,-1,1],cmap="RdBu_r",vmin=-lim,vmax=lim)
        ax.plot(np.cos(t),np.sin(t),"k-",lw=.8); ax.plot(elv[:,0],elv[:,1],"k.",ms=4)
        ax.plot([p[0] for p in pts],[p[1] for p in pts],"g+",ms=12,mew=2)
        ax.set_title(name,fontsize=10)
    for ax in axs[i,:4]: ax.set_xticks([]); ax.set_yticks([]); 
    for ax in axs[i,1:4]: ax.set_xlim(-1.35,1.35); ax.set_ylim(-1.35,1.35); ax.set_aspect("equal")
    a=axs[i,4]; a.axis("off")
    a.text(0,.75,"NCC",fontsize=11,weight="bold",transform=a.transAxes)
    a.text(0,.55,f"difference  {sd:.2f}",fontsize=12,transform=a.transAxes)
    a.text(0,.38,"absolute    "+("–" if sa is None else f"{sa:.2f}"),fontsize=12,transform=a.transAxes)
    a.text(0,.15,run[:15],fontsize=8,color="gray",transform=a.transAxes)
fig.tight_layout(); fig.savefig("D:/Here/asd/saline/contact_sheet.png",dpi=70)
