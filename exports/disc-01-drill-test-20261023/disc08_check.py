import sys; sys.path.insert(0, r"D:\Here\asd")
import json, numpy as np
from dataclasses import replace
from pathlib import Path
import phase3a_reconstruct as base, phase3a_unified_reconstruct as u
from tree_ert import survey, absolute
from tree_ert.settings import settings_from_dict
for run in sys.argv[1:]:
    p=Path(r"D:\Here\asd\scans\runs")/run
    st=json.loads((p/"conditions.json").read_text())["settings"]
    from tree_ert.settings import UiSettings
    s=UiSettings(port="x",pattern=st["pattern"],current_range="high",dac=st["dac"],settle_ms=st["settle_ms"],samples=st["samples"])
    pr,_=u.protocol_and_command(s.pattern); m,_=base.create_solver(pr)
    c=np.mean(m.node[m.element],axis=1); a=np.degrees(np.arctan2(c[:,1],c[:,0]))%360
    fr=survey.load_frames(p)
    loo=[(n,absolute.reconstruct_absolute(fr,replace(s,absolute_exclude_electrodes=(n,))).residual_percent) for n in range(1,13)]
    best=min(loo,key=lambda x:x[1])
    print(run[16:], "loo", " ".join(f"E{n}:{v:.0f}" for n,v in loo))
    for ex in [(),(best[0],)]:
        r=absolute.reconstruct_absolute(fr,replace(s,absolute_exclude_electrodes=ex)); v=np.log(r.sigma/r.sigma0)
        print("  excl",ex or "none",f"{r.residual_percent:.1f}%",r.trough_text(), "|", " ".join(f"{lo}:{v[(a>=lo)&(a<lo+30)].min():+.2f}" for lo in range(0,360,30)))
