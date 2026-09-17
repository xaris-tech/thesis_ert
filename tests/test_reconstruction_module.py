"""Tests for tree_ert.reconstruction.

The settings-compatibility gate and the null behaviour are the point: an image
built on incomparable data, or a blank difference read as a detection, are the
two failures this module exists to prevent.
"""

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase3a_unified_reconstruct as unified
from tree_ert import reconstruction
from tree_ert.settings import UiSettings


def settings(**overrides) -> UiSettings:
    base = UiSettings(
        port="DEMO",
        pattern="adjacent",
        current_range="high",
        dac=100,
        settle_ms=10,
        samples=4,
    )
    return replace(base, **overrides) if overrides else base


def settings_dict(**overrides) -> dict:
    data = {
        "pattern": "adjacent",
        "current_range": "high",
        "dac": 100,
        "settle_ms": 10,
        "samples": 4,
        "electrode_offset": 0,
        "electrode_reversed": False,
    }
    data.update(overrides)
    return data


def frame_from_vector(vector: np.ndarray, protocol) -> unified.UnifiedFrame:
    """Build a frame whose paired transfer resistances equal ``vector``.

    Inverts frame_to_vector: it reads -0.5 * (V_fwd/I - V_rev/I) at the
    canonical key, so a forward of -value and a reverse of +value at unit
    current reproduce the requested value exactly.
    """
    records = []
    current = 1000.0
    for ex_index, ex_pair in enumerate(protocol.ex_mat):
        i_pair = (int(ex_pair[0]), int(ex_pair[1]))
        for meas_index, meas_pair in enumerate(protocol.meas_mat[ex_index]):
            v_pair = (int(meas_pair[1]), int(meas_pair[0]))
            flat = ex_index * len(protocol.meas_mat[ex_index]) + meas_index
            value = float(vector[flat])
            mv = value * current
            records.append(
                unified.MeasurementRecord("FWD", i_pair, v_pair, -mv, current, "OK")
            )
            records.append(
                unified.MeasurementRecord(
                    "REV", (i_pair[1], i_pair[0]), v_pair, mv, current, "OK"
                )
            )
    return unified.UnifiedFrame(1, "ADJACENT", 100, 10, 4, records)


class SettingsGateTests(unittest.TestCase):
    def test_identical_settings_have_no_differences(self):
        self.assertEqual(
            reconstruction.settings_mismatch(settings_dict(), settings_dict()), []
        )

    def test_pattern_difference_is_reported_readably(self):
        differences = reconstruction.settings_mismatch(
            settings_dict(), settings_dict(pattern="opposite")
        )
        self.assertEqual(differences, ["pattern: adjacent vs opposite"])

    def test_every_measurement_setting_is_checked(self):
        for field, other in (
            ("pattern", "opposite"),
            ("current_range", "low"),
            ("dac", 200),
            ("settle_ms", 50),
            ("samples", 16),
            ("electrode_offset", 3),
            ("electrode_reversed", True),
        ):
            with self.subTest(field=field):
                differences = reconstruction.settings_mismatch(
                    settings_dict(), settings_dict(**{field: other})
                )
                self.assertTrue(any(d.startswith(field) for d in differences))

    def test_frame_counts_do_not_block_comparison(self):
        # Baselining over 5 frames and targeting over 10 is normal practice.
        self.assertEqual(
            reconstruction.settings_mismatch(
                settings_dict(frames=5, warmup_frames=20),
                settings_dict(frames=10, warmup_frames=2),
            ),
            [],
        )

    def test_a_missing_setting_counts_as_differing(self):
        # An older run that did not record the setting cannot be SHOWN to be
        # comparable, and assuming it was is the whole problem.
        partial = settings_dict()
        del partial["samples"]
        differences = reconstruction.settings_mismatch(partial, settings_dict())
        self.assertEqual(differences, ["samples: <missing> vs 4"])

    def test_require_compatible_raises_with_the_differences_attached(self):
        with self.assertRaises(reconstruction.SettingsMismatch) as caught:
            reconstruction.require_compatible(
                settings_dict(), settings_dict(dac=400, samples=16)
            )
        self.assertEqual(len(caught.exception.differences), 2)
        self.assertIn("dac: 100 vs 400", str(caught.exception))

    def test_require_compatible_passes_identical_settings(self):
        reconstruction.require_compatible(settings_dict(), settings_dict())


class ReconstructTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, _ = unified.protocol_and_command("adjacent")
        cls.size = len(cls.protocol.meas_mat) * len(cls.protocol.meas_mat[0])

    def uniform(self, value: float) -> np.ndarray:
        return np.full(self.size, value, dtype=float)

    def test_identical_states_reconstruct_to_nothing(self):
        # The structural null: a feature present in both states subtracts out.
        vector = self.uniform(1.0)
        frame = frame_from_vector(vector, self.protocol)
        result = reconstruction.reconstruct([frame], [frame], settings())
        self.assertLess(abs(result.peak_value), 1e-9)
        self.assertEqual(result.dropped_indexes, [])
        self.assertEqual(result.quality_label, "ok")

    def test_a_change_produces_a_non_zero_image(self):
        baseline = frame_from_vector(self.uniform(1.0), self.protocol)
        changed = self.uniform(1.0)
        changed[0] *= 1.5
        target = frame_from_vector(changed, self.protocol)
        result = reconstruction.reconstruct([baseline], [target], settings())
        self.assertGreater(abs(result.peak_value), 0.0)

    def test_peak_angle_is_reported_in_degrees(self):
        baseline = frame_from_vector(self.uniform(1.0), self.protocol)
        changed = self.uniform(1.0)
        changed[5] *= 2.0
        target = frame_from_vector(changed, self.protocol)
        result = reconstruction.reconstruct([baseline], [target], settings())
        self.assertGreaterEqual(result.peak_angle_deg, 0.0)
        self.assertLess(result.peak_angle_deg, 360.0)

    def test_settings_gate_is_enforced_before_any_computation(self):
        frame = frame_from_vector(self.uniform(1.0), self.protocol)
        with self.assertRaises(reconstruction.SettingsMismatch):
            reconstruction.reconstruct(
                [frame],
                [frame],
                settings(),
                baseline_settings=settings_dict(),
                target_settings=settings_dict(dac=400),
            )

    def test_matching_settings_pass_the_gate(self):
        frame = frame_from_vector(self.uniform(1.0), self.protocol)
        result = reconstruction.reconstruct(
            [frame],
            [frame],
            settings(),
            baseline_settings=settings_dict(),
            target_settings=settings_dict(),
        )
        self.assertEqual(result.total_pairs, self.size)

    def test_flagged_pairs_are_dropped_not_substituted(self):
        # ADR-0002 / D-05: substitution asserts "nothing changed here".
        baseline = frame_from_vector(self.uniform(1.0), self.protocol)
        target_frame = frame_from_vector(self.uniform(1.2), self.protocol)
        spoiled = [
            unified.MeasurementRecord(
                r.polarity, r.i_pair, r.v_pair, r.voltage_mv, r.current_ua,
                "I_LOW" if index < 4 else "OK",
            )
            for index, r in enumerate(target_frame.records)
        ]
        target = unified.UnifiedFrame(1, "ADJACENT", 100, 10, 4, spoiled)
        result = reconstruction.reconstruct([baseline], [target], settings())
        self.assertEqual(len(result.dropped_indexes), 2)
        self.assertEqual(result.kept_pairs, self.size - 2)
        self.assertEqual(result.quality_label, "best-effort")

    def test_no_frames_is_an_error_not_an_empty_image(self):
        frame = frame_from_vector(self.uniform(1.0), self.protocol)
        with self.assertRaises(ValueError):
            reconstruction.reconstruct([], [frame], settings())

    def test_vectors_are_averaged_across_frames(self):
        low = frame_from_vector(self.uniform(1.0), self.protocol)
        high = frame_from_vector(self.uniform(3.0), self.protocol)
        result = reconstruction.reconstruct([low, high], [low], settings())
        self.assertAlmostEqual(float(np.nanmean(result.baseline_vector)), 2.0, places=6)

    def test_kept_ratio_and_limit_are_derived(self):
        frame = frame_from_vector(self.uniform(1.0), self.protocol)
        result = reconstruction.reconstruct([frame], [frame], settings())
        self.assertAlmostEqual(result.kept_ratio, 1.0)
        self.assertGreaterEqual(result.limit, 0.0)


