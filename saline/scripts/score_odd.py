import sys, json; sys.path.insert(0,"D:/Here/asd")
import numpy as np
from pathlib import Path
import ssim_eval, phase3a_reconstruct as base, phase3a_unified_reconstruct as unified
from tree_ert import ssim
from tree_ert.reconstruction import reconstruct
from tree_ert.survey import load_frames
R=[Path("D:/Here/asd/scans/runs"),Path("D:/Here/asd/ssim/saline-tank-2026-10-02/runs")]
find=lambda r:next(p/r for p in R if (p/r).is_dir())
truth={"wood8":[("E8",7.97,0.648)],"wood5&11":[("E5",4.88,0.691),("E11",10.85,0.655)]}
cands={"wood8":[("20261022-171934-saline-pos-e8","20261022-134226-saline-pos-empty-first"),
                ("20261022-172734-saline-pos-e8","20261022-134226-saline-pos-empty-first"),
                ("20261022-173534-saline-pos-e8","20261022-134226-saline-pos-empty-first"),
                ("20261014-191430-saline-e8-adjacent-dac400-st10-n16","20261014-200326-saline-empty-adjacent-dac400-st10-n16"),
                ("20261014-191843-saline-e8-adjacent-dac400-st10-n16","20261014-200739-saline-empty-adjacent-dac400-st10-n16"),
                ("20261014-192257-saline-e8-adjacent-dac400-st10-n16","20261014-201151-saline-empty-adjacent-dac400-st10-n16"),
                ("20261002-150425-ssim-saline","20261002-143242-ssim-saline")],
       "wood5&11":[("20261023-145649-saline-pos-e5-e11","20261023-123841-saline-pos-empty-first"),
                   ("20261023-150449-saline-pos-e5-e11","20261023-123841-saline-pos-empty-first"),
                   ("20261023-151249-saline-pos-e5-e11","20261023-123841-saline-pos-empty-first"),
                   ("20261002-175516-ssim-saline","20261002-170541-ssim-saline")]}
W=lambda x:(x+180)%360-180
out=[]
for photo,runs in cands.items():
    for rid,bid in runs:
        d,b=find(rid),find(bid)
        st=ssim_eval._recorded_settings(json.loads((d/"conditions.json").read_text(encoding="utf-8"))["settings"])
        res=reconstruct(load_frames(b),load_frames(d),st)
        proto,_=unified.protocol_and_command(st.pattern); mesh,_=base.create_solver(proto)
        el=[np.degrees(np.arctan2(mesh.node[i][1],mesh.node[i][0])) for i in mesh.el_pos]
        blocks=[]
        for lab,e,r in truth[photo]:
            k=int(e)-1; t=e-int(e); a=el[k%12]+t*W(el[(k+1)%12]-el[k%12]); a=np.radians(a)
            blocks.append(ssim.Block(lab,r*np.cos(a),r*np.sin(a)))
        grid=ssim.rasterise(res.values,mesh); img=ssim.resistive_image(grid)
        mask=ssim.block_mask(blocks); reg=ssim.score_region(mask)
        bs=ssim.score_blocks(grid,blocks)
        row=dict(photo=photo,run=rid,baseline=bid,ssim_raw=round(ssim.ssim(img,mask,reg),3),
                 ssim_blurred=round(ssim.ssim(img,ssim.blur(mask),reg),3),dice=round(ssim.dice(img,mask,reg),3),
                 blocks=[dict(label=s.label,angle_err=round(s.centroid_angle_error_deg,1),
                              true_r=round(s.true_radius,2),recon_r=round(s.centroid_radius,2)) for s in bs])
        out.append(row); print(json.dumps(row),flush=True)
json.dump(out,open("odd_scores.json","w"),indent=1)
