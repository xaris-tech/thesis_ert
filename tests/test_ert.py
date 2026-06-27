import unittest

import numpy as np

import ert


class TestScanParsing(unittest.TestCase):
    def test_parse_scan_lines_extracts_measurement_values(self):
        lines = ["0,E3,151.0", "1,E4,150.5"]
        parsed = ert.parse_scan_lines(lines)
        self.assertEqual(parsed.channels, ("E3", "E4"))
        self.assertTrue(np.allclose(parsed.values, np.array([151.0, 150.5])))


class TestExportPayload(unittest.TestCase):
    def test_build_export_payload_includes_delta_matrix(self):
        baseline = np.array([151.0, 150.5])
        scans = [
            ert.MeasurementRecord(
                timestamp="2026-05-27T13:00:00",
                channels=("E3", "E4"),
                values=np.array([156.5, 158.0]),
                delta=np.array([5.5, 7.5]),
            )
        ]
        payload = ert.build_export_payload(scans, baseline)
        self.assertEqual(payload["measurements"].shape, (1, 2))
        self.assertTrue(np.allclose(payload["delta"], np.array([[5.5, 7.5]])))


class TestHistoryMatrix(unittest.TestCase):
    def test_build_recent_delta_matrix_returns_latest_rows_for_eight_channels(self):
        records = [
            ert.MeasurementRecord(
                timestamp=f"2026-05-27T13:00:0{index}",
                channels=("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"),
                values=np.arange(8, dtype=float) + index,
                delta=np.arange(8, dtype=float) - index,
            )
            for index in range(3)
        ]
        matrix = ert.build_recent_delta_matrix(records, limit=2)
        self.assertEqual(matrix.shape, (2, 8))
        self.assertTrue(np.allclose(matrix[0], np.arange(8, dtype=float) - 1))
        self.assertTrue(np.allclose(matrix[1], np.arange(8, dtype=float) - 2))


class TestSessionState(unittest.TestCase):
    def test_apply_scan_updates_delta_against_baseline(self):
        session = ert.AcquisitionSession()
        baseline_scan = ert.ParsedScan(
            channels=("E3", "E4"),
            values=np.array([151.0, 150.5]),
            raw_lines=("0,E3,151.0", "1,E4,150.5"),
        )
        current_scan = ert.ParsedScan(
            channels=("E3", "E4"),
            values=np.array([156.5, 158.0]),
            raw_lines=("0,E3,156.5", "1,E4,158.0"),
        )
        session.apply_scan(baseline_scan)
        record = session.apply_scan(current_scan)
        self.assertTrue(np.allclose(record.delta, np.array([5.5, 7.5])))


if __name__ == "__main__":
    unittest.main()
