import unittest

import numpy as np
from pyeit.eit.fem import EITForward

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert import absolute


def _synthetic(perm_fn):
    protocol, _ = unified.protocol_and_command("adjacent")
    eit_mesh, _ = base.create_solver(protocol)
    centres = np.mean(eit_mesh.node[eit_mesh.element], axis=1)
    perm = perm_fn(centres)
    return protocol, centres, np.real(EITForward(eit_mesh, protocol).solve_eit(perm=perm))


class SolveAbsoluteTests(unittest.TestCase):
    def test_homogeneous_conductivity_is_recovered(self):
        protocol, _, v = _synthetic(lambda c: np.full(len(c), 3.0))
        result = absolute.solve_absolute(v, protocol)
        self.assertAlmostEqual(result.sigma0, 3.0, places=6)
        self.assertLess(result.residual_percent, 0.1)

    def test_resistive_inclusion_is_located_and_lower(self):
        def perm(c):
            p = np.full(len(c), 2.0)
            p[np.hypot(c[:, 0] - 0.5, c[:, 1]) < 0.3] = 1.0
            return p

        protocol, centres, v = _synthetic(perm)
        result = absolute.solve_absolute(v, protocol)
        inside = np.hypot(centres[:, 0] - 0.5, centres[:, 1]) < 0.3
        self.assertLess(result.sigma[inside].mean(), result.sigma[~inside].mean())
        self.assertLess(result.peak_value, 0.0)
        angle = result.peak_angle_deg
        self.assertLess(min(angle, 360.0 - angle), 30.0)
        self.assertLess(result.residual_percent, absolute.MISFIT_GATE_PERCENT)

    def test_strong_void_is_located_by_the_trough_not_the_peak(self):
        # ADR-0061: a void lowers sigma0, so the largest |sigma - sigma0| is a
        # positive overshoot beside the void. The trough is what finds it.
        hole = np.radians(105.0)

        def perm(c):
            p = np.ones(len(c))
            p[np.hypot(c[:, 0] - 0.6 * np.cos(hole), c[:, 1] - 0.6 * np.sin(hole)) < 0.25] = 0.05
            return p

        protocol, _, v = _synthetic(perm)
        result = absolute.solve_absolute(v, protocol)
        def error(angle):
            return abs((angle - 105.0 + 180.0) % 360.0 - 180.0)

        self.assertLess(result.trough_value, 0.0)
        self.assertLess(error(result.trough_angle_deg), 20.0)
        # The behaviour ADR-0061 exists for: the peak alone misplaces a void.
        self.assertGreater(error(result.peak_angle_deg), 20.0)

    def test_sign_flip_is_detected_not_imaged(self):
        protocol, _, v = _synthetic(lambda c: np.full(len(c), 2.0))
        result = absolute.solve_absolute(-v, protocol)
        self.assertEqual(result.sign, -1)
        self.assertAlmostEqual(result.sigma0, 2.0, places=6)

    def test_nan_rows_are_dropped(self):
        protocol, _, v = _synthetic(lambda c: np.full(len(c), 2.0))
        v = v.copy()
        v[[0, 5]] = np.nan
        result = absolute.solve_absolute(v, protocol)
        self.assertEqual(result.dropped_indexes, [0, 5])
        self.assertAlmostEqual(result.sigma0, 2.0, places=6)

    def test_all_nan_refused(self):
        protocol, _, v = _synthetic(lambda c: np.full(len(c), 2.0))
        with self.assertRaises(ValueError):
            absolute.solve_absolute(np.full_like(v, np.nan), protocol)


