import unittest

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
import position_series as ps


class SeriesTests(unittest.TestCase):
    def test_full_series_matches_handoff_plan(self):
        keys = [p.key for p in ps.series()]
        self.assertEqual(len(keys), 21)  # 2 empty + 12 singles + 6 pairs + centre
        self.assertEqual(keys[0], "empty-first")
        self.assertEqual(keys[-1], "empty-last")
        self.assertIn("e3+e9", keys)
        self.assertIn("centre", keys)

    def test_unknown_position_is_refused(self):
        with self.assertRaises(ValueError):
            ps.series("e13")

    def test_headline_follows_blind_sector(self):
        blind = (1, 2, 3)
        by_key = {p.key: p for p in ps.series()}
        self.assertEqual(ps.headline(by_key["e2"], blind), "difference")
        self.assertEqual(ps.headline(by_key["e3+e9"], blind), "difference")
        self.assertEqual(ps.headline(by_key["e4+e10"], blind), "absolute")
        self.assertEqual(ps.headline(by_key["centre"], blind), "absolute")
        self.assertEqual(ps.headline(by_key["empty-first"], blind), "baseline")


class AngleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        protocol, _ = unified.protocol_and_command("adjacent")
        cls.mesh, _ = base.create_solver(protocol)

    def test_e7_is_at_zero_and_e1_at_180(self):
        e7 = ps.Position("e7", "wood at e7", (7,))
        e1 = ps.Position("e1", "wood at e1", (1,))
        self.assertLess(ps.angle_error(0.0, e7, self.mesh), 1.0)
        self.assertLess(ps.angle_error(180.0, e1, self.mesh), 1.0)

    def test_pair_uses_nearest_block(self):
        pair = ps.Position("e1+e7", "wood at e1 and e7", (1, 7))
        self.assertLess(ps.angle_error(175.0, pair, self.mesh), 10.0)
        self.assertLess(ps.angle_error(5.0, pair, self.mesh), 10.0)

    def test_difference_angle_is_the_resistive_lobe(self):
        import numpy as np
        centres = np.mean(self.mesh.node[self.mesh.element], axis=1)
        angles = np.degrees(np.arctan2(centres[:, 1], centres[:, 0])) % 360.0
        values = np.zeros(len(centres))
        values[np.argmin(np.abs(angles - 180.0))] = -1.0
        values[np.argmin(np.abs(angles - 0.0))] = 2.0  # larger, but conductive
        self.assertLess(abs(ps.resistive_trough_deg(values, self.mesh) - 180.0), 10.0)

    def test_centre_has_no_angle(self):
        self.assertIsNone(ps.angle_error(90.0, ps.Position("centre", "wood at centre", ()), self.mesh))


class LeaveOneOutTests(unittest.TestCase):
    def test_each_electrode_is_excluded_alone_not_on_top_of_standing_exclusion(self):
        from unittest import mock
        from tree_ert.settings import UiSettings

        seen = []

        def fake(frames, settings):
            seen.append(settings.absolute_exclude_electrodes)
            return mock.Mock(residual_percent=1.0)

        with mock.patch.object(ps.absolute, "reconstruct_absolute", fake):
            ps.leave_one_out([], UiSettings(port="x", absolute_exclude_electrodes=(2,)))
        self.assertEqual(seen, [(n,) for n in range(1, 13)])


class LocatedTests(unittest.TestCase):
    position = ps.Position("e2", "wood at e2", (2,))

    def test_difference_needs_significance(self):
        row = {"headline": "difference", "difference_significance": 1.5, "difference_trough_error_deg": 5.0}
        self.assertEqual(ps.located(row, self.position), "no (below noise)")
        row["difference_significance"] = 3.0
        self.assertEqual(ps.located(row, self.position), "yes")
        row["difference_trough_error_deg"] = 60.0
        self.assertEqual(ps.located(row, self.position), "no (wrong place)")

    def test_absolute_needs_gate(self):
        row = {"headline": "absolute", "excluded_gate": "misfit 40 %", "absolute_trough_error_deg": 0.0}
        self.assertEqual(ps.located(row, self.position), "no (refused)")


if __name__ == "__main__":
    unittest.main()
