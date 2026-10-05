"""Device verification report for a phantom series.

Reports the three reconstruction-fidelity metrics together, each beside the run's own
empty-tank control, so no number can be read without its null.

    python verify_device.py ssim/saline-tank-2026-10-02

What the three answer, which are not the same question:

  angular localization error   WHERE the block is. Ground truth is photographic, so
                               this is the one number that is independent of the
                               reconstruction itself.
  NCC                          does the image resemble the response this solver
                               produces for a block at that angle. The template comes
                               from the same solver, so this measures REPRODUCIBILITY,
                               not correctness -- a systematic pipeline bias would move
                               both together and cancel.
  Dice                         what fraction of the claimed lobe is where the lobe is.
                               Readable without a glossary; shares the same caveat.

Verdict per run is `detection must beat its own control`. A raw score means nothing on
its own, which is why the control column is not optional.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

import phase3a_reconstruct as base
from tree_ert import ssim

# Pass criteria. The angle threshold is a third of the 30 deg spacing between adjacent
# electrodes; the other two are "beat your own empty tank".
ANGLE_LIMIT_DEG = 10.0
BLOCK_CONTRAST = 0.08
"""Assumed conductivity ratio for the block. The metric is scale-invariant so this does
not affect NCC; it only has to be roughly right for the template's shape to be."""


def physics_template(blocks, eit_mesh, solver, contrast=BLOCK_CONTRAST):
    """Expected image for ``blocks``, simulated through this same solver.

    Using the same solver is deliberate: the template then carries the pipeline's own
    response, including its radial behaviour, so NCC measures reproducibility. It also
    means a shared bias cannot be detected this way -- that is what the photographic
    angle check is for.
    """
    centres = np.mean(eit_mesh.node[eit_mesh.element], axis=1)[:, :2]
    half_t = ssim.BLOCK_FOOTPRINT_MM[0] / 2.0 / ssim.ELECTRODE_RING_RADIUS_MM
    half_r = ssim.BLOCK_FOOTPRINT_MM[1] / 2.0 / ssim.ELECTRODE_RING_RADIUS_MM
    homogeneous = solver.fwd.solve_eit(perm=1.0)
    total = np.zeros(len(eit_mesh.element))
    for block in blocks:
        perm = np.ones(len(eit_mesh.element))
        inside = ((np.abs(centres[:, 0] - block.x) <= half_t)
                  & (np.abs(centres[:, 1] - block.y) <= half_r))
        perm[inside] = contrast
        simulated = solver.fwd.solve_eit(perm=perm)
        total = total + base.reconstruct_difference(homogeneous, simulated, solver, None)
    return ssim.resistive_image(ssim.rasterise(total, eit_mesh, ssim.GRID))


