"""Saline-tank position series: absolute where the sector can be seen, difference where it cannot.

Walks the handoff 2026-10-19 §3.5 series -- empty tank first, wood at each of
E1-E12, the six opposite pairs, the centre, empty tank last -- prompting the
operator to move the wood between positions. Every run is recorded in
``scans/`` like a Qt run and gets three solves (ADR-0071):

* absolute with **no** electrodes excluded (ADR-0070), plus a leave-one-out sweep;
* absolute with the standing exclusion (``--exclude``, default E1/E2, ADR-0067);
* difference against the last run of the opening empty baseline, all electrodes,
  with a split-half control from that baseline for significance.

Which of the two images is the result for a position depends on whether the
target sits in the sector the exclusion blinds (``--blind``, default E1-E3):
blind positions are judged by the difference image, the rest by the excluded
absolute image. Both are always written; the summary marks the headline one.

    .venv\\Scripts\\python.exe position_series.py --port COM7 --saline 1.0 --temp 24 --fill 50
    .venv\\Scripts\\python.exe position_series.py --demo --yes --runs 1 --frames 4 --warmup 0
"""

from __future__ import annotations

import argparse
import csv
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
import run_record
from tree_ert import absolute, capture_view, reconstruction, ssim, survey
from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.settings import UiSettings, settings_to_dict

ANGLE_TOLERANCE_DEG = 30.0
"""Trough within this of the nearest block counts as located (ADR-0068's ±30°)."""


@dataclass(frozen=True)
class Position:
    key: str
    """Short label: 'empty-first', 'e5', 'e1+e7', 'centre', 'empty-last'."""
    target: str
    """Target text in the form ``tree_ert.ssim.parse_target`` reads."""
    electrodes: tuple[int, ...]
    """1-based electrodes the wood sits at; empty for the tank or the centre."""

    @property
    def is_empty(self) -> bool:
        return self.key.startswith("empty")


def series(positions: str = "all") -> list[Position]:
    """The §3.5 series in bench order. ``positions`` narrows it to listed keys."""
    full = [Position("empty-first", "empty tank", ())]
    full += [Position(f"e{n}", f"wood at e{n}", (n,)) for n in range(1, 13)]
    full += [Position(f"e{n}+e{n + 6}", f"wood at e{n} and e{n + 6}", (n, n + 6)) for n in range(1, 7)]
    full += [Position("centre", "wood at centre", ())]
    full += [Position("empty-last", "empty tank", ())]
    if positions == "all":
        return full
    wanted = [key.strip() for key in positions.split(",") if key.strip()]
    by_key = {p.key: p for p in full}
    unknown = [key for key in wanted if key not in by_key]
    if unknown:
        raise ValueError(f"unknown positions: {', '.join(unknown)} (known: {', '.join(by_key)})")
    return [by_key[key] for key in wanted]


def is_blind(position: Position, blind: tuple[int, ...]) -> bool:
    """True if any block of this position sits in the blinded sector."""
    return any(n in blind for n in position.electrodes)


def headline(position: Position, blind: tuple[int, ...]) -> str:
    if position.is_empty:
        return "baseline"
    return "difference" if is_blind(position, blind) else "absolute"


def angle_error(found_deg: float | None, position: Position, eit_mesh) -> float | None:
    """Degrees from the found angle to the nearest block, None if not applicable.

    Uses the mesh's own electrode positions, as ``ssim_eval`` does. A centre
    target has no angle to miss.
    """
    if found_deg is None or not position.electrodes:
        return None
    vectors = ssim.electrode_unit_vectors(eit_mesh)
    errors = []
    for n in position.electrodes:
        x, y = vectors[n - 1]
        expected = float(np.degrees(np.arctan2(y, x)) % 360.0)
        diff = abs(found_deg - expected) % 360.0
        errors.append(min(diff, 360.0 - diff))
    return min(errors)


