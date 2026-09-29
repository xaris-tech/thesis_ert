"""Intact-disc survey: S_noise, S_between and S_defect from recorded runs (ADR-0035).

Either name the runs in a manifest,

    run_id,specimen_id,state,note
    20260929-153440-coconut-620-dry-32-samples,disc-01,intact,
    20260929-162756-coconut-620-dry-32-samples,disc-01,defect,holes E7-E9
    20260929-165833-coconut-620-dry-32-samples,disc-01,excluded,E8 contact lost

or let the runs name themselves from their conditions (runs taken under the
ADR-0037 naming gate): a run with a target description is a defect run.

    .venv\\Scripts\\python.exe disc_survey.py --manifest survey.csv
    .venv\\Scripts\\python.exe disc_survey.py --from-conditions --medium "cut disc"
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from tree_ert import survey


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path, help="CSV: run_id,specimen_id,state[,note]")
    source.add_argument(
        "--from-conditions",
        action="store_true",
        help="group runs by the specimen ID recorded in their conditions",
    )
    parser.add_argument("--scans-root", type=Path, default=Path("scans"))
    parser.add_argument("--medium", help="with --from-conditions: only runs of this medium")
    parser.add_argument(
        "--out",
        type=Path,
        help="directory for survey.txt and survey.json (default exports/survey-<stamp>)",
    )
    args = parser.parse_args(argv)

    if args.manifest:
        manifest = survey.read_manifest(args.manifest)
    else:
        manifest = survey.manifest_from_conditions(args.scans_root, medium=args.medium)
    if not manifest:
        print("No runs to survey.", file=sys.stderr)
        return 1

    report = survey.run_survey(args.scans_root, manifest)
    out = args.out or Path("exports") / f"survey-{datetime.now():%Y%m%d-%H%M%S}"
    text_path, json_path = survey.save_report(report, out)
    print(survey.format_report(report))
    print(f"Saved {text_path} and {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
