import sys
import types
import unittest
from unittest.mock import patch


class TestTreeErtUiEntrypoint(unittest.TestCase):
    def test_entrypoint_parses_demo_and_port(self):
        import tree_ert_app

        with patch.object(sys, "argv", ["tree_ert_app.py", "--demo", "--port", "COM7"]):
            args = tree_ert_app.parse_args()

        self.assertTrue(args.demo)
        self.assertEqual(args.port, "COM7")

    def test_main_lazily_imports_and_dispatches_to_run_app(self):
        import tree_ert_app

        calls = []
        fake_ui = types.SimpleNamespace(
            run_app=lambda **kwargs: calls.append(kwargs),
        )

        with patch.dict(sys.modules, {"tree_ert.ui": fake_ui}):
            with patch.object(sys, "argv", ["tree_ert_app.py", "--demo", "--port", "COM7"]):
                tree_ert_app.main()

        self.assertEqual(calls, [{"demo": True, "port": "COM7"}])

    def test_reconstruction_figure_has_map_and_vector_axes(self):
        from tree_ert.ui import build_reconstruction_figure

        figure, map_ax, vector_ax, scan_axes = build_reconstruction_figure()

        self.assertEqual(len(figure.axes), 6)
        self.assertIs(figure.axes[0], map_ax)
        self.assertIs(figure.axes[1], vector_ax)
        self.assertEqual(tuple(figure.axes[2:]), scan_axes)
        self.assertEqual(map_ax.get_title(), "Average difference reconstruction")
        self.assertEqual(vector_ax.get_title(), "Average measurement-difference vector")
        self.assertEqual(scan_axes[0].get_title(), "Scan 1")

    def test_live_reconstruction_can_show_current_frame_only(self):
        from tree_ert.ui import DebugApp

        app = DebugApp(demo=True, port="COM3")
        try:
            app._draw_live_placeholder_panels()
            self.assertEqual(app.scan_axes[0].get_title(), "Live")
        finally:
            app.destroy()

    def test_reading_figure_has_current_and_vector_axes(self):
        from tree_ert.ui import build_reading_figure

        figure, current_ax, vector_ax = build_reading_figure()

        self.assertEqual(len(figure.axes), 2)
        self.assertIs(figure.axes[0], current_ax)
        self.assertIs(figure.axes[1], vector_ax)
        self.assertEqual(current_ax.get_title(), "Latest measured current by record")
        self.assertEqual(vector_ax.get_title(), "Latest normalized transfer-resistance vector")

    def test_average_reconstruction_vector_averages_frames(self):
        import numpy as np
        from tree_ert.ui import average_reconstruction_vector

        average = average_reconstruction_vector([
            np.array([1.0, 3.0, 5.0]),
            np.array([3.0, 5.0, 7.0]),
        ])

        self.assertTrue(np.allclose(average, np.array([2.0, 4.0, 6.0])))

    def test_status_is_embedded_in_reconstruction_tab(self):
        from tree_ert.ui import debug_tab_titles

        self.assertEqual(debug_tab_titles(), ("Reconstruction", "Live Readings", "Health", "Serial", "Files"))
        self.assertNotIn("Status", debug_tab_titles())

    def test_preview_indices_spread_across_reconstructions(self):
        from tree_ert.ui import preview_scan_indices

        self.assertEqual(preview_scan_indices(0), ())
        self.assertEqual(preview_scan_indices(3), (0, 1, 2))
        self.assertEqual(preview_scan_indices(20), (0, 6, 13, 19))

    def test_control_drift_summary_reports_result(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.ui import format_control_drift_summary

        report = unified.ControlDriftReport(
            frames=[
                unified.ControlFrameMetric(
                    frame=1,
                    rms_kohm=0.001,
                    relative_rms_percent=0.5,
                    correlation=0.999,
                )
            ],
            pairs=[
                unified.ControlPairMetric(
                    index=0,
                    i_pair=(0, 1),
                    v_pair=(2, 3),
                    rms_kohm=0.002,
                    max_abs_kohm=0.003,
                )
            ],
            electrodes=[
                unified.ControlElectrodeMetric(electrode=2, mean_pair_rms_kohm=0.002),
            ],
        )

        summary = format_control_drift_summary(report)

        self.assertIn("Control drift result", summary)
        self.assertIn("max_rms=0.001000kOhm", summary)
        self.assertIn("max_relative=0.50%", summary)
        self.assertIn("min_corr=0.999000", summary)
        self.assertIn("worst_pair=I=E1-E2 V=E3-E4", summary)
        self.assertIn("worst_electrode=E3", summary)

    def test_drift_tune_summary_reports_best_settings(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.controller import DriftTuneAttempt, DriftTuneResult
        from tree_ert.settings import UiSettings
        from tree_ert.ui import format_drift_tune_summary

        report = unified.ControlDriftReport(
            frames=[
                unified.ControlFrameMetric(
                    frame=1,
                    rms_kohm=0.001,
                    relative_rms_percent=0.5,
                    correlation=0.999,
                )
            ],
            pairs=[],
            electrodes=[],
        )
        attempt = DriftTuneAttempt(
            UiSettings.default(),
            report,
        )
        summary = format_drift_tune_summary(DriftTuneResult([attempt], attempt))

        self.assertIn("Drift tuning result", summary)
        self.assertIn("best_settle=30ms", summary)
        self.assertIn("best_samples=4", summary)
        self.assertIn("max_relative=0.50%", summary)


if __name__ == "__main__":
    unittest.main()
