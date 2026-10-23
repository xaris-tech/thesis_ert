"""One recorded opposite-drive run on disc-01, solved absolutely; reciprocity reported, not required."""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, r"D:\Here\asd")
import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as u
import run_record
from tree_ert import absolute, capture_view
from tree_ert.acquisition import SerialAcquisition
from tree_ert.settings import UiSettings, preset_by_name, settings_to_dict

root = Path(r"D:\Here\asd\scans")
s = preset_by_name("Coconut").apply_to(UiSettings(port="COM7"))
s = replace(s, pattern="opposite").validate()
cond = run_record.Conditions(
    medium="cut disc", specimen_id="disc-01", target_description="holes near E4-E7",
    notes="2026-10-23 opposite-drive test after adjacent run; reciprocity not measurable for opposite "
          "(no reciprocal pairs), gate reported but not required; E2 channel intermittent",
    extra={"survey_state": "defect"},
)
log = run_record.SessionLog(root)
acq = SerialAcquisition()
acq.connect(s)
try:
    acq.configure(s)
    for _ in range(s.warmup_frames):
        acq.capture_frame()
    rec = run_record.create_run(root, "disc-01-opposite", conditions=cond, settings=settings_to_dict(s))
    log.banner(f"Run {rec.run_id}")
    frames = []
    for _ in range(s.frames):
        f = acq.capture_frame()
        rec.write_frame(f)
        frames.append(f)
finally:
    acq.close()

protocol, _ = u.protocol_and_command("opposite")
mesh, _ = base.create_solver(protocol)
c = np.mean(mesh.node[mesh.element], axis=1)
ang = np.degrees(np.arctan2(c[:, 1], c[:, 0])) % 360
lines = []
best = None
for ex in ((), (2,)):
    result, noise, report = absolute.evaluate(frames, replace(s, absolute_exclude_electrodes=ex))
    if result is None:
        lines.append(f"exclude {ex or 'none'}: solve failed")
        continue
    other = [r for r in report.reasons if "reciprocity" not in r]
    v = np.log(result.sigma / result.sigma0)
    sectors = " ".join(f"{lo}:{v[(ang >= lo) & (ang < lo + 30)].min():+.2f}" for lo in range(0, 360, 30))
    lines.append(f"exclude {ex or 'none'}: misfit {result.residual_percent:.1f}% "
                 f"significance {report.significance:.2f} | gates other than reciprocity: "
                 f"{'pass' if not other else '; '.join(other)} | {result.trough_text()}"
                 f"{absolute.excluded_text(replace(s, absolute_exclude_electrodes=ex), result)}\n  sectors {sectors}")
    absolute.save_absolute(absolute.Attempt(replace(s, absolute_exclude_electrodes=ex), frames, result, noise, report),
                           rec.path / f"absolute{'-excl-e2' if ex else ''}.png",
                           rec.path / f"absolute{'-excl-e2' if ex else ''}.npz",
                           title=f"{rec.run_id} opposite (absolute{', E2 excluded' if ex else ''})", thickness_mm=None)
    if not ex:
        best = (result, report)
summary = capture_view.session_summary(frames)
rec.write_text("summary.txt", capture_view.format_session_summary(summary) + "\n" + "\n".join(lines) + "\n")
result, report = best
run_record.append_index_row(root, rec.index_row(
    outcome="complete", significance=report.significance,
    noise_median_percent=report.noise_relative_percent,
    absolute_sigma0_ms=result.sigma0, absolute_misfit_percent=result.residual_percent,
    absolute_gate="pass" if report.passed else "; ".join(report.reasons),
    **absolute.trough_index_fields(result),
))
rec.close()
log.close()
print(rec.run_id)
print("\n".join(lines))
