import tempfile
import unittest
from pathlib import Path

import numpy as np

import pyeit_analyzer


class TestAnalyzerLoad(unittest.TestCase):
    def test_load_npz_export_reads_arrays(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "scan.npz"
            np.savez(
                export_path,
                measurements=np.array([[1.0, 2.0], [3.0, 4.0]]),
                delta=np.array([[0.1, 0.2], [0.3, 0.4]]),
                baseline=np.array([[0.9, 1.8], [0.9, 1.8]]),
                channels=np.array(["E1", "E2"]),
                timestamps=np.array(["2026-05-27T13:00:00", "2026-05-27T13:00:01"]),
            )

            loaded = pyeit_analyzer.load_export(export_path)

            self.assertEqual(loaded.channels, ("E1", "E2"))
            self.assertEqual(loaded.measurements.shape, (2, 2))
            self.assertTrue(np.allclose(loaded.delta[1], np.array([0.3, 0.4])))


class TestAnalyzerSummary(unittest.TestCase):
    def test_summarize_export_reports_per_channel_std(self):
        loaded = pyeit_analyzer.LoadedExport(
            source=Path("scan.npz"),
            channels=("E1", "E2"),
            timestamps=("t1", "t2", "t3"),
            measurements=np.array([[10.0, 5.0], [11.0, 7.0], [9.0, 6.0]]),
            delta=np.array([[0.0, 0.0], [1.0, 2.0], [-1.0, 1.0]]),
            baseline=np.array([[10.0, 5.0], [10.0, 5.0], [10.0, 5.0]]),
        )

        summary = pyeit_analyzer.summarize_export(loaded)

        self.assertEqual(summary.scan_count, 3)
        self.assertEqual(summary.channel_count, 2)
        self.assertTrue(np.allclose(summary.delta_mean, np.array([0.0, 1.0])))
        self.assertTrue(np.allclose(summary.delta_std, np.array([0.81649658, 0.81649658])))


if __name__ == "__main__":
    unittest.main()
