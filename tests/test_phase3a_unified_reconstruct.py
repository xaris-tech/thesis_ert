import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock
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

    def test_parses_skip_one_v2_header(self):
        frame = unified.parse_v2_frame([
            "FRAME,2,8,SKIP-1,DAC,150,SETTLE,100,SAMPLES,10",
            "M,P,FWD,I+,E1,I-,E3,V+,E4,V-,E5,V,20.000,I,200.000,Q,OK",
            "M,P,REV,I+,E3,I-,E1,V+,E4,V-,E5,V,-18.000,I,180.000,Q,OK",
            "END,8",
        ])

        self.assertEqual(frame.pattern, "skip-1")

    def test_parses_skip_two_v2_header(self):
        frame = unified.parse_v2_frame([
            "FRAME,2,9,SKIP-2,DAC,150,SETTLE,100,SAMPLES,10",
            "M,P,FWD,I+,E1,I-,E4,V+,E5,V-,E6,V,20.000,I,200.000,Q,OK",
            "M,P,REV,I+,E4,I-,E1,V+,E5,V-,E6,V,-18.000,I,180.000,Q,OK",
            "END,9",
        ])

        self.assertEqual(frame.pattern, "skip-2")

    def test_forward_reverse_pair_produces_transfer_resistance(self):
        frame = unified.parse_v2_frame([
            "FRAME,2,7,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4",
            "M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,20.000,I,200.000,Q,OK",
            "M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,-18.000,I,180.000,Q,OK",
            "END,7",
        ])

        values = unified.paired_transfer_resistance(frame)

        # Negated to match PyEIT's subtract_row convention (validity-audit D-02).
        self.assertAlmostEqual(values[((0, 1), (2, 3))], -0.1)

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

    def test_cli_can_bypass_baseline_stability_gate(self):
        with patch("sys.argv", [
            "phase3a_unified_reconstruct.py",
            "--allow-unstable-baseline",
        ]):
            args = unified.parse_args()

        self.assertTrue(args.allow_unstable_baseline)

    def test_pattern_selects_matching_protocol_and_serial_command(self):
        adjacent, adjacent_command = unified.protocol_and_command("adjacent")
        opposite, opposite_command = unified.protocol_and_command("opposite")
        skip_one, skip_one_command = unified.protocol_and_command("skip-1")
        skip_two, skip_two_command = unified.protocol_and_command("skip-2")

        self.assertEqual(adjacent.meas_mat.shape, (12, 9, 2))
        self.assertEqual(opposite.meas_mat.shape, (12, 8, 2))
        self.assertEqual(skip_one.ex_mat[0].tolist(), [0, 2])
        self.assertEqual(skip_one.meas_mat.shape, (12, 8, 2))
        self.assertEqual(skip_two.ex_mat[0].tolist(), [0, 3])
        self.assertEqual(skip_two.meas_mat.shape, (12, 8, 2))
        self.assertEqual(adjacent_command, b"ma\n")
        self.assertEqual(opposite_command, b"mo\n")
        self.assertEqual(skip_one_command, b"ms\n")
        self.assertEqual(skip_two_command, b"mk\n")

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

    def test_warmup_discards_low_current_frame_without_raising(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        invalid_frame = unified.parse_v2_frame([
            "FRAME,2,1,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4",
            "M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,20.000,I,0.100,Q,I_LOW",
            "M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,-18.000,I,0.100,Q,I_LOW",
            "END,1",
        ])

        with patch.object(unified, "request_frame", return_value=invalid_frame):
            ser = MagicMock()
            unified.discard_warmup_frames(ser, 1, "adjacent")


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

    def test_low_signal_baseline_is_rejected_despite_small_absolute_drift(self):
        # An offset-dominated rig collapses toward zero, so its absolute drift is
        # tiny while its shape is noise. This used to pass on the absolute arm
        # alone (validity-audit D-03).
        vectors = [
            np.array([0.0007, -0.0001, 0.0002]),
            np.array([0.0001, 0.0004, -0.0002]),
            np.array([-0.0002, 0.0003, 0.0001]),
        ]

        result = unified.assess_baseline_stability(vectors)

        self.assertFalse(result.stable)
        self.assertLess(result.max_absolute_rms_kohm, 0.002)
        self.assertGreater(result.max_relative_rms_percent, 2.0)

    def test_real_signal_baseline_is_not_failed_by_the_absolute_threshold(self):
        # 1 percent drift on a ~2 kOhm signal exceeds the old 2 ohm absolute
        # arm; stability must be judged on shape, not on drive level.
        vectors = [
            np.array([1.00, 2.00, 3.00]),
            np.array([1.01, 1.99, 3.01]),
        ]

        result = unified.assess_baseline_stability(vectors)

        self.assertTrue(result.stable)
        self.assertGreater(result.max_absolute_rms_kohm, unified.MAX_BASELINE_ABSOLUTE_RMS_KOHM)

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

    def test_unstable_baseline_can_be_allowed_temporarily(self):
        vectors = [
            np.array([1.0, 2.0, 3.0]),
            np.array([3.0, 1.0, 0.5]),
            np.array([0.5, 4.0, 1.0]),
        ]

        result = unified.require_stable_baseline(
            vectors,
            allow_unstable=True,
        )

        self.assertFalse(result.stable)


class TestControlDriftAnalysis(unittest.TestCase):
    def test_control_report_path_follows_run_csv_name(self):
        path = unified.control_report_path(Path("logs/phase3a-v2-adjacent-run.csv"))

        self.assertEqual(path.name, "phase3a-v2-adjacent-run-stability.csv")

    def test_consistency_report_path_follows_run_csv_name(self):
        path = unified.consistency_report_path(Path("logs/phase3a-v2-adjacent-run.csv"))

        self.assertEqual(path.name, "phase3a-v2-adjacent-run-consistency.csv")

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


class TestBestEffortFiltering(unittest.TestCase):
    def test_ranks_baseline_pair_instability(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        baseline_vectors = [
            np.ones(108),
            np.ones(108),
            np.ones(108),
        ]
        baseline_vectors[0][0] += 0.30
        baseline_vectors[1][0] -= 0.20
        baseline_vectors[2][10] += 0.05

        scores = unified.analyze_baseline_pair_health(baseline_vectors, protocol)

        self.assertEqual(scores[0].index, 0)
        self.assertEqual(scores[0].i_pair, (0, 1))
        self.assertEqual(scores[0].v_pair, (2, 3))
        self.assertGreater(scores[0].baseline_rms_kohm, scores[1].baseline_rms_kohm)

    def test_best_effort_filter_replaces_bad_pairs_with_baseline_values(self):
        protocol, _ = unified.protocol_and_command("adjacent")
        baseline_vectors = [
            np.ones(108),
            np.ones(108),
            np.ones(108),
        ]
        scores = unified.analyze_baseline_pair_health(baseline_vectors, protocol)
        current = np.ones(108)
        current[0] = 1.50
        current[1] = 1.01

        result = unified.filter_frame_vector_best_effort(
            baseline=np.ones(108),
            current=current,
            pair_scores=scores,
            current_median_ua=180.0,
            current_spread_ua=12.5,
        )

        self.assertEqual(result.dropped_indexes, [0])
        self.assertAlmostEqual(result.filtered_vector[0], 1.0)
        self.assertAlmostEqual(result.filtered_vector[1], 1.01)
        self.assertEqual(result.frame_health.quality_label, "debug-best-effort")
        self.assertEqual(result.frame_health.kept_pairs, 107)
        self.assertEqual(result.frame_health.current_spread_ua, 12.5)


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


def make_frame(records, frame_id=1, pattern="adjacent"):
    return unified.UnifiedFrame(
        frame_id=frame_id,
        pattern=pattern,
        dac_code=100,
        settle_ms=10,
        sample_count=4,
        records=list(records),
    )


def record(polarity, i_pair, v_pair, voltage_mv, current_ua, quality="OK"):
    return unified.MeasurementRecord(
        polarity, i_pair, v_pair, voltage_mv, current_ua, quality
    )


class TestFrameProbe(unittest.TestCase):
    def test_reports_weakest_measurement_not_the_average(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 20.0, 200.0),
            record("REV", (1, 0), (2, 3), -20.0, 200.0),
            record("FWD", (0, 1), (3, 4), 5.0, 4.0),
        ])

        probe = unified.probe_frame_health(frame)

        self.assertAlmostEqual(probe.min_current_ua, 4.0)
        self.assertEqual(probe.min_current_v_pair, (3, 4))
        self.assertAlmostEqual(probe.margin_ratio, 4.0)
        self.assertAlmostEqual(probe.median_current_ua, 200.0)
        self.assertTrue(probe.passes)

    def test_counts_quality_flags_and_fails_on_bad_records(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 20.0, 200.0),
            record("FWD", (0, 1), (3, 4), 1.0, 0.5, "I_LOW"),
        ])

        probe = unified.probe_frame_health(frame)

        self.assertEqual(probe.quality_counts, {"OK": 1, "I_LOW": 1})
        self.assertFalse(probe.passes)


