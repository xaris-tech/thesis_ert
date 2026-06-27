import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory

import numpy as np

import phase3a_unified_reconstruct as unified


class TestUnifiedFrameParsing(unittest.TestCase):
    def test_parses_v2_header_and_measurement_units(self):
        lines = [
            "FRAME,2,7,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4",
            "M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,20.000,I,200.000,Q,OK",
            "M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,-18.000,I,180.000,Q,OK",
            "END,7",
        ]

        frame = unified.parse_v2_frame(lines)

        self.assertEqual(frame.frame_id, 7)
        self.assertEqual(frame.pattern, "adjacent")
        self.assertEqual(frame.records[0].polarity, "FWD")
        self.assertEqual(frame.records[0].voltage_mv, 20.0)
        self.assertEqual(frame.records[0].current_ua, 200.0)

    def test_forward_reverse_pair_produces_transfer_resistance(self):
        frame = unified.parse_v2_frame([
            "FRAME,2,7,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4",
            "M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,20.000,I,200.000,Q,OK",
            "M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,-18.000,I,180.000,Q,OK",
            "END,7",
        ])

        values = unified.paired_transfer_resistance(frame)

        self.assertAlmostEqual(values[((0, 1), (2, 3))], 0.1)

    def test_rejects_non_ok_quality_and_tiny_current(self):
        bad_quality = unified.MeasurementRecord("FWD", (0, 1), (2, 3), 1.0, 100.0, "V_RANGE")
        tiny_current = unified.MeasurementRecord("FWD", (0, 1), (2, 3), 1.0, 0.0, "OK")

        with self.assertRaisesRegex(ValueError, "quality"):
            unified.validate_record(bad_quality)
        with self.assertRaisesRegex(ValueError, "current"):
            unified.validate_record(tiny_current)


class TestUnifiedProtocolMapping(unittest.TestCase):
    def test_cli_accepts_positive_diameter_cm(self):
        with patch("sys.argv", [
            "phase3a_unified_reconstruct.py",
            "--diameter-cm",
            "16.5",
        ]):
            args = unified.parse_args()

        self.assertEqual(args.diameter_cm, 16.5)

    def test_pattern_selects_matching_protocol_and_serial_command(self):
        adjacent, adjacent_command = unified.protocol_and_command("adjacent")
        opposite, opposite_command = unified.protocol_and_command("opposite")

        self.assertEqual(adjacent.meas_mat.shape, (12, 9, 2))
        self.assertEqual(opposite.meas_mat.shape, (12, 8, 2))
        self.assertEqual(adjacent_command, b"ma\n")
        self.assertEqual(opposite_command, b"mo\n")

    def test_average_vectors_requires_matching_shapes(self):
        result = unified.average_vectors([np.array([1.0, 3.0]), np.array([3.0, 5.0])])
        self.assertTrue(np.array_equal(result, np.array([2.0, 4.0])))

        with self.assertRaisesRegex(ValueError, "shape"):
            unified.average_vectors([np.array([1.0]), np.array([1.0, 2.0])])

    def test_target_gate_waits_unless_auto_continue_is_enabled(self):
        prompts = []

        unified.wait_for_target(False, prompts.append)
        unified.wait_for_target(True, prompts.append)

        self.assertEqual(len(prompts), 1)
        self.assertIn("target", prompts[0].lower())