def verify(series_dir: Path, limit: float = ANGLE_LIMIT_DEG) -> int:
    runs_dir = series_dir / "runs"
    if not runs_dir.is_dir():
        print(f"no runs/ under {series_dir}", file=sys.stderr)
        return 2

    eit_mesh, solver = base.create_solver(base.build_adjacent_protocol())
    results_csv = series_dir / "ssim_results.csv"
    wanted = None
    if results_csv.is_file():
        wanted = [r["run_id"] for r in csv.DictReader(results_csv.open(encoding="utf-8"))]

    print(f"device verification -- {series_dir.name}")
    print(f"electrode ring {ssim.ELECTRODE_RING_RADIUS_MM:.0f} mm, "
          f"block at {ssim.NEAR_RADIUS_MM:.0f} mm "
          f"({ssim.NEAR_RADIUS_MM / ssim.ELECTRODE_RING_RADIUS_MM:.3f} of the ring)")
    print(f"template: simulated through this solver at contrast {BLOCK_CONTRAST}\n")

    header = (f"{'run':<26}{'blocks':<8}{'angLoc':>8}{'NCC':>7}{'ctrl':>7}{'NCCmrg':>8}"
              f"{'Dice':>7}{'ctrl':>7}{'DicMrg':>8}  verdict")
    print(header)
    print("-" * len(header))

    rows = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir() or (wanted and run_dir.name not in wanted):
            continue
        npz_path = run_dir / "reconstruction.npz"
        cond_path = run_dir / "conditions.json"
        if not npz_path.is_file() or not cond_path.is_file():
            continue
        # Copy into memory and close the handle: npz_path is opened lazily and an open
        # handle blocks cleanup on Windows, which is where verification usually runs.
        with np.load(npz_path, allow_pickle=True) as handle:
            npz = {key: handle[key] for key in handle.files}
        if "control_values" not in npz:
            continue
        conditions = json.loads(cond_path.read_text(encoding="utf-8"))["conditions"]
        labels = ssim.parse_target(conditions.get("target_description", ""))
        if not labels:
            continue

        blocks = ssim.blocks_for(labels, eit_mesh)
        template = physics_template(blocks, eit_mesh, solver)
        image = base.reconstruct_difference(
            np.asarray(npz["baseline"], float), np.asarray(npz["target"], float), solver, None)
        control = np.asarray(npz["control_values"], float)

        found = ssim.score(image, eit_mesh, labels, template=template)
        empty = ssim.score(control, eit_mesh, labels, template=template)

        angular = found.max_abs_centroid_angle_error
        angular_text = "-" if angular is None else f"{angular:.1f}"
        ncc_margin = found.ncc - empty.ncc
        dice_margin = found.dice - empty.dice

        beats_null = ncc_margin > 0 and dice_margin > 0
        angle_ok = angular is None or angular <= limit
        if angular is None:
            verdict = "PASS (no angle: centre target)"
        elif beats_null and angle_ok:
            verdict = "PASS"
        elif beats_null:
            verdict = "MARGINAL (detected, angle over limit)"
        else:
            verdict = "FAIL (does not beat its empty tank)"

        rows.append((run_dir.name, found.ncc, empty.ncc, ncc_margin,
                     found.dice, empty.dice, dice_margin, angular, verdict))
        print(f"{run_dir.name:<26}{'+'.join(b.label for b in blocks):<8}{angular_text:>8}"
              f"{found.ncc:>7.3f}{empty.ncc:>7.3f}{ncc_margin:>8.3f}"
              f"{found.dice:>7.3f}{empty.dice:>7.3f}{dice_margin:>8.3f}  {verdict}")

    if not rows:
        print("no scored runs found")
        return 2

    def column(index):
        return np.array([r[index] for r in rows], dtype=float)

    angles = column(7)
    angles = angles[~np.isnan(angles)]
    print("-" * len(header))
    print(f"{'MEDIAN':<26}{'':<8}{(np.median(angles) if angles.size else float('nan')):>8.1f}"
          f"{np.median(column(1)):>7.3f}{np.median(column(2)):>7.3f}{np.median(column(3)):>8.3f}"
          f"{np.median(column(4)):>7.3f}{np.median(column(5)):>7.3f}{np.median(column(6)):>8.3f}")
    print()
    print(f"runs scored                     {len(rows)}")
    if angles.size:
        print(f"angular localization error     median {np.median(angles):.2f} deg, "
              f"max {angles.max():.2f} deg")
        print(f"                                within {ANGLE_LIMIT_DEG:.0f} deg: "
              f"{int((angles <= limit).sum())}/{angles.size}")
    print(f"NCC beats its empty tank        {int((column(3) > 0).sum())}/{len(rows)}")
    print(f"Dice beats its empty tank       {int((column(6) > 0).sum())}/{len(rows)}")
    failures = [r for r in rows if r[8].startswith("FAIL")]
    marginal = [r for r in rows if r[8].startswith("MARGINAL")]
    print()
    print(f"verdict: {'PASS' if not failures and not marginal else 'SEE ABOVE'}"
          f"  ({len(failures)} fail, {len(marginal)} marginal)")
    print()
    print("reminder: NCC and Dice are measured against a template from this solver, so they")
    print("show reproducibility, not correctness. The angular localization error is the only")
    print("metric here with photographic ground truth.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("series", type=Path, help="series directory containing runs/")
    parser.add_argument("--angle-limit", type=float, default=ANGLE_LIMIT_DEG,
                        help=f"pass threshold in degrees (default {ANGLE_LIMIT_DEG})")
    args = parser.parse_args()
    return verify(args.series, args.angle_limit)


if __name__ == "__main__":
    raise SystemExit(main())
