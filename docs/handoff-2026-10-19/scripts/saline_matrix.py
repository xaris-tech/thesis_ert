"""Saline-tank settings matrix: one recorded run per (pattern, DAC, settle, samples).

Each run is recorded in scans/ exactly like a Qt run (conditions, frames.csv,
index row), solved absolutely with the given exclusion, and its gate verdict printed.
"""
import argparse
import itertools
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, r"D:\Here\asd")
import run_record  # noqa: E402
from tree_ert import absolute, capture_view  # noqa: E402
from tree_ert.acquisition import SerialAcquisition  # noqa: E402
from tree_ert.settings import UiSettings, settings_to_dict  # noqa: E402


def ints(text):
    return [int(x) for x in text.split(",") if x]


p = argparse.ArgumentParser()
p.add_argument("--port", default="COM7")
p.add_argument("--patterns", default="adjacent,opposite,skip-1,skip-2")
p.add_argument("--dacs", default="100,200,400")
p.add_argument("--settles", default="10")
p.add_argument("--samples", default="16")
p.add_argument("--warmup", type=int, default=5)
p.add_argument("--frames", type=int, default=10)
p.add_argument("--exclude", default="1,2")
p.add_argument("--specimen", default="saline-tank")
p.add_argument("--target", default="wood at e6")
p.add_argument("--label", default="saline-matrix")
p.add_argument("--saline", type=float, default=None)
p.add_argument("--temp", type=float, default=None)
p.add_argument("--fill", type=float, default=None)
p.add_argument("--grounding", default="unknown")
p.add_argument("--notes", default="")
p.add_argument("--start", type=int, default=1)
p.add_argument("--medium", default="saline tank")
a = p.parse_args()

root = Path(r"D:\Here\asd\scans")
combos = list(itertools.product(
    a.patterns.split(","), ints(a.dacs), ints(a.settles), ints(a.samples)))
print(f"{len(combos)} runs", flush=True)

log = run_record.SessionLog(root)
acq = SerialAcquisition()
base = UiSettings(port=a.port, current_range="high", warmup_frames=a.warmup,
                  frames=a.frames, absolute_exclude_electrodes=tuple(ints(a.exclude)))
acq.connect(base)
try:
    for n, (pattern, dac, settle, samples) in enumerate(combos, 1):
        if n < a.start:
            continue
        s = replace(base, pattern=pattern, dac=dac, settle_ms=settle, samples=samples).validate()
        cond = run_record.Conditions(
            medium=a.medium, specimen_id=a.specimen, target_description=a.target, tank_contents=a.target,
            saline_g_per_l=a.saline, water_temp_c=a.temp, fill_depth_mm=a.fill,
            grounding=a.grounding,
            electrode_map="E1 = marked nail, clockwise viewed from above",
            notes=f"{a.notes} matrix {n}/{len(combos)}".strip(),
        )
        label = f"{a.label}-{pattern}-dac{dac}-st{settle}-n{samples}"
        t0 = time.time()
        acq.configure(s)
        for _ in range(s.warmup_frames):
            acq.capture_frame()
        rec = run_record.create_run(root, label, conditions=cond, settings=settings_to_dict(s))
        log.banner(f"Run {rec.run_id}")
        frames = []
        for _ in range(s.frames):
            f = acq.capture_frame()
            rec.write_frame(f)
            frames.append(f)
        result, noise, report = absolute.evaluate(frames, s)
        verdict = "PASS" if report.passed else "REFUSED: " + "; ".join(report.reasons)
        if result is not None:
            verdict += absolute.excluded_text(s, result)
            absolute.save_absolute(
                absolute.Attempt(s, frames, result, noise, report),
                rec.path / "absolute.png", rec.path / "absolute.npz",
                title=f"{rec.run_id} (absolute)", thickness_mm=None)
        summary = capture_view.session_summary(frames)
        rec.write_text("summary.txt",
                       capture_view.format_session_summary(summary) + f"\nabsolute: {verdict}\n")
        run_record.append_index_row(root, rec.index_row(
            outcome="complete",
            peak_value=result.peak_value if result else None,
            peak_angle_deg=result.peak_angle_deg if result else None,
            significance=report.significance,
            reciprocity_median_percent=report.reciprocity_percent,
            noise_median_percent=report.noise_relative_percent,
            absolute_sigma0_ms=result.sigma0 if result else None,
            absolute_misfit_percent=result.residual_percent if result else None,
            absolute_gate="pass" if report.passed else "; ".join(report.reasons),
            **absolute.trough_index_fields(result),
        ))
        rec.close()
        cur = [r.current_ua for f in frames for r in f.records]
        cur.sort()
        line = (f"[{n}/{len(combos)}] {pattern:8} dac{dac:<4} st{settle:<3} n{samples:<3} "
                f"I med {cur[len(cur)//2]:.0f} uA | {verdict} | "
                f"s0 {result.sigma0 if result else float('nan'):.2f} "
                f"peak {result.peak_angle_deg if result else float('nan'):.0f} deg | "
                f"{(time.time()-t0)/60:.1f} min | {rec.run_id}")
        print(line, flush=True)
        log.write(line)
finally:
    acq.close()
    log.close()
