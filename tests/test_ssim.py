"""SSIM scoring against block masks (ADR-0045), on synthetic images; no board, no recorded runs."""

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


class NccTests(unittest.TestCase):
    """NCC is reported alongside SSIM, not instead of it (ADR-0047)."""

    def setUp(self) -> None:
        self.mesh = mesh()
        _, _, self.inside = ssim.grid_coordinates()

    def test_identical_images_correlate_perfectly(self) -> None:
        image = np.random.default_rng(1).random(self.inside.shape)
        self.assertAlmostEqual(ssim.ncc(image, image, self.inside), 1.0, places=6)

    def test_inverted_image_anticorrelates(self) -> None:
        image = np.random.default_rng(2).random(self.inside.shape)
        self.assertAlmostEqual(ssim.ncc(image, -image, self.inside), -1.0, places=6)

    def test_brightness_does_not_change_the_score(self) -> None:
        # The reason NCC is here: SSIM's luminance term punishes a dim but
        # correctly placed blob, which this reconstruction produces routinely.
        image = np.random.default_rng(3).random(self.inside.shape)
        self.assertAlmostEqual(ssim.ncc(image, 0.2 * image, self.inside), 1.0, places=6)

    def test_flat_image_scores_zero_rather_than_nan(self) -> None:
        image = np.random.default_rng(4).random(self.inside.shape)
        flat = np.zeros_like(image)
        self.assertEqual(ssim.ncc(image, flat, self.inside), 0.0)
        self.assertEqual(ssim.ncc(flat, flat, self.inside), 0.0)

    def test_wrong_place_scores_near_zero(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]

        def blob_at(x: float, y: float) -> np.ndarray:
            return -np.exp(-((centres[:, 0] - x) ** 2 + (centres[:, 1] - y) ** 2) / 0.02)

        mask = ssim.block_mask(ssim.blocks_for(["E7"], self.mesh))
        region = ssim.score_region(mask)
        right = ssim.ncc(ssim.resistive_image(ssim.rasterise(blob_at(0.8, 0.0), self.mesh)), mask, region)
        wrong = ssim.ncc(ssim.resistive_image(ssim.rasterise(blob_at(-0.8, 0.0), self.mesh)), mask, region)
        self.assertGreater(right, 0.5)
        self.assertLess(wrong, 0.3)

    def test_dice_is_zero_for_two_empty_images(self) -> None:
        flat = np.zeros(self.inside.shape)
        self.assertEqual(ssim.dice(flat, flat, self.inside), 0.0)

    def test_dice_is_one_for_identical_lobes(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]
        blob = -np.exp(-((centres[:, 0] - 0.8) ** 2 + (centres[:, 1]) ** 2) / 0.02)
        image = ssim.resistive_image(ssim.rasterise(blob, self.mesh))
        self.assertAlmostEqual(ssim.dice(image, image, ssim.score_region(image > 0.1)), 1.0, places=6)

    def test_score_reports_the_new_metrics(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]
        blob = -np.exp(-((centres[:, 0] - 0.8) ** 2 + (centres[:, 1]) ** 2) / 0.02)
        result = ssim.score(blob, self.mesh, ["E7"])
        self.assertIsNotNone(result.ncc)
        self.assertIsNotNone(result.dice)
        self.assertGreater(result.ncc, 0.5)

    def test_an_explicit_template_is_used_for_ncc(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]
        blob = -np.exp(-((centres[:, 0] - 0.8) ** 2 + (centres[:, 1]) ** 2) / 0.02)
        expected = ssim.block_mask(ssim.blocks_for(["E7"], self.mesh))
        with_mask = ssim.score(blob, self.mesh, ["E7"]).ncc
        with_template = ssim.score(blob, self.mesh, ["E7"], template=expected).ncc
        self.assertAlmostEqual(with_mask, with_template, places=6)


if __name__ == "__main__":
    unittest.main()