class TestPolarizationDetection(unittest.TestCase):
    def test_flags_current_decaying_across_a_fixed_injection_pair(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 10.0, 300.0),
            record("FWD", (0, 1), (3, 4), 10.0, 120.0),
            record("FWD", (0, 1), (4, 5), 10.0, 40.0),
        ])

        report = unified.analyze_polarization(frame)

        self.assertTrue(report.flagged)
        self.assertAlmostEqual(report.worst_decay_ratio, 7.5)
        self.assertAlmostEqual(report.metrics[0].decreasing_fraction, 1.0)

    def test_non_monotonic_swing_is_not_reported_as_polarisation(self):
        # Large first-to-last ratio, but the steps are not a monotonic slide.
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 10.0, 300.0),
            record("FWD", (0, 1), (3, 4), 10.0, 400.0),
            record("FWD", (0, 1), (4, 5), 10.0, 350.0),
            record("FWD", (0, 1), (5, 6), 10.0, 500.0),
            record("FWD", (0, 1), (6, 7), 10.0, 40.0),
        ])

        report = unified.analyze_polarization(frame)

        self.assertGreater(report.worst_decay_ratio, unified.MAX_POLARIZATION_DECAY_RATIO)
        self.assertFalse(report.flagged)

    def test_steady_current_is_not_flagged(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 10.0, 200.0),
            record("FWD", (0, 1), (3, 4), 10.0, 199.0),
            record("FWD", (0, 1), (4, 5), 10.0, 201.0),
        ])

        report = unified.analyze_polarization(frame)

        self.assertFalse(report.flagged)


