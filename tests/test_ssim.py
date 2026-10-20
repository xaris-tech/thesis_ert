"""SSIM scoring against block masks (ADR-0048), on synthetic images; no board, no recorded runs."""

from __future__ import annotations

import unittest

import numpy as np

import phase3a_reconstruct as base
from tree_ert import ssim


def mesh():
    eit_mesh, _ = base.create_solver(base.build_adjacent_protocol())
    return eit_mesh


# Where the block actually sits, in the units the mesh uses (electrodes at radius 1.0).
# Derived rather than hard-coded so a geometry correction cannot leave these stale.
NEAR = ssim.NEAR_RADIUS_MM / ssim.ELECTRODE_RING_RADIUS_MM
FAR = -NEAR


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
            self.assertAlmostEqual(block.radius, NEAR, places=6)

    def test_mask_lands_on_the_block(self):
        mask = ssim.block_mask(ssim.blocks_for(["E7"], self.mesh))
        xx, yy, _ = ssim.grid_coordinates()
        self.assertGreater(mask.sum(), 0)
        self.assertAlmostEqual(float(xx[mask > 0].mean()), NEAR, delta=0.05)
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

        right = ssim.score(blob_at(NEAR, 0.0), eit_mesh, ["E7"])
        wrong = ssim.score(blob_at(FAR, 0.0), eit_mesh, ["E7"])
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
    """NCC is reported alongside SSIM, not instead of it (ADR-0050)."""

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
        right = ssim.ncc(ssim.resistive_image(ssim.rasterise(blob_at(NEAR, 0.0), self.mesh)), mask, region)
        wrong = ssim.ncc(ssim.resistive_image(ssim.rasterise(blob_at(FAR, 0.0), self.mesh)), mask, region)
        self.assertGreater(right, 0.5)
        self.assertLess(wrong, 0.3)

    def test_dice_is_zero_for_two_empty_images(self) -> None:
        flat = np.zeros(self.inside.shape)
        self.assertEqual(ssim.dice(flat, flat, self.inside), 0.0)

    def test_dice_is_one_for_identical_lobes(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]
        blob = -np.exp(-((centres[:, 0] - NEAR) ** 2 + (centres[:, 1]) ** 2) / 0.02)
        image = ssim.resistive_image(ssim.rasterise(blob, self.mesh))
        self.assertAlmostEqual(ssim.dice(image, image, ssim.score_region(image > 0.1)), 1.0, places=6)

    def test_score_reports_the_new_metrics(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]
        blob = -np.exp(-((centres[:, 0] - NEAR) ** 2 + (centres[:, 1]) ** 2) / 0.02)
        result = ssim.score(blob, self.mesh, ["E7"])
        self.assertIsNotNone(result.ncc)
        self.assertIsNotNone(result.dice)
        self.assertGreater(result.ncc, 0.5)

    def test_an_explicit_template_is_used_for_ncc(self) -> None:
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)[:, :2]
        blob = -np.exp(-((centres[:, 0] - NEAR) ** 2 + (centres[:, 1]) ** 2) / 0.02)
        expected = ssim.block_mask(ssim.blocks_for(["E7"], self.mesh))
        with_mask = ssim.score(blob, self.mesh, ["E7"]).ncc
        with_template = ssim.score(blob, self.mesh, ["E7"], template=expected).ncc
        self.assertAlmostEqual(with_mask, with_template, places=6)