class TestBaselineStability(unittest.TestCase):
    def test_safe_acquisition_defaults(self):
        self.assertEqual(unified.DEFAULT_WARMUP_FRAMES, 10)
        self.assertEqual(unified.DEFAULT_BASELINE_FRAMES, 10)
        self.assertEqual(unified.DEFAULT_SETTLE_MS, 30)

    def test_stable_baseline_reports_small_relative_rms(self):
        vectors = [
            np.array([1.00, 2.00, 3.00]),
            np.array([1.01, 1.99, 3.01]),
            np.array([0.99, 2.01, 2.99]),
        ]

        result = unified.assess_baseline_stability(vectors)

        self.assertTrue(result.stable)
        self.assertLess(result.max_relative_rms_percent, 2.0)
        self.assertGreater(result.min_correlation, 0.995)

    def test_low_signal_baseline_can_pass_absolute_drift_limit(self):
        vectors = [
            np.array([0.0007, -0.0001, 0.0002]),
            np.array([0.0001, 0.0004, -0.0002]),
            np.array([-0.0002, 0.0003, 0.0001]),
        ]

        result = unified.assess_baseline_stability(vectors)

        self.assertTrue(result.stable)
        self.assertLess(result.max_absolute_rms_kohm, 0.002)
        self.assertGreater(result.max_relative_rms_percent, 2.0)

    def test_unstable_baseline_is_rejected(self):
        vectors = [
            np.array([1.0, 2.0, 3.0]),
            np.array([3.0, 1.0, 0.5]),
            np.array([0.5, 4.0, 1.0]),
        ]

        result = unified.assess_baseline_stability(vectors)

        self.assertFalse(result.stable)
        with self.assertRaisesRegex(ValueError, "Baseline is unstable"):
            unified.require_stable_baseline(vectors)


class TestControlDriftAnalysis(unittest.TestCase):
    def test_control_report_path_follows_run_csv_name(self):
        path = unified.control_report_path(Path("logs/phase3a-v2-adjacent-run.csv"))

        self.assertEqual(path.name, "phase3a-v2-adjacent-run-stability.csv")

    def test_ranks_unstable_measurement_and_its_electrodes(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        baseline = np.ones(108)
        controls = [baseline.copy() for _ in range(4)]
        controls[0][0] += 0.4
        controls[1][0] -= 0.4

        report = unified.analyze_control_drift(baseline, controls, protocol)

        self.assertEqual(report.pairs[0].i_pair, (0, 1))
        self.assertEqual(report.pairs[0].v_pair, (2, 3))
        self.assertEqual(
            {item.electrode for item in report.electrodes[:4]},
            {0, 1, 2, 3},
        )
        self.assertGreater(report.frames[0].relative_rms_percent, 0.0)

    def test_writes_frame_pair_and_electrode_records(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        baseline = np.ones(108)
        controls = [baseline.copy(), baseline + 0.01]
        report = unified.analyze_control_drift(baseline, controls, protocol)

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "control-stability.csv"
            unified.write_control_report(path, report)
            text = path.read_text(encoding="utf-8")

        self.assertIn("record_type", text)
        self.assertIn("frame,", text)
        self.assertIn("pair,", text)
        self.assertIn("electrode,", text)


class TestReconstructionImageSaving(unittest.TestCase):
    def test_plot_title_can_include_real_body_diameter(self):
        title = unified.reconstruction_title(
            "Phase 3A Adjacent V2 Reconstruction",
            16.5,
        )

        self.assertIn("diameter=16.5 cm", title)

    def test_image_paths_follow_csv_log_name(self):
        contact, average = unified.reconstruction_image_paths(
            Path("logs/phase3a-v2-adjacent-run.csv")
        )

        self.assertEqual(contact.name, "phase3a-v2-adjacent-run-reconstructions.png")
        self.assertEqual(average.name, "phase3a-v2-adjacent-run-average.png")

    def test_saves_twenty_frame_contact_sheet_and_average(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        mesh, _ = unified.base.create_solver(protocol)
        element_count = mesh.element.shape[0]
        frames = [np.full(element_count, index + 1.0) for index in range(20)]

        with TemporaryDirectory() as temp_dir:
            contact = Path(temp_dir) / "contact.png"
            average = Path(temp_dir) / "average.png"
            unified.save_reconstruction_images(mesh, frames, contact, average, "Adjacent")

            self.assertTrue(contact.exists())
            self.assertGreater(contact.stat().st_size, 0)
            self.assertTrue(average.exists())
            self.assertGreater(average.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