class TestOffsetDomination(unittest.TestCase):
    def test_flags_forward_reverse_voltages_that_do_not_invert(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 46.0, 200.0),
            record("REV", (1, 0), (2, 3), 46.0, 200.0),
        ])

        report = unified.analyze_offset_domination(frame)

        self.assertTrue(report.flagged)
        self.assertEqual(report.dominated_pairs, 1)
        self.assertAlmostEqual(report.dominated_fraction, 1.0)

    def test_inverting_pair_is_not_flagged(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 20.0, 200.0),
            record("REV", (1, 0), (2, 3), -19.0, 200.0),
        ])

        report = unified.analyze_offset_domination(frame)

        self.assertFalse(report.flagged)
        self.assertEqual(report.dominated_pairs, 0)


class TestElectrodeHealth(unittest.TestCase):
    def test_separates_drive_and_sense_roles_per_electrode(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 20.0, 100.0),
            record("FWD", (0, 1), (4, 5), 30.0, 50.0),
            record("FWD", (2, 3), (0, 1), 10.0, 8.0, "I_LOW"),
        ])

        health = {item.electrode: item for item in unified.analyze_electrode_health(frame)}

        self.assertEqual(health[0].drive_count, 2)
        self.assertAlmostEqual(health[0].drive_median_ua, 75.0)
        self.assertEqual(health[0].sense_count, 1)
        self.assertEqual(health[0].bad_quality_count, 1)
        self.assertEqual(health[6].drive_count, 0)