class TroughLobeTests(unittest.TestCase):
    """ADR-0062: the trough is a connected lobe, and says which electrodes it touches."""

    # A strip of four triangles; node 0 and node 5 are electrodes.
    #   0---2---4
    #   | / | / |
    #   1---3---5
    NODES = np.array([[0, 1], [0, 0], [1, 1], [1, 0], [2, 1], [2, 0]], dtype=float)
    ELEMENTS = np.array([[0, 1, 2], [1, 3, 2], [2, 3, 4], [3, 5, 4]])

    def test_lobe_is_the_connected_region_around_the_minimum(self):
        lobe = absolute.trough_lobe(
            np.array([-1.0, -0.8, 0.0, -0.9]), self.ELEMENTS, self.NODES, np.array([0, 5])
        )
        # Element 3 is deep enough but not connected through element 2.
        self.assertEqual(lobe.elements, (0, 1))
        self.assertEqual(lobe.electrodes, (0,))

    def test_interior_lobe_touches_no_electrode(self):
        lobe = absolute.trough_lobe(
            np.array([0.0, -1.0, -0.6, 0.0]), self.ELEMENTS, self.NODES, np.array([0, 5])
        )
        self.assertEqual(lobe.elements, (1, 2))
        self.assertEqual(lobe.electrodes, ())

    def test_no_negative_value_means_no_trough(self):
        self.assertIsNone(
            absolute.trough_lobe(np.zeros(4), self.ELEMENTS, self.NODES, np.array([0, 5]))
        )


class DisplayScaleTests(unittest.TestCase):
    """ADR-0061: one spike must not flatten the rest of the image to grey."""

    def test_log_ratio_and_clipped_scale(self):
        sigma = np.full(100, 2.0)
        sigma[:10] = 3.0   # a real 1.5x region
        sigma[-1] = 74.0   # one 37x spike
        image, noise, scale, clipped, _ = absolute.display_values(
            sigma, 2.0, np.zeros(100)
        )
        np.testing.assert_allclose(image[:10], np.log10(1.5))
        self.assertEqual(clipped, 1)
        # The 1.5x region spans a visible share of the scale, not ~1 %.
        self.assertGreater(np.log10(1.5) / scale, 0.5)
        np.testing.assert_allclose(noise, 0.0)

    def test_noise_is_first_order_log_of_the_split_half_difference(self):
        sigma = np.full(10, 2.0)
        _, noise, _, _, _ = absolute.display_values(sigma, 2.0, np.full(10, 0.02))
        np.testing.assert_allclose(noise, 0.01 / np.log(10.0))

    def test_huge_noise_saturates_its_panel_instead_of_flattening_the_image(self):
        # ADR-0063, run 20261013-175019-disc2: noise at three contacts reached
        # +-10 in log units and stretched the shared scale until the image was pale.
        sigma = np.full(100, 2.0)
        sigma[:10] = 3.0
        noise = np.zeros(100)
        noise[-5:] = 1e10
        _, _, scale, _, noise_clipped = absolute.display_values(sigma, 2.0, noise)
        self.assertAlmostEqual(scale, np.log10(1.5))
        self.assertEqual(noise_clipped, 5)


def _coconut(**changes):
    from dataclasses import replace

    from tree_ert.settings import UiSettings, preset_by_name

    return replace(preset_by_name("Coconut").apply_to(UiSettings(port="X")), **changes)


def _report(recip, noise=1.0, passed=False):
    return absolute.GateReport(recip, noise, None, () if passed else ("x",))


