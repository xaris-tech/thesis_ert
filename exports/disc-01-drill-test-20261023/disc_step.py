"""One drill-test step on any disc: an adjacent and an opposite recorded run at fixed settings.

DAC 620, settle 10 ms, 16 samples, 5 warm-up + 10 frames (the 2026-10-24 disc-08 settings).
Each run is solved absolutely (reciprocity not required for opposite) and, with --ref-adj /
--ref-opp, differenced against that reference run.

    python disc_step.py disc-08 B1 "hole near E10"
    python disc_step.py disc-08 D1 "holes near E10 and E5" --ref-adj <run> --ref-opp <run>
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
from tree_ert.settings import UiSettings, settings_to_dict

ap = argparse.ArgumentParser()
ap.add_argument("specimen")
ap.add_argument("step")
ap.add_argument("target")
ap.add_argument("--ref-adj")
ap.add_argument("--ref-opp")
ap.add_argument("--note", default="")
ap.add_argument("--port", default="COM7")
args = ap.parse_args()

root = Path(r"D:\Here\asd\scans")
base_settings = UiSettings(port=args.port, current_range="high", dac=620, settle_ms=10, samples=16,
                           warmup_frames=5, frames=10)
log = run_record.SessionLog(root)
acq = SerialAcquisition()
acq.connect(base_settings)
try:
    for pattern, ref in (("opposite", args.ref_opp), ("adjacent", args.ref_adj)):
        s = replace(base_settings, pattern=pattern).validate()
        cond = run_record.Conditions(
            medium="cut disc", specimen_id=args.specimen, target_description=args.target,
            notes=f"drill test step {args.step} ({pattern}). {args.note}".strip(),
            extra={"drill_test_step": args.step},
        )
        acq.configure(s)
        for _ in range(s.warmup_frames):
            acq.capture_frame()
        rec = run_record.create_run(root, f"{args.specimen}-{args.step.lower()}-{pattern}",
                                    conditions=cond, settings=settings_to_dict(s))
        log.banner(f"Run {rec.run_id}")
        frames = []
        for _ in range(s.frames):
            f = acq.capture_frame()
            rec.write_frame(f)
            frames.append(f)
        protocol, _ = u.protocol_and_command(pattern)
        mesh, _ = base.create_solver(protocol)
        c = np.mean(mesh.node[mesh.element], axis=1)
        ang = np.degrees(np.arctan2(c[:, 1], c[:, 0])) % 360
        sectors = lambda v: " ".join(f"{lo}:{v[(ang >= lo) & (ang < lo + 30)].min():+.3f}" for lo in range(0, 360, 30))
        result, noise, report = absolute.evaluate(frames, s)
        other = [r for r in report.reasons if "reciprocity" not in r] if pattern == "opposite" else report.reasons
        loo = " ".join(f"E{n}:{absolute.reconstruct_absolute(frames, replace(s, absolute_exclude_electrodes=(n,))).residual_percent:.0f}"
                       for n in range(1, 13))
        lines = [f"absolute: misfit {result.residual_percent:.1f}%, {'pass' if not other else '; '.join(other)}, {result.trough_text()}",
                 f"  sectors {sectors(np.log(result.sigma / result.sigma0))}",
                 f"  leave-one-out misfit %: {loo}"]
        absolute.save_absolute(absolute.Attempt(s, frames, result, noise, report),
                               rec.path / "absolute.png", rec.path / "absolute.npz",
                               title=f"{rec.run_id} ({pattern}, absolute)", thickness_mm=None)
        if ref:
            ref_frames = survey.load_frames(root / "runs" / ref)
            diff = reconstruction.reconstruct(ref_frames, frames, s)
            control = reconstruction.split_half_control(ref_frames, s)
            sig = reconstruction.significance(diff, control)
            reconstruction.save_reconstruction(diff, s, rec.path / "reconstruction.png", rec.path / "reconstruction.npz",
                                               title=f"{rec.run_id} vs {ref}", control=control)
            rec.write_text("reconstruction.txt", f"baseline: {ref}\ntarget: {args.target}\n")
            lines.append(f"difference vs {ref}: resistive trough {ps.resistive_trough_deg(diff.values, mesh):.0f} deg, "
                         f"significance {sig:.2f}")
            lines.append(f"  sectors {sectors(diff.values)}")
        rec.write_text("summary.txt", capture_view.format_session_summary(capture_view.session_summary(frames))
                       + "\n" + "\n".join(lines) + "\n")
        run_record.append_index_row(root, rec.index_row(
            outcome="complete", significance=report.significance,
            noise_median_percent=report.noise_relative_percent,
            absolute_sigma0_ms=result.sigma0, absolute_misfit_percent=result.residual_percent,
            absolute_gate="pass" if report.passed else "; ".join(report.reasons),
            **absolute.trough_index_fields(result)))
        rec.close()
        msg = f"[{args.specimen} {args.step} {pattern}] {rec.run_id}\n  " + "\n  ".join(lines)
        print(msg, flush=True)
        log.write(msg)
finally:
    acq.close()
    log.close()
