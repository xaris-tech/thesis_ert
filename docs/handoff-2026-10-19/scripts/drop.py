import sys, json, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
sys.path.insert(0, r"D:\Here\asd")
import phase3a_unified_reconstruct as unified
from tree_ert import absolute, survey
from tree_ert.settings import UiSettings
runs = sys.argv[1:]
for r in runs:
    d = next(Path(r"D:\Here\asd\scans\runs").glob(r + "*"))
    s = json.load(open(d / "conditions.json"))["settings"]
    frames = survey.load_frames(d)
    st = UiSettings(**{k: v for k, v in s.items() if k in UiSettings.__dataclass_fields__})
    protocol, _ = unified.protocol_and_command(st.pattern)
    vec = absolute.average_frame_vectors(frames, protocol, st)
    ex = np.asarray(protocol.ex_mat); mm = np.asarray(protocol.meas_mat)
    def touch(els):
        rows = []
        if mm.ndim == 3:
            for k, block in enumerate(mm):
                a, b = ex[k]
                for m in block:
                    rows.append(bool({int(m[0]), int(m[1]), int(a), int(b)} & set(els)))
        else:
            for m in mm:
                a, b = ex[int(m[2])]
                rows.append(bool({int(m[0]), int(m[1]), int(a), int(b)} & set(els)))
        return np.array(rows)
    out = []
    for name, els in [("all", []), ("-E1E2", [0, 1]), ("-E1E2E3", [0, 1, 2]), ("-E5E6", [4, 5])]:
        v = vec.copy()
        if els: v[touch(els)] = np.nan
        try:
            res = absolute.solve_absolute(v, protocol)
            out.append(f"{name} misfit {res.residual_percent:5.1f}% kept {res.kept_pairs}/{res.total_pairs} s0 {res.sigma0*1000:.2f}")
        except Exception as e:
            out.append(f"{name} ERR {e}")
    print(d.name[:45], " | ".join(out))
