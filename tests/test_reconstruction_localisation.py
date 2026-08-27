"""End-to-end localisation checks against PyEIT's own forward model.

These exist because nothing in the suite previously put a target of known
position and known sign through the pipeline and checked where it came out.
That gap is what let the mirrored electrode labels (validity-audit D-01) and the
inverted reconstruction sign (D-02) survive.
"""

import unittest

import numpy as np
import pyeit.mesh as pyeit_mesh
from pyeit.eit.fem import EITForward
from pyeit.mesh.wrapper import PyEITAnomaly_Circle

import phase3a_reconstruct as base


TARGET_ANGLE_DEG = 30.0
TARGET_RADIUS = 0.6


def _forward_pair(protocol, target_angle_deg=TARGET_ANGLE_DEG, perm=10.0):
    """Homogeneous and anomaly measurement vectors in PyEIT's own convention."""
    mesh_obj = pyeit_mesh.create(base.N_ELECTRODES, h0=0.08)
    forward = EITForward(mesh_obj, protocol)
    homogeneous = forward.solve_eit()

    angle = np.deg2rad(target_angle_deg)
    anomaly = PyEITAnomaly_Circle(
        center=[TARGET_RADIUS * np.cos(angle), TARGET_RADIUS * np.sin(angle)],
        r=0.2,
        perm=perm,
    )
    anomaly_mesh = pyeit_mesh.set_perm(mesh_obj, anomaly=anomaly, background=1.0)
    measured = forward.solve_eit(perm=anomaly_mesh.perm)
    return homogeneous, measured


def _peak_angle_deg(mesh_obj, values):
    centroids = mesh_obj.node[mesh_obj.element].mean(axis=1)
    peak = centroids[int(np.argmax(np.abs(values)))]
    return float(np.rad2deg(np.arctan2(peak[1], peak[0]))) % 360.0


class TestReconstructionLocalisation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = base.build_adjacent_protocol()
        cls.mesh_obj, cls.solver = base.create_solver(cls.protocol)
        cls.homogeneous, cls.measured = _forward_pair(cls.protocol)

    def test_conductive_target_reconstructs_at_its_own_angle(self):
        values = base.reconstruct_difference(
            self.homogeneous, self.measured, self.solver
        )

        peak = _peak_angle_deg(self.mesh_obj, values)
        separation = abs((peak - TARGET_ANGLE_DEG + 180.0) % 360.0 - 180.0)

        # One electrode sector is 30 degrees; HANDOVER.md accepts 1-2 sectors.
        self.assertLess(separation, 60.0, f"peak at {peak:.1f} deg")

    def test_conductive_target_reconstructs_positive(self):
        values = base.reconstruct_difference(
            self.homogeneous, self.measured, self.solver
        )
        peak_value = values[int(np.argmax(np.abs(values)))]

        # A more conductive inclusion must not render as a negative (blue)
        # region; that inversion was validity-audit D-02.
        self.assertGreater(peak_value, 0.0)

    def test_resistive_target_reconstructs_negative(self):
        homogeneous, measured = _forward_pair(self.protocol, perm=0.1)

        values = base.reconstruct_difference(homogeneous, measured, self.solver)
        peak_value = values[int(np.argmax(np.abs(values)))]

        self.assertLess(peak_value, 0.0)

    def test_electrode_labels_sit_on_the_mesh_electrodes(self):
        placements = base.electrode_label_positions(self.mesh_obj)

        self.assertEqual(len(placements), base.N_ELECTRODES)
        for index, x, y in placements:
            node = self.mesh_obj.node[self.mesh_obj.el_pos[index]]
            label_angle = np.rad2deg(np.arctan2(y, x)) % 360.0
            node_angle = np.rad2deg(np.arctan2(node[1], node[0])) % 360.0
            separation = abs((label_angle - node_angle + 180.0) % 360.0 - 180.0)
            self.assertLess(
                separation,
                1.0,
                f"E{index + 1} label at {label_angle:.1f} deg, "
                f"mesh electrode at {node_angle:.1f} deg",
            )

    def test_labels_would_fail_under_the_old_assumed_angle(self):
        # Guards the fix itself: the previous formula must not agree with the
        # mesh, otherwise this test proves nothing.
        mismatches = 0
        for index, _x, _y in base.electrode_label_positions(self.mesh_obj):
            node = self.mesh_obj.node[self.mesh_obj.el_pos[index]]
            assumed = np.rad2deg(2.0 * np.pi * index / base.N_ELECTRODES) % 360.0
            node_angle = np.rad2deg(np.arctan2(node[1], node[0])) % 360.0
            if abs((assumed - node_angle + 180.0) % 360.0 - 180.0) > 1.0:
                mismatches += 1
        self.assertGreater(mismatches, 0)


if __name__ == "__main__":
    unittest.main()
