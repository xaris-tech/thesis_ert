"""Absolute reconstruction of a series of cut discs, with continuous recalibration.

Each specimen in the plan is mounted in turn. For each one the instrument is
configured from the Coconut preset, warmed up, and a run is recorded; the run is
solved absolutely and gated on reciprocity, model misfit and significance
(ADR-0041). A refused run is re-acquired with settings chosen from the earlier
attempts (more averaging when noisy, settle 10-50 ms, then a lower DAC, ADR-0060)
until one passes, a stop rule fires (ADR-0043) or ``--max-attempts`` is reached.
Every attempt is a recorded run in ``scans/``.

    .venv\\Scripts\\python.exe absolute_session.py --plan plans/coconut-discs-2026-10-06.csv --port COM3
    .venv\\Scripts\\python.exe absolute_session.py --plan plans/coconut-discs-2026-10-06.csv --demo --yes

Plan CSV: ``specimen_id,state,target,note`` (state intact/defect/excluded, as the
survey manifest). At the end a survey manifest naming the passing run of each
specimen is written next to the summary, ready for ``disc_survey.py --manifest``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import run_record
from tree_ert import absolute, capture_view
from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.settings import UiSettings, preset_by_name, settings_to_dict


def read_plan(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    for row in rows:
        if row.get("state") not in {"intact", "defect", "excluded"}:
            raise ValueError(f"{row.get('specimen_id')}: state must be intact/defect/excluded")
    return rows


def base_settings(port: str) -> UiSettings:
    preset = preset_by_name("Coconut")
    settings = UiSettings(port=port)
    return preset.apply_to(settings) if preset else settings


def make_conditions(row: dict[str, str], args: argparse.Namespace, attempt: int) -> run_record.Conditions:
    notes = row.get("note", "")
    return run_record.Conditions(
        medium="cut disc",
        specimen_id=row["specimen_id"],
        target_description=row.get("target", ""),
        electrode_map=args.electrode_map,
        thickness_mm=args.thickness_mm,
        operator=args.operator,
        notes=notes,
        extra={"survey_state": row["state"], "recalibration_attempt": attempt},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, required=True)
    hardware = parser.add_mutually_exclusive_group(required=True)
    hardware.add_argument("--port")
    hardware.add_argument("--demo", action="store_true", help="synthetic frames, no hardware")
    parser.add_argument("--scans-root", type=Path, default=Path("scans"))
    parser.add_argument(
        "--max-attempts", type=int, default=absolute.ADAPTIVE_MAX_ATTEMPTS,
        help="acquisitions per specimen before giving up (ADR-0060)",
    )
    parser.add_argument("--only", nargs="*", help="specimen IDs to run (default all)")
    parser.add_argument("--thickness-mm", type=float, help="disc thickness, for S/m")
    parser.add_argument("--electrode-map", default="")
    parser.add_argument("--operator", default="")
    parser.add_argument("--yes", action="store_true", help="do not wait for Enter between discs")
    args = parser.parse_args(argv)

    plan = read_plan(args.plan)
    if args.only:
        plan = [row for row in plan if row["specimen_id"] in set(args.only)]
    acquisition = DemoAcquisition() if args.demo else SerialAcquisition()
    settings = base_settings("DEMO" if args.demo else args.port).validate()

    session_log = run_record.SessionLog(args.scans_root)
    session_log.banner(f"absolute session: {args.plan} ({len(plan)} specimens)")

    def say(message: str) -> None:
        print(message, flush=True)
        session_log.write(message)

    acquisition.connect(settings)
    outcomes: list[dict[str, str]] = []
    try:
        for row in plan:
            specimen = row["specimen_id"]
            if not args.yes:
                input(f"\nMount {specimen} ({row['state']}"
                      f"{': ' + row['target'] if row['target'] else ''}) and press Enter...")
            session_log.banner(f"specimen {specimen}")
            attempt_counter = {"n": 0}
            recorders: dict[int, run_record.RunRecorder] = {}

            def capture(candidate: UiSettings) -> list:
                attempt_counter["n"] += 1
                number = attempt_counter["n"]
                conditions = make_conditions(row, args, number)
                label = run_record.run_label(conditions)
                problems = run_record.naming_problems(conditions, label)
                if problems:
                    raise ValueError("; ".join(problems))
                acquisition.configure(candidate)
                for _ in range(candidate.warmup_frames):
                    acquisition.capture_frame()
                recorder = run_record.create_run(
                    args.scans_root, label, conditions=conditions,
                    settings=settings_to_dict(candidate),
                )
                recorders[number] = recorder
                frames = []
                for _ in range(candidate.frames):
                    frame = acquisition.capture_frame()
                    recorder.write_frame(frame)
                    frames.append(frame)
                return frames

            def on_attempt(number: int, attempt: absolute.Attempt) -> None:
                recorder = recorders[number]
                report = attempt.report
                result = attempt.result
                s = attempt.settings
                verdict = "PASS" if report.passed else "REFUSED: " + "; ".join(report.reasons)
                say(
                    f"{specimen} attempt {number}: settle={s.settle_ms}ms samples={s.samples} "
                    f"warmup={s.warmup_frames} frames={s.frames} -> {verdict}"
                )
                if result is not None:
                    absolute.save_absolute(
                        attempt,
                        recorder.path / "absolute.png",
                        recorder.path / "absolute.npz",
                        title=f"{recorder.run_id} (absolute)",
                        thickness_mm=args.thickness_mm,
                    )
                summary = capture_view.session_summary(attempt.frames)
                recorder.write_text(
                    "summary.txt",
                    capture_view.format_session_summary(summary) + f"\nabsolute: {verdict}\n",
                )
                run_record.append_index_row(
                    args.scans_root,
                    recorder.index_row(
                        outcome="complete",
                        peak_value=result.peak_value if result else None,
                        peak_angle_deg=result.peak_angle_deg if result else None,
                        significance=report.significance,
                        reciprocity_median_percent=report.reciprocity_percent,
                        noise_median_percent=report.noise_relative_percent,
                        absolute_sigma0_ms=result.sigma0 if result else None,
                        absolute_misfit_percent=result.residual_percent if result else None,
                        absolute_gate="pass" if report.passed else "; ".join(report.reasons),
                    ),
                )
                recorder.close()

            attempts, passed = absolute.acquire_until_pass(
                capture, settings, on_attempt=on_attempt, max_attempts=args.max_attempts
            )
            if passed is None:
                say(f"{specimen}: no attempt passed after {len(attempts)} acquisitions -- check contacts")
            run_id = recorders[attempts.index(passed) + 1].run_id if passed else ""
            outcomes.append({
                "run_id": run_id,
                "specimen_id": specimen,
                "state": row["state"] if passed else "excluded",
                "note": row.get("note", "") if passed else "no attempt passed the absolute gates",
            })
    except KeyboardInterrupt:
        say("session interrupted by operator")
    finally:
        acquisition.close()

    out = Path("exports") / f"absolute-session-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "survey-manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id", "specimen_id", "state", "note"])
        writer.writeheader()
        writer.writerows(row for row in outcomes if row["run_id"])
    for row in outcomes:
        say(f"{row['specimen_id']}: {row['run_id'] or 'FAILED'}")
    say(f"Survey manifest: {manifest}")
    session_log.close()
    return 0 if outcomes and all(row["run_id"] for row in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