class ReciprocityGateTests(unittest.TestCase):
    """ADR-0030: no difference image from data that breaks reciprocity."""

    def gate_with(self, summary):
        from unittest import mock

        with mock.patch.object(
            reconstruction.capture_view, "reciprocity_summary", return_value=summary
        ):
            return reconstruction.reciprocity_gate([])

    def summary(self, median):
        from tree_ert.capture_view import ReciprocitySummary

        return ReciprocitySummary(
            pair_count=54, median_error_percent=median,
            max_error_percent=median * 2, sign_flip_count=0,
        )

    def test_threshold_is_ten_percent(self):
        self.assertEqual(reconstruction.RECIPROCITY_GATE_PERCENT, 10.0)

    def test_good_reciprocity_passes(self):
        self.assertIsNone(self.gate_with(self.summary(2.0)))

    def test_exactly_at_the_threshold_passes(self):
        self.assertIsNone(self.gate_with(self.summary(10.0)))

    def test_the_measured_tank_value_fails_and_says_why(self):
        reason = self.gate_with(self.summary(79.1))
        self.assertIn("79.1%", reason)
        self.assertIn("10%", reason)

    def test_unmeasurable_reciprocity_fails_rather_than_passes(self):
        self.assertIn("could not be measured", self.gate_with(None))


class ControlImageTests(unittest.TestCase):
    """The baseline against itself: what noise looks like in solver units.

    Without it, a difference image of drift and a difference image of a real
    feature are indistinguishable -- both auto-scale to fill the colour range.
    """

    @classmethod
    def setUpClass(cls):
        cls.protocol, _ = unified.protocol_and_command("adjacent")
        cls.size = len(cls.protocol.meas_mat) * len(cls.protocol.meas_mat[0])

    def frames(self, values, count=1):
        return [frame_from_vector(np.asarray(values), self.protocol) for _ in range(count)]

    def test_too_few_frames_gives_no_control_rather_than_a_fake_one(self):
        # One frame per half would make the control a single-frame difference,
        # which understates noise rather than measuring it.
        for count in (0, 1, 2, 3):
            with self.subTest(frames=count):
                frames = self.frames(np.full(self.size, 1.0), count)
                self.assertIsNone(reconstruction.split_half_control(frames, settings()))

    def test_four_frames_are_enough_to_split(self):
        frames = self.frames(np.full(self.size, 1.0), 4)
        control = reconstruction.split_half_control(frames, settings())
        self.assertIsNotNone(control)
        self.assertEqual(control.total_pairs, self.size)

    def test_identical_frames_give_a_zero_noise_image(self):
        frames = self.frames(np.full(self.size, 1.0), 6)
        control = reconstruction.split_half_control(frames, settings())
        self.assertAlmostEqual(control.limit, 0.0)

    def test_drifting_frames_give_a_non_zero_noise_image(self):
        # Halves that differ produce exactly the residual the control exists to
        # measure.
        frames = []
        for step in range(6):
            values = np.full(self.size, 1.0)
            values[0] += step * 0.01
            frames.append(frame_from_vector(values, self.protocol))
        control = reconstruction.split_half_control(frames, settings())
        self.assertGreater(control.limit, 0.0)


class SignificanceTests(unittest.TestCase):
    @staticmethod
    def result_with(limit: float) -> reconstruction.ReconstructionResult:
        values = np.zeros(10)
        values[0] = limit
        return reconstruction.ReconstructionResult(
            values=values,
            baseline_vector=np.zeros(1),
            target_vector=np.zeros(1),
            dropped_indexes=[],
            kept_pairs=1,
            total_pairs=1,
            quality_label="ok",
            peak_value=limit,
            peak_xy=(0.0, 0.0),
            peak_angle_deg=0.0,
            noise_floor_kohm=None,
        )

    def test_an_image_the_size_of_its_noise_scores_one(self):
        self.assertAlmostEqual(
            reconstruction.significance(self.result_with(1.0), self.result_with(1.0)),
            1.0,
        )

    def test_a_ten_times_larger_image_scores_ten(self):
        self.assertAlmostEqual(
            reconstruction.significance(self.result_with(10.0), self.result_with(1.0)),
            10.0,
        )

    def test_zero_noise_and_zero_image_is_zero_not_a_crash(self):
        self.assertEqual(
            reconstruction.significance(self.result_with(0.0), self.result_with(0.0)),
            0.0,
        )

    def test_zero_noise_with_a_real_image_is_infinite(self):
        self.assertEqual(
            reconstruction.significance(self.result_with(1.0), self.result_with(0.0)),
            float("inf"),
        )


class SaveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        protocol, _ = unified.protocol_and_command("adjacent")
        size = len(protocol.meas_mat) * len(protocol.meas_mat[0])
        baseline = frame_from_vector(np.full(size, 1.0), protocol)
        changed = np.full(size, 1.0)
        changed[0] *= 1.4
        target = frame_from_vector(changed, protocol)
        self.result = reconstruction.reconstruct([baseline], [target], settings())

    def test_image_and_data_are_written(self):
        image, data = reconstruction.save_reconstruction(
            self.result,
            settings(),
            self.root / "reconstruction.png",
            self.root / "reconstruction.npz",
        )
        self.assertTrue(image.is_file())
        self.assertTrue(data.is_file())
        self.assertGreater(image.stat().st_size, 1000)

    def test_npz_round_trips_the_vectors_and_the_peak(self):
        _, data = reconstruction.save_reconstruction(
            self.result,
            settings(),
            self.root / "r.png",
            self.root / "r.npz",
        )
        loaded = np.load(data, allow_pickle=False)
        np.testing.assert_allclose(loaded["values"], self.result.values)
        np.testing.assert_allclose(loaded["baseline"], self.result.baseline_vector)
        self.assertAlmostEqual(float(loaded["peak_value"]), self.result.peak_value)
        self.assertEqual(int(loaded["total_pairs"]), self.result.total_pairs)

    def test_data_path_is_optional(self):
        image, data = reconstruction.save_reconstruction(
            self.result, settings(), self.root / "only.png"
        )
        self.assertTrue(image.is_file())
        self.assertIsNone(data)

    def test_caption_states_the_magnitude_and_the_scale(self):
        # The line that stops a vivid null being read as a detection.
        caption = reconstruction._magnitude_caption(self.result)
        self.assertIn("peak", caption)
        self.assertIn("auto-scaled to this image", caption)
        self.assertIn("pairs", caption)

    def test_a_zero_image_says_so_rather_than_quoting_a_zero_scale(self):
        # The colourbar falls back to a nominal range when there is nothing to
        # scale; "+/-0.000e+00" beside a bar reading +/-1.00 reads as a
        # contradiction rather than as a null.
        protocol, _ = unified.protocol_and_command("adjacent")
        size = len(protocol.meas_mat) * len(protocol.meas_mat[0])
        flat = frame_from_vector(np.full(size, 1.0), protocol)
        null = reconstruction.reconstruct([flat], [flat], settings())
        caption = reconstruction._magnitude_caption(null)
        self.assertIn("identically zero", caption)
        self.assertNotIn("colour scale", caption)

    def test_a_control_panel_is_drawn_and_stored(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        size = len(protocol.meas_mat) * len(protocol.meas_mat[0])
        frames = [frame_from_vector(np.full(size, 1.0), protocol) for _ in range(4)]
        control = reconstruction.split_half_control(frames, settings())
        image, data = reconstruction.save_reconstruction(
            self.result,
            settings(),
            self.root / "c.png",
            self.root / "c.npz",
            control=control,
        )
        loaded = np.load(data, allow_pickle=False)
        self.assertIn("control_values", loaded.files)
        self.assertIn("significance", loaded.files)
        # Two panels make a wider figure than one.
        self.assertTrue(image.is_file())

    def test_the_two_panels_share_one_colour_scale(self):
        # Scaling them independently would make the noise image look exactly as
        # dramatic as the real one, which is the misreading this prevents.
        big = self.result
        small = reconstruction.ReconstructionResult(
            **{**self.result.__dict__, "values": self.result.values * 0.01}
        )
        shared = max(big.limit, small.limit)
        self.assertAlmostEqual(shared, big.limit)
        self.assertGreater(big.limit, small.limit)

    def test_caption_states_the_significance_against_the_control(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        size = len(protocol.meas_mat) * len(protocol.meas_mat[0])
        frames = [frame_from_vector(np.full(size, 1.0), protocol) for _ in range(4)]
        control = reconstruction.split_half_control(frames, settings())
        reconstruction.save_reconstruction(
            self.result,
            settings(),
            self.root / "s.png",
            control=control,
        )
        # A zero-noise control makes any real image infinitely significant,
        # which the caption must render rather than crash on.
        self.assertEqual(control.limit, 0.0)

    def test_caption_names_the_noise_floor_when_known(self):
        with_floor = reconstruction.ReconstructionResult(
            **{
                **self.result.__dict__,
                "noise_floor_kohm": 0.00017,
            }
        )
        caption = reconstruction._magnitude_caption(with_floor)
        self.assertIn("noise floor", caption)
        self.assertIn("not a detection", caption)


if __name__ == "__main__":
    unittest.main()
