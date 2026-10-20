"""Tests for the device verification report (verify_device.py).

The report is a claim-making tool, so what matters is that it cannot emit a pass without
the control it depends on, and that it counts the placement it is asked about.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import phase3a_reconstruct as base
import verify_device
from tree_ert import ssim


class PhysicsTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mesh, cls.solver = base.create_solver(base.build_adjacent_protocol())

    def test_template_lands_where_the_block_is(self) -> None:
        blocks = ssim.blocks_for(["E7"], self.mesh)
        template = verify_device.physics_template(blocks, self.mesh, self.solver)
        angle = template.argmax()
        row, col = np.unravel_index(angle, template.shape)
        xx, yy, _ = ssim.grid_coordinates()
        recovered = float(np.degrees(np.arctan2(yy[row, col], xx[row, col])) % 360.0)
        self.assertLess(min(abs(recovered - blocks[0].angle_deg),
                            360.0 - abs(recovered - blocks[0].angle_deg)), 10.0)

    def test_two_blocks_produce_two_lobes(self) -> None:
        one = verify_device.physics_template(ssim.blocks_for(["E7"], self.mesh),
                                             self.mesh, self.solver)
        two = verify_device.physics_template(ssim.blocks_for(["E1", "E7"], self.mesh),
                                             self.mesh, self.solver)
        # a pair must be wider than a single block, and not merely brighter
        yy, xx = np.nonzero(one > 0.5 * one.max())
        spread_one = float(np.hypot(xx.max() - xx.min(), yy.max() - yy.min()))
        yy, xx = np.nonzero(two > 0.5 * two.max())
        spread_two = float(np.hypot(xx.max() - xx.min(), yy.max() - yy.min()))
        self.assertGreater(spread_two, spread_one)


class ReportTests(unittest.TestCase):
    """Builds a tiny synthetic series and checks the report's accounting."""

    def _series(self, root: Path, n_runs: int = 3) -> Path:
        series = root / "series"
        (series / "runs").mkdir(parents=True)
        mesh, solver = base.create_solver(base.build_adjacent_protocol())
        c = np.mean(mesh.node[mesh.element], axis=1)[:, :2]
        hx = ssim.BLOCK_FOOTPRINT_MM[0] / 2 / ssim.ELECTRODE_RING_RADIUS_MM
        hy = ssim.BLOCK_FOOTPRINT_MM[1] / 2 / ssim.ELECTRODE_RING_RADIUS_MM
        near = ssim.NEAR_RADIUS_MM / ssim.ELECTRODE_RING_RADIUS_MM

        perm = np.ones(len(mesh.element))
        perm[(np.abs(c[:, 0] - near) <= hx) & (np.abs(c[:, 1]) <= hy)] = 0.08
        baseline = solver.fwd.solve_eit(perm=1.0)
        target = solver.fwd.solve_eit(perm=perm)
        image = base.reconstruct_difference(baseline, target, solver, None)

        # The control must be a genuinely DIFFERENT image, not a scaled copy: NCC is
        # scale-invariant and `resistive_image` normalises to peak, so a control built as
        # 0.02 * image scores exactly the same as the detection. Rotating the block to
        # the far side gives a control that actually looks like "nothing at E7".
        away = np.ones(len(mesh.element))
        away[(np.abs(c[:, 0] + near) <= hx) & (np.abs(c[:, 1]) <= hy)] = 0.08
        control = base.reconstruct_difference(baseline, solver.fwd.solve_eit(perm=away),
                                              solver, None)

        for i in range(n_runs):
            run = series / "runs" / f"20260101-0000{i}0-synthetic"
            run.mkdir()
            np.savez(run / "reconstruction.npz",
                     values=image,
                     control_values=control,
                     baseline=baseline, target=target)
            (run / "conditions.json").write_text(json.dumps({
                "conditions": {"target_description": "wood at e7"},
            }), encoding="utf-8")
        return series

    def test_report_runs_and_reports_every_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            series = self._series(Path(tmp), n_runs=3)
            code = verify_device.verify(series)
            self.assertEqual(code, 0)

    def test_a_scaled_copy_of_the_detection_is_indistinguishable(self) -> None:
        """Why the control has to be a different image, not a quieter one.

        NCC is scale-invariant and `resistive_image` normalises to peak, so a control
        that is simply a fainter copy of the detection scores *identically*. Any
        verification protocol whose control is "the same thing, less strong" therefore
        proves nothing about NCC at all.
        """
        with tempfile.TemporaryDirectory() as tmp:
            series = self._series(Path(tmp), n_runs=1)
            mesh, _ = base.create_solver(base.build_adjacent_protocol())
            run = next((series / "runs").iterdir())
            with np.load(run / "reconstruction.npz", allow_pickle=True) as h:
                values = h["values"]
            labels = ssim.parse_target("wood at e7")
            quiet = ssim.score(values * 0.02, mesh, labels)
            loud = ssim.score(values, mesh, labels)
            self.assertAlmostEqual(quiet.ncc, loud.ncc, places=6)

    def test_a_control_elsewhere_scores_lower_than_the_detection(self) -> None:
        """The margin only means something because the control is a different image."""
        with tempfile.TemporaryDirectory() as tmp:
            series = self._series(Path(tmp), n_runs=1)
            mesh, solver = base.create_solver(base.build_adjacent_protocol())
            run = next((series / "runs").iterdir())
            with np.load(run / "reconstruction.npz", allow_pickle=True) as h:
                npz = {k: h[k] for k in h.files}
            labels = ssim.parse_target("wood at e7")
            template = verify_device.physics_template(ssim.blocks_for(labels, mesh),
                                                      mesh, solver)
            found = ssim.score(npz["values"], mesh, labels, template=template)
            empty = ssim.score(npz["control_values"], mesh, labels, template=template)
            self.assertGreater(found.ncc, empty.ncc)
            self.assertGreater(found.dice, empty.dice)

    def test_missing_control_is_skipped_not_scored_against_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            series = self._series(Path(tmp), n_runs=2)
            run = next((series / "runs").iterdir())
            with np.load(run / "reconstruction.npz", allow_pickle=True) as h:
                npz = {k: h[k] for k in h.files}
            np.savez(run / "reconstruction.npz", values=npz["values"],
                     baseline=npz["baseline"], target=npz["target"])
            # must not crash, and must not count the control-less run
            self.assertEqual(verify_device.verify(series), 0)


if __name__ == "__main__":
    unittest.main()