class TestElectrodeRemap(unittest.TestCase):
    def test_identity_by_default(self):
        self.assertEqual(unified.remap_electrode(5), 5)
        key = ((0, 1), (2, 3))
        self.assertEqual(unified.remap_measurement_key(key), key)

    def test_reversed_ring_mirrors_about_the_offset_axis(self):
        # offset=6, reversed: E1<->E7, E2<->E6, E3<->E5, E4 and E10 fixed.
        pairs = {0: 6, 1: 5, 2: 4, 3: 3, 5: 1, 6: 0, 9: 9, 7: 11, 11: 7}
        for source, expected in pairs.items():
            self.assertEqual(
                unified.remap_electrode(source, offset=6, reversed_ring=True),
                expected,
                f"E{source + 1}",
            )

    def test_offset_rotates_the_ring(self):
        self.assertEqual(unified.remap_electrode(0, offset=3), 3)
        self.assertEqual(unified.remap_electrode(11, offset=3), 2)

    def test_remap_applies_to_both_pairs_of_a_key(self):
        remapped = unified.remap_measurement_key(
            ((0, 1), (5, 6)), offset=6, reversed_ring=True
        )
        self.assertEqual(remapped, ((6, 5), (1, 0)))


class TestLenientQualityHandling(unittest.TestCase):
    def test_lenient_mode_skips_bad_records_instead_of_raising(self):
        frame = make_frame([
            record("FWD", (0, 1), (2, 3), 20.0, 200.0),
            record("REV", (1, 0), (2, 3), -18.0, 180.0),
            record("FWD", (0, 1), (3, 4), 5.0, 0.4, "I_LOW"),
            record("REV", (1, 0), (3, 4), -5.0, 180.0),
        ])

        with self.assertRaises(ValueError):
            unified.paired_transfer_resistance(frame)

        values = unified.paired_transfer_resistance(frame, strict=False)

        self.assertEqual(list(values), [((0, 1), (2, 3))])
        # Negated to match PyEIT's subtract_row convention (validity-audit D-02).
        self.assertAlmostEqual(values[((0, 1), (2, 3))], -0.1)

    def test_missing_values_are_filled_from_a_reference(self):
        vector = np.asarray([1.0, float("nan"), 3.0])
        reference = np.asarray([9.0, 5.0, 9.0])

        self.assertEqual(unified.missing_value_indexes(vector), [1])
        filled = unified.fill_missing_values(vector, reference)
        np.testing.assert_allclose(filled, [1.0, 5.0, 3.0])

    def test_average_vectors_ignores_missing_entries(self):
        vectors = [
            np.asarray([1.0, float("nan")]),
            np.asarray([3.0, 4.0]),
        ]

        average = unified.average_vectors(vectors)

        np.testing.assert_allclose(average, [2.0, 4.0])


