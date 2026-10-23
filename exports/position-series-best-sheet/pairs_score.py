import sys; sys.path.insert(0, r"D:\Here\asd")
import json, numpy as np
from dataclasses import replace
from pathlib import Path
import phase3a_reconstruct as base, phase3a_unified_reconstruct as u
from tree_ert import survey, reconstruction, absolute
from tree_ert.settings import UiSettings
R=Path(r"D:\Here\asd\scans\runs")
s=UiSettings(port="x",pattern="adjacent",current_range="high",dac=400,settle_ms=10,samples=16)
p,_=u.protocol_and_command("adjacent"); m,_=base.create_solver(p)
c=np.mean(m.node[m.element],axis=1); a=np.degrees(np.arctan2(c[:,1],c[:,0]))%360; rad=np.hypot(c[:,0],c[:,1])
def near(deg): d=np.abs((a-deg+180)%360-180); return (d<=20)&(rad>0.4)
def score(v, blocks):
    bg=np.ones(len(v),bool)
    for b in blocks: bg&=~(np.abs((a-b+180)%360-180)<=45)
    bgmin=v[bg&(rad>0.4)].min()
    return [v[near(b)].min()/bgmin for b in blocks]   # >1 = block deeper than deepest background dip
empties=sorted(R.glob("20261023-*-empty-last"))
L={e:survey.load_frames(e) for e in empties}
ctl={e:reconstruction.split_half_control(L[e],s) for e in empties}
ref=min(empties,key=lambda e:ctl[e].limit); print("ref",ref.name,"control",f"{ctl[ref].limit:.4f}", {e.name[9:15]:round(ctl[e].limit,4) for e in empties})
sx=replace(s,absolute_exclude_electrodes=(2,))
print("pair run | diff sig | diff ratio A,B | abs(E2 excl) ratio A,B | abs all-el misfit")
for run in sorted(R.glob("20261023-*-saline-pos-e*-e*")):
    pos=json.loads((run/"conditions.json").read_text())["conditions"]["extra"]["position"]
    blocks=[(7-int(x[1:]))*30%360 for x in pos.split("+")]
    fr=survey.load_frames(run)
    d=reconstruction.reconstruct(L[ref],fr,s); sig=reconstruction.significance(d,ctl[ref])
    dr=score(d.values,blocks)
    ax=absolute.reconstruct_absolute(fr,sx); ar=score(np.log(ax.sigma/ax.sigma0),blocks)
    al=absolute.reconstruct_absolute(fr,s).residual_percent
    print(f"{pos:7} {run.name[9:15]} | {sig:5.1f} | {dr[0]:.2f},{dr[1]:.2f} | {ar[0]:.2f},{ar[1]:.2f} | {al:.1f}%")