def resistive_trough_deg(values: np.ndarray, eit_mesh) -> float:
    """Angle of the most negative element of a difference image.

    Wood is resistive and the solver's negative is a conductivity decrease
    (``tree_ert.ssim.resistive_image``); ``ReconstructionResult.peak_angle_deg``
    takes the largest change of either sign, which a conductive artefact wins.
    """
    centres = np.mean(eit_mesh.node[eit_mesh.element], axis=1)
    x, y = centres[int(np.argmin(values))][:2]
    return float(np.degrees(np.arctan2(y, x)) % 360.0)


def leave_one_out(frames, settings: UiSettings) -> list[tuple[int, float | None]]:
    """(electrode, misfit %) with each electrode excluded alone (ADR-0070).

    Only the misfit is needed, so each electrode gets one solve, not the
    split-half noise solves ``absolute.evaluate`` adds (about 3 s against 10 s).
    """
    out = []
    for n in range(1, 13):
        try:
            result = absolute.reconstruct_absolute(
                frames, replace(settings, absolute_exclude_electrodes=(n,)))
            out.append((n, result.residual_percent))
        except (ValueError, np.linalg.LinAlgError):
            out.append((n, None))
    return out


SUMMARY_COLUMNS = [
    "position", "repeat", "run_id", "headline", "blind",
    "unexcluded_gate", "unexcluded_misfit_percent", "sweep_best", "sweep_best_misfit_percent",
    "excluded", "excluded_gate", "excluded_misfit_percent", "excluded_sigma0_ms",
    "absolute_trough_deg", "absolute_trough_error_deg", "absolute_trough_electrodes",
    "baseline_run_id", "difference_trough_deg", "difference_trough_error_deg", "difference_significance",
    "located",
]


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def located(row: dict, position: Position) -> str:
    """'yes'/'no' for the headline image, '' where the question does not apply."""
    if position.is_empty or not position.electrodes:
        return ""
    if row["headline"] == "absolute":
        if row["excluded_gate"] != "pass":
            return "no (refused)"
        error = row["absolute_trough_error_deg"]
    else:
        significance = row["difference_significance"]
        if significance is None or significance < 2.0:
            return "no (below noise)"
        error = row["difference_trough_error_deg"]
    return "yes" if error is not None and error <= ANGLE_TOLERANCE_DEG else "no (wrong place)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    hardware = parser.add_mutually_exclusive_group(required=True)
    hardware.add_argument("--port")
    hardware.add_argument("--demo", action="store_true", help="synthetic frames, no hardware")
    parser.add_argument("--positions", default="all", help="comma-separated keys, e.g. e3,e1+e7,centre")
    parser.add_argument("--runs", type=int, default=3, help="repeats per position")
    parser.add_argument("--exclude", default="1,2", help="standing exclusion (ADR-0067)")
    parser.add_argument("--blind", default="1,2,3", help="electrodes whose positions are judged by difference")
    parser.add_argument("--baseline", help="run ID of an empty-tank run to difference against (on resume)")
    parser.add_argument("--dac", type=int, default=400)
    parser.add_argument("--settle", type=int, default=10)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--no-sweep", action="store_true", help="skip the leave-one-out sweep")
    parser.add_argument("--saline", type=float, help="saline concentration, g/L")
    parser.add_argument("--temp", type=float, help="water temperature, C")
    parser.add_argument("--fill", type=float, help="fill depth, mm")
    parser.add_argument("--grounding", default="unknown")
    parser.add_argument("--electrode-map", default="E1 = marked nail, clockwise viewed from above")
    parser.add_argument("--operator", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--scans-root", type=Path, default=Path("scans"))
    parser.add_argument("--yes", action="store_true", help="do not wait for Enter between positions")
    args = parser.parse_args(argv)

    def ints(text: str) -> tuple[int, ...]:
        return tuple(int(x) for x in text.split(",") if x.strip())

    plan = series(args.positions)
    blind = ints(args.blind)
    settings = UiSettings(
        port="DEMO" if args.demo else args.port, pattern="adjacent", current_range="high",
        dac=args.dac, settle_ms=args.settle, samples=args.samples,
        warmup_frames=args.warmup, frames=args.frames,
        absolute_exclude_electrodes=ints(args.exclude),
    ).validate()
    unexcluded = replace(settings, absolute_exclude_electrodes=())
    protocol, _ = unified.protocol_and_command(settings.pattern)
    eit_mesh, _ = base.create_solver(protocol)

    baseline_frames: list | None = None
    baseline_id = ""
    if args.baseline:
        run_dir = args.scans_root / "runs" / args.baseline
        baseline_frames = survey.load_frames(run_dir)
        baseline_id = args.baseline

    out = Path("exports") / f"position-series-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS).writeheader()

    log = run_record.SessionLog(args.scans_root)
    log.banner(f"position series: {len(plan)} positions x {args.runs} runs")

    log_lock = threading.Lock()

    def say(message: str) -> None:
        with log_lock:
            print(message, flush=True)
            log.write(message)

    def banner(message: str) -> None:
        with log_lock:
            log.banner(message)

    def analyse(position, repeat, mode, recorder, frames, baseline_frames, baseline_id) -> bool:
        """Solve, save and report one run. Runs on the analysis thread, so the
        next run captures meanwhile; returns True if a target was not located."""
        row = {key: None for key in SUMMARY_COLUMNS}
        row.update(position=position.key, repeat=repeat, run_id=recorder.run_id,
                   headline=mode, blind="yes" if is_blind(position, blind) else "no",
                   excluded=" ".join(f"E{n}" for n in settings.absolute_exclude_electrodes))
        lines = []

        # ADR-0070: the unexcluded solve first, then the sweep.
        raw, _, raw_report = absolute.evaluate(frames, unexcluded)
        row["unexcluded_gate"] = "pass" if raw_report.passed else "; ".join(raw_report.reasons)
        row["unexcluded_misfit_percent"] = raw.residual_percent if raw else None
        lines.append(f"unexcluded: {row['unexcluded_gate']}, misfit {_fmt(row['unexcluded_misfit_percent'])} %")
        if not args.no_sweep:
            sweep = [(n, m) for n, m in leave_one_out(frames, settings) if m is not None]
            if sweep:
                best = min(sweep, key=lambda item: item[1])
                row["sweep_best"], row["sweep_best_misfit_percent"] = f"E{best[0]}", best[1]
            lines.append("leave-one-out misfit %: " + ", ".join(f"E{n} {m:.1f}" for n, m in sweep))

        result, noise, report = absolute.evaluate(frames, settings)
        row["excluded_gate"] = "pass" if report.passed else "; ".join(report.reasons)
        if result is not None:
            row["excluded_misfit_percent"] = result.residual_percent
            row["excluded_sigma0_ms"] = result.sigma0
            row["absolute_trough_deg"] = result.trough_angle_deg
            row["absolute_trough_error_deg"] = angle_error(result.trough_angle_deg, position, eit_mesh)
            row["absolute_trough_electrodes"] = absolute.trough_index_fields(result)["absolute_trough_electrodes"]
            absolute.save_absolute(
                absolute.Attempt(settings, frames, result, noise, report),
                recorder.path / "absolute.png", recorder.path / "absolute.npz",
                title=f"{recorder.run_id} (absolute)", thickness_mm=None,
            )
            lines.append(f"excluded: {row['excluded_gate']}, {result.trough_text()}"
                         + absolute.excluded_text(settings, result))

        diff = control = None
        if baseline_frames is not None and not position.is_empty:
            diff = reconstruction.reconstruct(baseline_frames, frames, settings)
            control = reconstruction.split_half_control(baseline_frames, settings)
            trough_deg = resistive_trough_deg(diff.values, eit_mesh)
            row["baseline_run_id"] = baseline_id
            row["difference_trough_deg"] = trough_deg
            row["difference_trough_error_deg"] = angle_error(trough_deg, position, eit_mesh)
            if control is not None:
                row["difference_significance"] = reconstruction.significance(diff, control)
            reconstruction.save_reconstruction(
                diff, settings, recorder.path / "reconstruction.png",
                recorder.path / "reconstruction.npz",
                title=f"{recorder.run_id} vs {baseline_id}", control=control,
            )
            recorder.write_text("reconstruction.txt", f"baseline: {baseline_id}\ntarget: {position.target}\n")
            lines.append(f"difference vs {baseline_id}: resistive trough {trough_deg:.0f} deg (|peak| {diff.peak_angle_deg:.0f}), "
                         f"significance {_fmt(row['difference_significance'])}")
        row["located"] = located(row, position)

        summary = capture_view.session_summary(frames)
        recorder.write_text(
            "summary.txt",
            capture_view.format_session_summary(summary) + "\n" + "\n".join(lines) + "\n",
        )
        run_record.append_index_row(args.scans_root, recorder.index_row(
            outcome="complete",
            peak_value=result.peak_value if result else None,
            peak_angle_deg=result.peak_angle_deg if result else None,
            significance=report.significance,
            reciprocity_median_percent=report.reciprocity_percent,
            noise_median_percent=report.noise_relative_percent,
            absolute_sigma0_ms=result.sigma0 if result else None,
            absolute_misfit_percent=result.residual_percent if result else None,
            absolute_gate=row["excluded_gate"],
            **absolute.trough_index_fields(result),
        ))
        recorder.close()
        with summary_path.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS).writerow(
                {key: _fmt(value) for key, value in row.items()})

        say(f"[{position.key} {repeat}/{args.runs}] {recorder.run_id} ({mode}) "
            f"{row['located'] or ''}\n  " + "\n  ".join(lines))
        if mode != "baseline" and row["located"] != "yes" and position.electrodes:
            return True
        return False

    acquisition = DemoAcquisition() if args.demo else SerialAcquisition()
    acquisition.connect(settings)
    acquisition.configure(settings)
    pool = ThreadPoolExecutor(max_workers=1)
    pending = []
    try:
        for position in plan:
            mode = headline(position, blind)
            if not args.yes:
                input(f"\nSet up: {position.target} ({mode}) and press Enter...")
            banner(f"position {position.key} ({mode})")
            for repeat in range(1, args.runs + 1):
                conditions = run_record.Conditions(
                    medium="saline tank", specimen_id="saline-tank",
                    target_description=position.target, tank_contents=position.target,
                    saline_g_per_l=args.saline, water_temp_c=args.temp, fill_depth_mm=args.fill,
                    grounding=args.grounding, electrode_map=args.electrode_map,
                    operator=args.operator,
                    notes=f"{args.notes} position series {position.key} run {repeat}/{args.runs}".strip(),
                    extra={"position": position.key, "headline": mode},
                )
                # Warm up after the wood is moved, not between repeats of an
                # untouched position: capture is continuous at fixed settings.
                if repeat == 1:
                    for _ in range(settings.warmup_frames):
                        acquisition.capture_frame()
                recorder = run_record.create_run(
                    args.scans_root, f"saline-pos-{position.key.replace('+', '-')}",
                    conditions=conditions, settings=settings_to_dict(settings),
                )
                frames = []
                for _ in range(settings.frames):
                    frame = acquisition.capture_frame()
                    recorder.write_frame(frame)
                    frames.append(frame)

                # Analysis overlaps the next capture; one worker keeps runs in order.
                future = pool.submit(
                    analyse, position, repeat, mode, recorder, frames, baseline_frames, baseline_id)
                future.add_done_callback(
                    lambda f, run=recorder.run_id: f.exception() and say(f"{run}: analysis failed: {f.exception()!r}"))
                pending.append(future)
                # The difference reference is the last run of the opening empty tank.
                if position.key == "empty-first":
                    baseline_frames, baseline_id = frames, recorder.run_id
    except KeyboardInterrupt:
        say("series interrupted by operator")
    finally:
        acquisition.close()
        pool.shutdown(wait=True)
        say(f"Summary: {summary_path}")
        log.close()
    # A run whose analysis failed is recorded but unscored: count it as not located.
    failures = sum(1 for future in pending if future.exception() is not None or future.result())
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