class TestReciprocityCheck(unittest.TestCase):
    def test_scores_percent_error_between_reciprocal_pairs_once(self):
        values = {
            ((0, 1), (2, 3)): 1.00,
            ((2, 3), (0, 1)): 1.10,
            ((4, 5), (6, 7)): 2.00,  # no reciprocal captured, not scored
        }

        errors = unified.reciprocity_errors(values)

        self.assertEqual(len(errors), 1)
        key = next(iter(errors))
        self.assertIn(key, [((0, 1), (2, 3)), ((2, 3), (0, 1))])
        # ADR-0008: relative to the larger magnitude, not the mean.
        self.assertAlmostEqual(errors[key], 100.0 * 0.10 / 1.10, places=6)

    def test_score_is_monotonic_across_a_sign_boundary(self):
        # ADR-0008: the previous mean-magnitude denominator returned exactly
        # 200% for all three of these, so the column could not rank.
        def score(a, b):
            values = {((0, 1), (2, 3)): a, ((2, 3), (0, 1)): b}
            return next(iter(unified.reciprocity_scores(values).values())).error_percent

        near, mid, far = score(1.0, -1.0), score(1.0, -10.0), score(1.0, -100.0)

        self.assertLess(near, mid)
        self.assertLess(mid, far)

    def test_sign_flip_is_reported_separately_from_magnitude(self):
        values = {((0, 1), (2, 3)): 1.0, ((2, 3), (0, 1)): -1.0}

        score = next(iter(unified.reciprocity_scores(values).values()))

        # Magnitudes agree perfectly; only the sign disagrees.
        self.assertAlmostEqual(score.error_percent, 0.0)
        self.assertTrue(score.sign_flipped)

    def test_matching_signs_are_not_flagged_as_flipped(self):
        values = {((0, 1), (2, 3)): 1.0, ((2, 3), (0, 1)): 2.0}

        score = next(iter(unified.reciprocity_scores(values).values()))

        self.assertFalse(score.sign_flipped)
        self.assertAlmostEqual(score.error_percent, 50.0)

    def test_filter_drops_both_orientations_above_threshold(self):
        values = {
            ((0, 1), (2, 3)): 1.00,
            ((2, 3), (0, 1)): 2.00,  # ~67% error, should drop
            ((4, 5), (6, 7)): 3.00,
            ((6, 7), (4, 5)): 3.05,  # ~1.6% error, should keep
        }

        kept, dropped = unified.filter_by_reciprocity(values, threshold_percent=10.0)

        self.assertEqual(dropped, [((0, 1), (2, 3))])
        self.assertNotIn(((0, 1), (2, 3)), kept)
        self.assertNotIn(((2, 3), (0, 1)), kept)
        self.assertIn(((4, 5), (6, 7)), kept)
        self.assertIn(((6, 7), (4, 5)), kept)

    def test_average_measurement_values_averages_across_frames(self):
        frames = [
            {((0, 1), (2, 3)): 1.0, ((4, 5), (6, 7)): 5.0},
            {((0, 1), (2, 3)): 3.0},
        ]

        averaged = unified.average_measurement_values(frames)

        self.assertAlmostEqual(averaged[((0, 1), (2, 3))], 2.0)
        self.assertAlmostEqual(averaged[((4, 5), (6, 7))], 5.0)


class TestDacAddressDiscovery(unittest.TestCase):
    def test_parses_addresses_between_the_scan_markers(self):
        lines = [
            "[INFO] banner",
            "I2C_SCAN,BEGIN",
            "I2C_DEVICE,0x48",
            "I2C_DEVICE,0x61",
            "I2C_SCAN,END,FOUND,2",
            "I2C_DEVICE,0x60",
        ]

        self.assertEqual(unified.parse_i2c_scan(lines), [0x48, 0x61])

    def test_ignores_malformed_device_lines(self):
        lines = ["I2C_SCAN,BEGIN", "I2C_DEVICE,junk", "I2C_DEVICE,0x60", "I2C_SCAN,END"]

        self.assertEqual(unified.parse_i2c_scan(lines), [0x60])

    def test_selects_the_only_mcp4725_candidate(self):
        self.assertEqual(unified.select_dac_address([0x48, 0x61]), 0x61)
        self.assertEqual(unified.select_dac_address([0x48, 0x60]), 0x60)

    def test_refuses_to_guess_between_two_candidates(self):
        # Both 0x60 and 0x61 answering means the bus cannot say which is the
        # DAC; binding to whichever was listed first would be a coin flip.
        self.assertIsNone(unified.select_dac_address([0x48, 0x60, 0x61]))

    def test_returns_none_when_no_candidate_is_present(self):
        self.assertIsNone(unified.select_dac_address([0x48]))
        self.assertIsNone(unified.select_dac_address([]))

    def test_command_is_newline_terminated_lowercase_hex(self):
        self.assertEqual(unified.dac_address_command(0x60), b"b60\n")
        self.assertEqual(unified.dac_address_command(0x61), b"b61\n")

    def test_command_rejects_addresses_outside_the_mcp4725_span(self):
        with self.assertRaises(ValueError):
            unified.dac_address_command(0x48)


if __name__ == "__main__":
    unittest.main()
