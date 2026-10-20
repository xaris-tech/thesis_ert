import sys, json, warnings
warnings.filterwarnings("ignore")
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, r"D:\Here\asd")
from tree_ert import absolute, survey
from tree_ert.settings import settings_from_dict
for r in sys.argv[1:]:
    d = next(Path(r"D:\Here\asd\scans\runs").glob(r + "*"))
    s = settings_from_dict(json.load(open(d / "conditions.json"))["settings"])
    s = replace(s, absolute_exclude_electrodes=())
    frames = survey.load_frames(d)
    res, noise, rep = absolute.evaluate(frames, s)
    v = "PASS" if rep.passed else "REFUSED: " + "; ".join(rep.reasons)
    print(d.name[:52], v[:40], f"s0 {res.sigma0:.2f}", res.trough_text(), flush=True)
