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
        absolute.contact_fault = lambda frames: ((1, 50.0),)
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
