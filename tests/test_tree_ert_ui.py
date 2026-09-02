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
        self.assertEqual(map_ax.get_title(), "Latest scan map")
        self.assertEqual(vector_ax.get_title(), "Latest reconstruction vector")
        self.assertEqual(scan_axes[0].get_title(), "Scan 1")

    def test_latest_reconstruction_returns_most_recent_scan(self):
        import numpy as np
        from tree_ert.ui import latest_reconstruction

        latest = latest_reconstruction([
            np.array([1.0, 3.0, 5.0]),
            np.array([3.0, 5.0, 7.0]),
        ])

        self.assertTrue(np.allclose(latest, np.array([3.0, 5.0, 7.0])))
        self.assertEqual(latest_reconstruction([]).size, 0)

    def test_average_reconstruction_vector_averages_frames(self):
        import numpy as np
        from tree_ert.ui import average_reconstruction_vector

        average = average_reconstruction_vector([
            np.array([1.0, 3.0, 5.0]),
            np.array([3.0, 5.0, 7.0]),
        ])

        self.assertTrue(np.allclose(average, np.array([2.0, 4.0, 6.0])))

    def test_reciprocity_summary_counts_sign_flips_apart_from_errors(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.ui import format_reciprocity_summary

        scores = {
            ((0, 1), (2, 3)): unified.ReciprocityScore(0.0, True),
            ((4, 5), (6, 7)): unified.ReciprocityScore(80.0, False),
        }

        summary = format_reciprocity_summary(scores, threshold_percent=10.0)

        # The flipped pair agrees perfectly on magnitude, so it must not be
        # counted as an error (ADR-0008).
        self.assertIn("2 pairs", summary)
        self.assertIn("1 above 10%", summary)
        self.assertIn("1 sign-flipped", summary)

    def test_reciprocity_summary_handles_no_reciprocal_pairs(self):
        from tree_ert.ui import format_reciprocity_summary

        self.assertIn("no reciprocal pairs", format_reciprocity_summary({}))

    def test_status_is_embedded_in_reconstruction_tab(self):
        from tree_ert.ui import debug_tab_titles

        self.assertEqual(
            debug_tab_titles(),
            ("Reconstruction", "Self Test", "Reciprocity", "Health", "Serial", "Files"),
        )
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


class TestPartialCaptureDescription(unittest.TestCase):
    def test_describes_kept_frame_vectors(self):
        from tree_ert.ui import describe_partial_capture

        self.assertEqual(describe_partial_capture([1, 2, 3]), "kept 3 frame vector(s)")
        self.assertEqual(describe_partial_capture([]), "no partial data kept")
        self.assertEqual(describe_partial_capture(None), "no partial data kept")

    def test_describes_kept_target_reconstructions(self):
        from tree_ert.controller import TargetResult
        from tree_ert.ui import describe_partial_capture

        partial = TargetResult(reconstructions=[1, 2], frame_healths=[])

        self.assertEqual(
            describe_partial_capture(partial), "kept 2 target reconstruction(s)"
        )


class TestSettingsPersistence(unittest.TestCase):
    def test_round_trips_settings_through_disk(self):
        from dataclasses import replace
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from tree_ert.settings import UiSettings, load_settings, save_settings

        with TemporaryDirectory() as directory:
            path = Path(directory) / "ui_settings.json"
            original = replace(
                UiSettings.default(),
                dac=75,
                settle_ms=100,
                samples=16,
                lenient_quality=True,
            )

            save_settings(original, path)
            restored = load_settings(path)

            self.assertEqual(restored.dac, 75)
            self.assertEqual(restored.settle_ms, 100)
            self.assertEqual(restored.samples, 16)
            self.assertTrue(restored.lenient_quality)
            self.assertIsInstance(restored.log_dir, Path)

    def test_missing_or_corrupt_file_returns_none_rather_than_raising(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from tree_ert.settings import load_settings

        with TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            corrupt = Path(directory) / "corrupt.json"
            corrupt.write_text("{not json", encoding="utf-8")

            self.assertIsNone(load_settings(missing))
            self.assertIsNone(load_settings(corrupt))

    def test_unknown_and_invalid_keys_fall_back_to_defaults(self):
        from tree_ert.settings import UiSettings, settings_from_dict

        restored = settings_from_dict({"dac": 200, "no_such_field": 1})
        self.assertEqual(restored.dac, 200)

        # dac above the validated ceiling must not produce unusable settings.
        fallback = settings_from_dict({"dac": 99999})
        self.assertEqual(fallback, UiSettings.default())


class TestFrameDiagnosticFormatters(unittest.TestCase):
    @staticmethod
    def _frame(records):
        import phase3a_unified_reconstruct as unified

        return unified.UnifiedFrame(
            frame_id=1,
            pattern="adjacent",
            dac_code=100,
            settle_ms=10,
            sample_count=4,
            records=list(records),
        )

    @staticmethod
    def _record(polarity, i_pair, v_pair, voltage_mv, current_ua, quality="OK"):
        import phase3a_unified_reconstruct as unified

        return unified.MeasurementRecord(
            polarity, i_pair, v_pair, voltage_mv, current_ua, quality
        )

    def test_probe_summary_names_the_weakest_pair_and_verdict(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.ui import format_frame_probe

        frame = self._frame([
            self._record("FWD", (0, 1), (2, 3), 20.0, 200.0),
            self._record("FWD", (0, 1), (3, 4), 5.0, 40.0),
        ])

        summary = format_frame_probe(unified.probe_frame_health(frame))

        self.assertIn("PASS", summary)
        self.assertIn("min_current=40.000uA", summary)
        self.assertIn("V=E4-E5", summary)

    def test_polarization_summary_reports_decay(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.ui import format_polarization_summary

        frame = self._frame([
            self._record("FWD", (0, 1), (2, 3), 10.0, 300.0),
            self._record("FWD", (0, 1), (3, 4), 10.0, 100.0),
        ])

        summary = format_polarization_summary(unified.analyze_polarization(frame))

        self.assertIn("FLAGGED", summary)
        self.assertIn("worst_decay=3.00x", summary)

    def test_offset_summary_reports_dominated_fraction(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.ui import format_offset_summary

        frame = self._frame([
            self._record("FWD", (0, 1), (2, 3), 46.0, 200.0),
            self._record("REV", (1, 0), (2, 3), 46.0, 200.0),
        ])

        summary = format_offset_summary(unified.analyze_offset_domination(frame))

        self.assertIn("FLAGGED", summary)
        self.assertIn("1/1 pairs", summary)

    def test_electrode_summary_lists_weakest_drive_currents(self):
        import phase3a_unified_reconstruct as unified
        from tree_ert.ui import format_electrode_health_summary

        frame = self._frame([
            self._record("FWD", (0, 1), (2, 3), 20.0, 200.0),
        ])

        summary = format_electrode_health_summary(
            unified.analyze_electrode_health(frame), limit=2
        )

        self.assertIn("drive=", summary)


if __name__ == "__main__":
    unittest.main()