class NextSettingsTests(unittest.TestCase):
    """ADR-0060: the next attempt is chosen from what the previous ones measured."""

    def test_first_attempt_is_the_operators_settings(self):
        start = _coconut()
        self.assertEqual(absolute.next_settings(start, []), start)

    def test_noisy_run_averages_more_at_the_same_settle(self):
        start = _coconut(samples=16, frames=10)
        step = absolute.next_settings(start, [(start, _report(12.0, noise=7.9))])
        self.assertEqual(step.settle_ms, start.settle_ms)
        self.assertEqual(step.samples, absolute.SAMPLES_CEILING)
        self.assertGreater(step.frames, start.frames)

    def test_quiet_reciprocity_failure_moves_settle_within_the_wood_range(self):
        start = _coconut(settle_ms=30)
        step = absolute.next_settings(start, [(start, _report(21.7))])
        self.assertNotEqual(step.settle_ms, 30)
        self.assertIn(step.settle_ms, absolute.WOOD_SETTLE_MS)

    def test_climbs_from_the_best_attempt_not_the_latest(self):
        # disc-01, 2026-10-07: 30 ms 6.5 % beat 10 ms 7.3 % and 100 ms 13.9 %.
        start = _coconut(settle_ms=30)
        tried = [
            (start, _report(16.0)),
            (_coconut(settle_ms=20), _report(25.0)),
        ]
        step = absolute.next_settings(start, tried)
        self.assertEqual(step.settle_ms, 40)

    def test_settle_never_leaves_the_wood_range(self):
        start = _coconut(settle_ms=100)
        tried = [(start, _report(13.9))]
        for _ in range(absolute.ADAPTIVE_MAX_ATTEMPTS):
            step = absolute.next_settings(start, tried)
            if step is None:
                break
            self.assertLessEqual(step.settle_ms, max(absolute.WOOD_SETTLE_MS))
            tried.append((step, _report(20.0)))

    def test_never_repeats_and_stops_at_the_cap(self):
        start = _coconut()
        tried = []
        while (step := absolute.next_settings(start, tried)) is not None:
            self.assertNotIn(step, [s for s, _ in tried])
            tried.append((step, _report(20.0)))
        self.assertLessEqual(len(tried), absolute.ADAPTIVE_MAX_ATTEMPTS)

    def test_never_exceeds_firmware_or_range_ceilings(self):
        start = _coconut(samples=32, frames=16)
        tried = []
        while (step := absolute.next_settings(start, tried)) is not None:
            self.assertLessEqual(step.samples, absolute.SAMPLES_CEILING)
            self.assertLessEqual(step.dac, start.max_dac_code())
            self.assertLessEqual(step.frames, absolute.FRAMES_CEILING)
            self.assertEqual(step.pattern, start.pattern)
            self.assertEqual(step.current_range, start.current_range)
            tried.append((step, _report(20.0, noise=8.0)))


class RecalibrationTimingTests(unittest.TestCase):
    def _coconut(self):
        return _coconut()

    def test_time_estimate_matches_measured_preset(self):
        # 2026-10-06: 64 s per frame at settle 30 / samples 32.
        s = self._coconut()
        per_frame = absolute.estimated_minutes(s) * 60 / (s.warmup_frames + s.frames)
        self.assertAlmostEqual(per_frame, 64.0, delta=2.0)


class GateReciprocityApplicabilityTests(unittest.TestCase):
    def frames(self, pattern):
        from dataclasses import replace

        from tree_ert.acquisition import DemoAcquisition
        from tree_ert.settings import UiSettings

        board = DemoAcquisition()
        board.configure(replace(UiSettings.default(), pattern=pattern))
        return [board.capture_frame() for _ in range(2)]

    def test_opposite_is_not_refused_for_unmeasurable_reciprocity(self):
        report = absolute.gate(self.frames("opposite"), None, None)
        self.assertFalse(any("reciprocity" in r for r in report.reasons), report.reasons)
        self.assertIn("absolute solve failed", report.reasons)

    def test_adjacent_still_gates_reciprocity(self):
        from unittest import mock

        with mock.patch.object(absolute.capture_view, "reciprocity_summary", return_value=None):
            report = absolute.gate(self.frames("adjacent"), None, None)
        self.assertIn("reciprocity could not be measured (no reciprocal pairs)", report.reasons)


class StopReasonTests(unittest.TestCase):
    def _r(self, recip):
        return absolute.GateReport(recip, None, None, ("x",))

    def test_stall_without_a_suspect_electrode(self):
        # disc-08, 2026-10-06: every electrode bad together, none flagged.
        history = [(self._r(19.8), ()), (self._r(26.1), ()), (self._r(19.3), ())]
        self.assertIn("reciprocity stayed above", absolute.stop_reason(history))

    def test_improving_run_keeps_going(self):
        history = [(self._r(19.8), ()), (self._r(26.1), ()), (self._r(9.0), ())]
        self.assertIsNone(absolute.stop_reason(history))

    def test_contact_streak(self):
        history = [(self._r(5.0), ((1, 40.0),))] * 3
        self.assertIn("E2", absolute.stop_reason(history))

    def test_too_short_history(self):
        self.assertIsNone(absolute.stop_reason([(self._r(40.0), ((1, 9.0),))] * 2))


