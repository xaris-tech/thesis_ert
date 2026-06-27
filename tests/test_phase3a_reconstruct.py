import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import phase3a_reconstruct as phase3a


class TestPhase3AProtocol(unittest.TestCase):
    def test_capture_frame_numbers_produces_requested_count(self):
        self.assertEqual(list(phase3a.capture_frame_numbers(20)), list(range(1, 21)))

    def test_capture_frame_numbers_rejects_non_positive_count(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            phase3a.capture_frame_numbers(0)

    def test_build_adjacent_protocol_order_matches_firmware(self):
        protocol = phase3a.build_adjacent_protocol(12)

        self.assertEqual(protocol.ex_mat.shape, (12, 2))
        self.assertTrue(np.array_equal(protocol.ex_mat[0], np.array([0, 1])))
        self.assertTrue(np.array_equal(protocol.ex_mat[-1], np.array([11, 0])))
        self.assertEqual(protocol.meas_mat.shape, (12, 9, 2))
        self.assertTrue(np.array_equal(protocol.meas_mat[0][0], np.array([3, 2])))
        self.assertTrue(np.array_equal(protocol.meas_mat[0][-1], np.array([11, 10])))

    def test_build_opposite_protocol_uses_opposing_injection_pairs(self):
        protocol = phase3a.build_opposite_protocol(12)

        self.assertEqual(protocol.ex_mat.shape, (12, 2))
        self.assertTrue(np.array_equal(protocol.ex_mat[0], np.array([0, 6])))
        self.assertTrue(np.array_equal(protocol.ex_mat[1], np.array([1, 7])))
        self.assertEqual(protocol.meas_mat.shape, (12, 8, 2))
        self.assertTrue(np.array_equal(protocol.meas_mat[0][0], np.array([2, 1])))


class TestPhase3AParsing(unittest.TestCase):
    def test_parse_frame_records_maps_values_to_protocol_order(self):
        lines = [
            "I+,E1,I-,E2,V+,E3,V-,E4,V,-1.5",
            "I+,E1,I-,E2,V+,E4,V-,E5,V,-2.5",
        ]

        records = phase3a.parse_frame_records(lines)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].i_pair, (0, 1))
        self.assertEqual(records[0].v_pair, (2, 3))
        self.assertEqual(records[1].voltage_mv, -2.5)

    def test_protocol_mismatch_identifies_opposite_drive_frame(self):
        records = [
            phase3a.FrameRecord(i_pair=(0, 6), v_pair=(1, 2), voltage_mv=-1.5),
        ]

        with self.assertRaisesRegex(ValueError, "opposite-drive"):
            phase3a.records_to_vector(records, phase3a.build_adjacent_protocol(12))


class TestPhase3ALogging(unittest.TestCase):
    def test_build_frame_log_row_preserves_pairs_and_value(self):
        record = phase3a.FrameRecord(i_pair=(0, 1), v_pair=(2, 3), voltage_mv=-1.5)

        row = phase3a.build_frame_log_row("run-1", 4, record)

        self.assertEqual(
            row,
            ["run-1", "4", "E1", "E2", "E3", "E4", "-1.500000"],
        )

    def test_default_log_path_uses_mode_name(self):
        path = phase3a.default_log_path(Path("logs"), "adjacent")

        self.assertTrue(str(path).startswith("logs"))
        self.assertIn("phase3a-adjacent", path.name)
        self.assertEqual(path.suffix, ".csv")

    def test_frame_logger_stops_at_frame_limit(self):
        record = phase3a.FrameRecord(i_pair=(0, 1), v_pair=(2, 3), voltage_mv=10.0)

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "limited.csv"
            logger = phase3a.FrameLogger(path, max_frames=1)
            try:
                logger.write_frame("run-1", 0, [record])
                logger.write_frame("run-1", 1, [record])
            finally:
                logger.close()

            rows = path.read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(len(rows), 2)
        self.assertIn("frame_index", rows[0])
        self.assertIn("run-1,0,E1,E2,E3,E4,10.000000", rows[1])


if __name__ == "__main__":
    unittest.main()
