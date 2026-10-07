"""SSIM scoring against block masks (ADR-0048), on synthetic images; no board, no recorded runs."""

from __future__ import annotations

import unittest

import numpy as np

import phase3a_reconstruct as base
from tree_ert import ssim


def mesh():
    eit_mesh, _ = base.create_solver(base.build_adjacent_protocol())
    return eit_mesh


class ParseTargetTests(unittest.TestCase):
    def test_forms_used_on_2026_10_02(self) -> None:
        cases = {
            "wood at e5": ["E5"],
            "wood block at 10": ["E10"],
            "wood at 4": ["E4"],
            "A: near E9 (block centre ~128 mm from tank centre, upright, 23 mm face to centre)": ["E9"],
            "wood at e1 and e7": ["E1", "E7"],
            "wood at centre": ["centre"],
            "wood at center and e7": ["centre", "E7"],
            "empty": [],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(ssim.parse_target(text), expected)


class GeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mesh = mesh()

    def test_electrode_angles_come_from_the_mesh(self) -> None:
        # PyEIT: E1 at 180 deg, clockwise. E4 top, E7 right, E10 bottom.
        expected = {"E1": 180.0, "E4": 90.0, "E7": 0.0, "E10": 270.0}
        for label, angle in expected.items():
            block = ssim.blocks_for([label], self.mesh)[0]
            diff = ((block.angle_deg - angle + 180) % 360) - 180
            self.assertAlmostEqual(diff, 0.0, delta=1.0, msg=label)
            self.assertAlmostEqual(block.radius, 0.8, places=6)

    def test_mask_lands_on_the_block(self) -> None:
        mask = ssim.block_mask(ssim.blocks_for(["E7"], self.mesh))
        xx, yy, _ = ssim.grid_coordinates()
        self.assertGreater(mask.sum(), 0)
        self.assertAlmostEqual(float(xx[mask > 0].mean()), 0.8, delta=0.05)
        self.assertAlmostEqual(float(yy[mask > 0].mean()), 0.0, delta=0.05)


class SsimTests(unittest.TestCase):
    def test_identical_images_score_one(self) -> None:
        _, _, inside = ssim.grid_coordinates()
        image = np.random.default_rng(0).random(inside.shape)
        self.assertAlmostEqual(ssim.ssim(image, image, inside), 1.0, places=6)

    def test_right_place_beats_wrong_place(self) -> None:
        eit_mesh = mesh()
        centres = np.mean(eit_mesh.node[eit_mesh.element], axis=1)[:, :2]

        def blob_at(x: float, y: float) -> np.ndarray:
            return -np.exp(-((centres[:, 0] - x) ** 2 + (centres[:, 1] - y) ** 2) / 0.02)

        right = ssim.score(blob_at(0.8, 0.0), eit_mesh, ["E7"])
        wrong = ssim.score(blob_at(-0.8, 0.0), eit_mesh, ["E7"])
        self.assertGreater(right.ssim_raw, wrong.ssim_raw)
        self.assertGreater(right.ssim_blurred, wrong.ssim_blurred)
        self.assertLess(abs(right.blocks[0].angle_error_deg), 10.0)

    def test_conductive_lobe_is_not_a_wooden_block(self) -> None:
        values_grid = np.ones((ssim.GRID, ssim.GRID))
        self.assertEqual(ssim.resistive_image(values_grid).max(), 0.0)

    def test_empty_target_refuses(self) -> None:
        with self.assertRaises(ValueError):
            ssim.score(np.zeros(10), mesh(), [])


if __name__ == "__main__":
    unittest.main()