class CentroidAngleTests(unittest.TestCase):
    """The lobe centroid is the better angle estimator (ADR-0051).

    The single strongest pixel is unreliable on the diffuse lobes this solver
    produces: on the 2026-10-02 series it put E6 18.2 deg off where the centroid
    puts it 3.7 deg off, and it read 20 of 24 placements within 10 deg against the
    centroid's 24 of 24.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.mesh = mesh()
        cls.centres = np.mean(cls.mesh.node[cls.mesh.element], axis=1)[:, :2]

    def blob_at(self, x: float, y: float, scale: float = 0.02) -> np.ndarray:
        d2 = (self.centres[:, 0] - x) ** 2 + (self.centres[:, 1] - y) ** 2
        return -np.exp(-d2 / scale)

    def test_a_compact_artefact_still_drags_the_centroid(self) -> None:
        # Documents the known limitation rather than pretending it away. The lobe is the
        # connected component containing the *strongest* pixel, so a spike brighter than
        # the block becomes the lobe and the centroid follows it. No centroid estimator
        # avoids this: the artefact is by definition the strongest signal. The defence
        # is reporting the score alongside the argmax so the disagreement is visible --
        # which is why BlockScore keeps both.
        xx, yy, inside = ssim.grid_coordinates()
        lobe = np.exp(-(((xx - NEAR) ** 2 + yy**2) / 0.02))
        spike_r, spike_a = 0.93, np.deg2rad(35.0)
        spike = 6.0 * np.exp(-(
            ((xx - spike_r * np.cos(spike_a)) ** 2 + (yy - spike_r * np.sin(spike_a)) ** 2) / 0.0008))
        values = np.where(inside, -(lobe + spike), 0.0)

        blocks = ssim.blocks_for(["E7"], self.mesh)
        scored = ssim.score_blocks(values, blocks)[0]

        self.assertGreater(scored.peak_radius, 0.85, "spike wins the argmax")
        # both estimates follow the spike -- the point of the test is that this is known
        self.assertGreater(abs(scored.angle_error_deg), 20.0)
        self.assertGreater(abs(scored.centroid_angle_error_deg), 20.0)

    def test_centroid_is_insensitive_to_the_lobe_threshold(self) -> None:
        # The reason this estimator replaced the windowed one: a threshold between 0.5
        # and 0.6 moves an answer by 1-2 deg, where the window choice was worth 12.3 deg.
        blocks = ssim.blocks_for(["E7"], self.mesh)
        values = self.blob_at(NEAR * np.cos(np.deg2rad(20)), NEAR * np.sin(np.deg2rad(20)))
        grid = ssim.rasterise(values, self.mesh)

        original = ssim.LOBE_THRESHOLD
        try:
            answers = {}
            for threshold in (0.5, 0.6):
                ssim.LOBE_THRESHOLD = threshold
                got = ssim.score_blocks(grid, blocks)[0].centroid_angle_error_deg
                self.assertIsNotNone(got)
                answers[threshold] = abs(got)
        finally:
            ssim.LOBE_THRESHOLD = original
        self.assertLess(abs(answers[0.5] - answers[0.6]), 2.5)

    def test_centroid_error_is_reported_for_a_clean_blob(self) -> None:
        blocks = ssim.blocks_for(["E7"], self.mesh)
        scored = ssim.score_blocks(ssim.rasterise(self.blob_at(NEAR, 0.0), self.mesh), blocks)[0]
        self.assertLess(abs(scored.centroid_angle_error_deg), 2.0)
        self.assertAlmostEqual(scored.centroid_radius, NEAR, delta=0.06)

    def test_two_blocks_do_not_collapse_to_the_tank_centre(self) -> None:
        # The reason the centroid is wedge-restricted: over the whole disc these two
        # lobes merge and the centroid falls to radius 0.03.
        angle_a, angle_b = np.deg2rad(0.0), np.deg2rad(180.0)
        values = self.blob_at(NEAR * np.cos(angle_a), 0.8 * np.sin(angle_a))
        values = values + self.blob_at(NEAR * np.cos(angle_b), NEAR * np.sin(angle_b))
        blocks = ssim.blocks_for(["E1", "E7"], self.mesh)
        scored = ssim.score_blocks(ssim.rasterise(values, self.mesh), blocks)
        for block in scored:
            self.assertGreater(block.centroid_radius, 0.5, block.label)
            self.assertLess(abs(block.centroid_angle_error_deg), 5.0, block.label)

    def test_a_flat_image_reports_no_centroid(self) -> None:
        blocks = ssim.blocks_for(["E7"], self.mesh)
        scored = ssim.score_blocks(np.zeros((ssim.GRID, ssim.GRID)), blocks)[0]
        self.assertIsNone(scored.centroid_angle_deg)
        self.assertIsNone(scored.centroid_angle_error_deg)

    def test_max_abs_centroid_angle_error_property(self) -> None:
        values = self.blob_at(NEAR, 0.0)
        result = ssim.score(values, self.mesh, ["E7"])
        self.assertIsNotNone(result.max_abs_centroid_angle_error)
        self.assertLess(result.max_abs_centroid_angle_error, 5.0)


if __name__ == "__main__":
    unittest.main()
