"""disc-01 drill test: one adjacent and one opposite recorded run per step (B1..B3, S1, D1..D3).

Absolute solve reported (reciprocity not required for opposite); with --ref-adj/--ref-opp,
the difference image against those runs is saved and its trough/significance printed.
"""
import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, r"D:\Here\asd")
import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as u
import position_series as ps
import run_record
from tree_ert import absolute, capture_view, reconstruction, survey
from tree_ert.acquisition import SerialAcquisition
from tree_ert.settings import UiSettings, preset_by_name, settings_to_dict

ap = argparse.ArgumentParser()
ap.add_argument("step")  # B1, S1, D1 ...
ap.add_argument("--ref-adj")
ap.add_argument("--ref-opp")
ap.add_argument("--note", default="")
args = ap.parse_args()

root = Path(r"D:\Here\asd\scans")
coconut = preset_by_name("Coconut").apply_to(UiSettings(port="COM7")).validate()
state = "intact" if args.step.startswith(("B", "S")) else "defect"
target = {"B": "before drilling (existing holes near E4-E7)",
          "S": "sham: handled at drill site, not drilled",
          "D": "after drilling new hole at E3 (~120 deg), through"}[args.step[0]]
log = run_record.SessionLog(root)
acq = SerialAcquisition()
acq.connect(coconut)
try:
    for pattern, ref in (("adjacent", args.ref_adj), ("opposite", args.ref_opp)):
        s = replace(coconut, pattern=pattern).validate()
        cond = run_record.Conditions(
            medium="cut disc", specimen_id="disc-01", target_description=target,
            notes=f"2026-10-23 disc-01 drill test step {args.step} ({pattern}); screws/leads untouched since B1. {args.note}".strip(),
            extra={"drill_test_step": args.step, "survey_state": state},
        )
        acq.configure(s)
        for _ in range(s.warmup_frames):
            acq.capture_frame()
        rec = run_record.create_run(root, f"disc-01-{args.step.lower()}-{pattern}", conditions=cond,
                                    settings=settings_to_dict(s))
        log.banner(f"Run {rec.run_id}")
        frames = []
        for _ in range(s.frames):
            f = acq.capture_frame()
            rec.write_frame(f)
            frames.append(f)
        result, noise, report = absolute.evaluate(frames, s)
        other = [r for r in report.reasons if "reciprocity" not in r] if pattern == "opposite" else report.reasons
        lines = [f"absolute (all electrodes): misfit {result.residual_percent:.1f}%, "
                 f"{'pass' if not other else '; '.join(other)}, {result.trough_text()}"]
        absolute.save_absolute(absolute.Attempt(s, frames, result, noise, report),
                               rec.path / "absolute.png", rec.path / "absolute.npz",
                               title=f"{rec.run_id} ({pattern}, absolute)", thickness_mm=None)
        if ref:
            protocol, _ = u.protocol_and_command(pattern)
            mesh, _ = base.create_solver(protocol)
            ref_frames = survey.load_frames(root / "runs" / ref)
            diff = reconstruction.reconstruct(ref_frames, frames, s)
            control = reconstruction.split_half_control(ref_frames, s)
            sig = reconstruction.significance(diff, control)
            trough = ps.resistive_trough_deg(diff.values, mesh)
            reconstruction.save_reconstruction(diff, s, rec.path / "reconstruction.png", rec.path / "reconstruction.npz",
                                               title=f"{rec.run_id} vs {ref}", control=control)
            rec.write_text("reconstruction.txt", f"baseline: {ref}\ntarget: {target}\n")
            lines.append(f"difference vs {ref}: resistive trough {trough:.0f} deg (target ~120), significance {sig:.2f}")
        rec.write_text("summary.txt", capture_view.format_session_summary(capture_view.session_summary(frames))
                       + "\n" + "\n".join(lines) + "\n")
        run_record.append_index_row(root, rec.index_row(
            outcome="complete", significance=report.significance,
            noise_median_percent=report.noise_relative_percent,
            absolute_sigma0_ms=result.sigma0, absolute_misfit_percent=result.residual_percent,
            absolute_gate="pass" if report.passed else "; ".join(report.reasons),
            **absolute.trough_index_fields(result)))
        rec.close()
        msg = f"[{args.step} {pattern}] {rec.run_id}\n  " + "\n  ".join(lines)
        print(msg, flush=True)
        log.write(msg)
finally:
    acq.close()
    log.close()
