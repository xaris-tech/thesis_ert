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


class RecalibrationLadderTests(unittest.TestCase):
    def _coconut(self):
        from tree_ert.settings import UiSettings, preset_by_name

        return preset_by_name("Coconut").apply_to(UiSettings(port="X"))

    def test_settle_ramps_and_every_parameter_varies(self):
        ladder = absolute.recalibration_ladder(self._coconut())
        self.assertEqual([s.settle_ms for s in ladder], [10, 30, 50, 75, 100, 150, 200])
        for field in ("samples", "warmup_frames", "frames", "dac"):
            self.assertGreater(len({getattr(s, field) for s in ladder}), 1, field)

    def test_never_exceeds_firmware_or_range_ceilings(self):
        base_settings = self._coconut()
        for step in absolute.recalibration_ladder(base_settings):
            self.assertLessEqual(step.samples, absolute.SAMPLES_CEILING)
            self.assertLessEqual(step.dac, base_settings.max_dac_code())
            self.assertGreaterEqual(step.frames, 4)
            self.assertEqual(step.pattern, base_settings.pattern)
            self.assertEqual(step.current_range, base_settings.current_range)

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

    def test_stops_at_first_pass_and_cycles_rounds(self):
        verdicts = iter([False, False, True])
        original = absolute.evaluate
        absolute.evaluate = lambda frames, s: (None, None, self._report(next(verdicts)))
        try:
            seen = []
            attempts, passed = absolute.acquire_until_pass(
                lambda s: [], ["a", "b"], rounds=2, on_attempt=lambda n, a: seen.append(n)
            )
        finally:
            absolute.evaluate = original
        self.assertEqual(seen, [1, 2, 3])
        self.assertEqual(passed.settings, "a")
        self.assertEqual(len(attempts), 3)

    def test_stops_after_repeated_contact_faults(self):
        original, original_fault = absolute.evaluate, absolute.contact_fault
        absolute.evaluate = lambda frames, s: (None, None, self._report(False))
        absolute.contact_fault = lambda frames: ((1, 50.0),)
        try:
            attempts, passed = absolute.acquire_until_pass(lambda s: [], list("abcdef"))
        finally:
            absolute.evaluate, absolute.contact_fault = original, original_fault
        self.assertIsNone(passed)
        self.assertEqual(len(attempts), absolute.CONTACT_FAULT_STREAK)

    def test_returns_none_when_ladder_exhausted(self):
        original = absolute.evaluate
        absolute.evaluate = lambda frames, s: (None, None, self._report(False))
        try:
            attempts, passed = absolute.acquire_until_pass(lambda s: [], ["a", "b"], rounds=2)
        finally:
            absolute.evaluate = original
        self.assertIsNone(passed)
        self.assertEqual(len(attempts), 4)


if __name__ == "__main__":
    unittest.main()