class ClampTests(unittest.TestCase):
    def test_runaway_is_bounded(self):
        protocol, _, v = _synthetic(lambda c: np.full(len(c), 2.0))
        rng = np.random.default_rng(1)
        garbage = v * (1 + 2.0 * rng.standard_normal(v.size))
        result = absolute.solve_absolute(garbage, protocol)
        ratio = result.sigma / result.sigma0
        self.assertLessEqual(ratio.max(), 100.0 + 1e-6)
        self.assertGreaterEqual(ratio.min(), 0.01 - 1e-9)


class SignificanceTests(unittest.TestCase):
    def test_zero_noise(self):
        protocol, _, v = _synthetic(lambda c: np.full(len(c), 2.0))
        result = absolute.solve_absolute(v, protocol)
        self.assertEqual(absolute.significance(result, np.zeros(3)), 0.0)


class AcquireUntilPassTests(unittest.TestCase):
    def _report(self, passed):
        return absolute.GateReport(None, None, None, () if passed else ("bad",))

    def test_stops_at_first_pass(self):
        verdicts = iter([False, False, True])
        original = absolute.evaluate
        absolute.evaluate = lambda frames, s: (None, None, self._report(next(verdicts)))
        try:
            seen = []
            attempts, passed = absolute.acquire_until_pass(
                lambda s: [], _coconut(), on_attempt=lambda n, a: seen.append(n)
            )
        finally:
            absolute.evaluate = original
        self.assertEqual(seen, [1, 2, 3])
        self.assertEqual(passed.settings, attempts[2].settings)
        self.assertEqual(attempts[0].settings, _coconut())

    def test_stops_after_repeated_contact_faults(self):
        original, original_fault = absolute.evaluate, absolute.contact_fault
        absolute.evaluate = lambda frames, s: (None, None, self._report(False))
        absolute.contact_fault = lambda frames, excluded=(): ((1, 50.0),)
        try:
            attempts, passed = absolute.acquire_until_pass(lambda s: [], _coconut())
        finally:
            absolute.evaluate, absolute.contact_fault = original, original_fault
        self.assertIsNone(passed)
        self.assertEqual(len(attempts), absolute.CONTACT_FAULT_STREAK)

    def test_returns_none_when_attempts_exhausted(self):
        original = absolute.evaluate
        absolute.evaluate = lambda frames, s: (None, None, self._report(False))
        try:
            attempts, passed = absolute.acquire_until_pass(
                lambda s: [], _coconut(), max_attempts=4
            )
        finally:
            absolute.evaluate = original
        self.assertIsNone(passed)
        self.assertEqual(len(attempts), 4)


if __name__ == "__main__":
    unittest.main()


class ExcludeElectrodesTests(unittest.TestCase):
    """ADR-0064: a known-faulty channel is left out of the absolute solve."""

    def _frame(self):
        record = unified.MeasurementRecord
        return unified.UnifiedFrame(
            frame_id=1, pattern="adjacent", dac_code=400, settle_ms=30, sample_count=16,
            records=[
                record("FWD", (0, 1), (2, 3), 1.0, 100.0, "OK"),   # drives on E1/E2
                record("FWD", (4, 5), (6, 7), 1.0, 100.0, "OK"),   # clear of E1/E2
                record("FWD", (4, 5), (1, 2), 1.0, 100.0, "OK"),   # senses on E2
            ],
        )

    def test_records_touching_an_excluded_electrode_are_removed(self):
        (kept,) = absolute.exclude_electrodes([self._frame()], (1, 2))
        self.assertEqual([r.i_pair for r in kept.records], [(4, 5)])
        self.assertEqual(kept.records[0].v_pair, (6, 7))

    def test_nothing_excluded_leaves_frames_untouched(self):
        frame = self._frame()
        self.assertEqual(absolute.exclude_electrodes([frame], ()), [frame])

    def test_contact_fault_ignores_excluded_electrodes(self):
        self.assertEqual(absolute.contact_fault([self._frame()], (1, 2, 3, 4, 5, 6)), ())
