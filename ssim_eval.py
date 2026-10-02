"""Score a saline-tank series by SSIM against block masks (ADR-0044, ADR-0045).

Offline: reads recorded runs, no board needed.

    .venv\\Scripts\\python.exe ssim_eval.py ssim/saline-tank-2026-10-02
    .venv\\Scripts\\python.exe ssim_eval.py ssim/saline-tank-2026-10-02 --since 20261002-165444

Targets come from the series ``manifest.csv`` (rows with role ``target`` whose
note does not say ``superseded``), plus, with ``--since``, every later run in
``scans/runs`` that has a reconstruction. Each target is reconstructed against
the baseline its own ``reconstruction.txt`` names, using the same code path as
the UI. Writes ``ssim_results.csv`` and ``ssim_contact_sheet.png`` into the
series directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert import ssim
from tree_ert.reconstruction import reconstruct, require_compatible
from tree_ert.settings import UiSettings
from tree_ert.survey import load_frames

RESULT_COLUMNS = [
    "run_id", "baseline_run", "target", "blocks", "ssim_raw", "ssim_blurred",
    "max_abs_angle_error_deg", "angle_errors_deg", "peak_radius", "true_radius",
]


def find_run(run_id: str, series: Path, scans_runs: Path) -> Path:
    for root in (series / "runs", scans_runs):
        if (root / run_id).is_dir():
            return root / run_id
    raise FileNotFoundError(f"run {run_id} not found under {series / 'runs'} or {scans_runs}")


def baseline_of(run_dir: Path) -> str | None:
    text_path = run_dir / "reconstruction.txt"
    if not text_path.exists():
        return None
    match = re.search(r"baseline run: (\S+)", text_path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def target_runs(series: Path, scans_runs: Path, since: str | None) -> list[str]:
    ids: list[str] = []
    listed: set[str] = set()  # every manifest row, excluded ones too, so --since cannot re-admit them
    manifest = series / "manifest.csv"
    if manifest.exists():
        with manifest.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                listed.add(row["run_id"])
                if row["role"] == "target" and "superseded" not in row.get("note", "").lower():
                    ids.append(row["run_id"])
    if since:
        for run_dir in sorted(scans_runs.iterdir()):
            if run_dir.name > since and run_dir.name not in listed and baseline_of(run_dir):
                ids.append(run_dir.name)
    return ids


def evaluate(run_dir: Path, baseline_dir: Path, psf_sigma: float):
    run = json.loads((run_dir / "conditions.json").read_text(encoding="utf-8"))
    base_run = json.loads((baseline_dir / "conditions.json").read_text(encoding="utf-8"))
    require_compatible(base_run["settings"], run["settings"])
    target = run["conditions"].get("target_description") or run["conditions"].get("tank_contents") or ""
    labels = ssim.parse_target(target)
    settings = UiSettings(pattern=run["settings"]["pattern"])
    result = reconstruct(load_frames(baseline_dir), load_frames(run_dir), settings)
    protocol, _ = unified.protocol_and_command(settings.pattern)
    eit_mesh, _ = base.create_solver(protocol)
    return target, labels, ssim.score(result.values, eit_mesh, labels, psf_sigma), result, eit_mesh


def _fmt(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def contact_sheet(entries, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not entries:
        return
    fig, axes = plt.subplots(len(entries), 3, figsize=(7.5, 2.4 * len(entries)), squeeze=False)
    for row, (run_id, labels, score, result, eit_mesh) in enumerate(entries):
        grid = ssim.rasterise(result.values, eit_mesh)
        mask = ssim.block_mask(ssim.blocks_for(labels, eit_mesh))
        panels = [
            (ssim.resistive_image(grid), f"{run_id[9:15]} {'+'.join(labels)}"),
            (mask, f"mask  SSIM {score.ssim_raw:.2f}"),
            (ssim.blur(mask), f"blurred  SSIM {score.ssim_blurred:.2f}"),
        ]
        for col, (image, title) in enumerate(panels):
            ax = axes[row][col]
            ax.imshow(image, extent=(-1, 1, -1, 1), cmap="viridis", vmin=0, vmax=1)
            ax.add_patch(matplotlib.patches.Circle((0, 0), 1, fill=False, color="w", lw=0.8))
            ax.set_title(title, fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("series", type=Path, help="series directory, e.g. ssim/saline-tank-2026-10-02")
    parser.add_argument("--scans-runs", type=Path, default=Path("scans/runs"))
    parser.add_argument("--since", help="also score every later run in scans/runs that has a reconstruction")
    parser.add_argument("--psf-sigma", type=float, default=ssim.PSF_SIGMA, help="mask blur, in tank radii")
    args = parser.parse_args(argv)

    rows, entries = [], []
    for run_id in target_runs(args.series, args.scans_runs, args.since):
        run_dir = find_run(run_id, args.series, args.scans_runs)
        baseline_id = baseline_of(run_dir)
        if not baseline_id:
            print(f"{run_id}: no baseline named in reconstruction.txt, skipped", file=sys.stderr)
            continue
        try:
            target, labels, score, result, eit_mesh = evaluate(
                run_dir, find_run(baseline_id, args.series, args.scans_runs), args.psf_sigma
            )
        except Exception as error:  # one bad run must not lose the rest of the series
            print(f"{run_id}: {error}", file=sys.stderr)
            continue
        errors = [b.angle_error_deg for b in score.blocks if b.angle_error_deg is not None]
        rows.append({
            "run_id": run_id,
            "baseline_run": baseline_id,
            "target": target,
            "blocks": "+".join(labels),
            "ssim_raw": _fmt(score.ssim_raw),
            "ssim_blurred": _fmt(score.ssim_blurred),
            "max_abs_angle_error_deg": _fmt(score.max_abs_angle_error, 1),
            "angle_errors_deg": " ".join(f"{e:+.1f}" for e in errors),
            "peak_radius": " ".join(f"{b.peak_radius:.2f}" for b in score.blocks),
            "true_radius": " ".join(f"{b.true_radius:.2f}" for b in score.blocks),
        })
        entries.append((run_id, labels, score, result, eit_mesh))
        print(f"{run_id}  {'+'.join(labels):<10} raw {score.ssim_raw:.3f}  blurred {score.ssim_blurred:.3f}  "
              f"angle {rows[-1]['angle_errors_deg'] or '-'}")

    out = args.series / "ssim_results.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    contact_sheet(entries, args.series / "ssim_contact_sheet.png")
    if rows:
        raw = np.array([float(r["ssim_raw"]) for r in rows])
        blurred = np.array([float(r["ssim_blurred"]) for r in rows])
        print(f"\n{len(rows)} runs  SSIM raw mean {raw.mean():.3f}  blurred mean {blurred.mean():.3f}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
