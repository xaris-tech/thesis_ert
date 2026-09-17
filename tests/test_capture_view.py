import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase3a_unified_reconstruct as unified
from tree_ert import capture_view


def record(polarity, i_pair, v_pair, voltage_mv, current_ua=200.0, quality="OK"):
    return unified.MeasurementRecord(
        polarity=polarity,
        i_pair=i_pair,
        v_pair=v_pair,
        voltage_mv=voltage_mv,
        current_ua=current_ua,
        quality=quality,
    )


def frame(records, frame_id=1):
    return unified.UnifiedFrame(
        frame_id=frame_id,
        pattern="ADJACENT",
        dac_code=100,
        settle_ms=10,
        sample_count=4,
        records=records,
    )


def reciprocal_frame(forward_mv=200.0, reciprocal_mv=None, current_ua=200.0):
    """One frame holding a reciprocal pair: I:E1,E2/V:E3,E4 and its swap.

    At equal current, a transfer resistance of |v|/current appears for each, so
    equal voltages mean reciprocity is satisfied. ``reciprocal_mv`` defaults to
    ``forward_mv`` so that varying one argument moves the whole frame to a new
    resistance rather than leaving a second pair behind at the old one.
    """
    if reciprocal_mv is None:
        reciprocal_mv = forward_mv
    return frame(
        [
            record("FWD", (0, 1), (2, 3), forward_mv, current_ua),
            record("REV", (1, 0), (2, 3), -forward_mv, current_ua),
            record("FWD", (2, 3), (0, 1), reciprocal_mv, current_ua),
            record("REV", (3, 2), (0, 1), -reciprocal_mv, current_ua),
        ]
    )


class LabelTests(unittest.TestCase):
    def test_electrode_labels_are_one_based(self):
        self.assertEqual(capture_view.electrode_label(0), "E1")
        self.assertEqual(capture_view.electrode_label(11), "E12")

    def test_pair_label_names_drive_and_sense(self):
        self.assertEqual(
            capture_view.pair_label(((0, 1), (2, 3))), "I:E1,E2 V:E3,E4"
        )


class RecordRowTests(unittest.TestCase):
    def test_rows_preserve_capture_order(self):
        # Capture order is evidence: re-sorting would hide a polarity sequence
        # that had stopped alternating.
        rows = capture_view.record_rows(
            frame(
                [
                    record("FWD", (0, 1), (2, 3), 10.0),
                    record("REV", (1, 0), (2, 3), -10.0),
                    record("FWD", (0, 1), (3, 4), 5.0),
                ]
            )
        )
        self.assertEqual([r.polarity for r in rows], ["FWD", "REV", "FWD"])

    def test_row_carries_electrode_labels_and_derived_resistance(self):
        row = capture_view.record_rows(
            frame([record("FWD", (0, 1), (2, 3), 40.0, current_ua=200.0)])
        )[0]
        self.assertEqual((row.i_plus, row.i_minus), ("E1", "E2"))
        self.assertEqual((row.v_plus, row.v_minus), ("E3", "E4"))
        self.assertAlmostEqual(row.resistance_kohm, 0.2)
        self.assertTrue(row.ok)

    def test_zero_current_gives_no_resistance_rather_than_infinity(self):
        row = capture_view.record_rows(
            frame([record("FWD", (0, 1), (2, 3), 40.0, current_ua=0.0, quality="I_LOW")])
        )[0]
        self.assertIsNone(row.resistance_kohm)
        self.assertFalse(row.ok)

    def test_negative_current_still_yields_positive_magnitude_resistance(self):
        row = capture_view.record_rows(
            frame([record("REV", (1, 0), (2, 3), -40.0, current_ua=-200.0)])
        )[0]
        self.assertAlmostEqual(row.resistance_kohm, -0.2)


class FrameSummaryTests(unittest.TestCase):
    def test_counts_qualities_and_ok_fraction(self):
        summary = capture_view.frame_summary(
            frame(
                [
                    record("FWD", (0, 1), (2, 3), 40.0),
                    record("REV", (1, 0), (2, 3), -40.0),
                    record("FWD", (0, 1), (3, 4), 1.0, quality="I_LOW"),
                    record("REV", (1, 0), (3, 4), -1.0, quality="I_LOW"),
                ]
            )
        )
        self.assertEqual(summary.record_count, 4)
        self.assertEqual(summary.ok_count, 2)
        self.assertEqual(summary.quality_counts["I_LOW"], 2)
        self.assertAlmostEqual(summary.ok_fraction, 0.5)

    def test_current_statistics_use_magnitudes(self):
        summary = capture_view.frame_summary(
            frame(
                [
                    record("FWD", (0, 1), (2, 3), 40.0, current_ua=100.0),
                    record("REV", (1, 0), (2, 3), -40.0, current_ua=-300.0),
                ]
            )
        )
        self.assertAlmostEqual(summary.min_current_ua, 100.0)
        self.assertAlmostEqual(summary.max_current_ua, 300.0)
        self.assertAlmostEqual(summary.median_current_ua, 200.0)

    def test_bad_records_are_summarised_not_raised(self):
        # The frame that would raise in the CLI's strict mode is exactly the one
        # the operator needs summarised.
        summary = capture_view.frame_summary(
            frame([record("FWD", (0, 1), (2, 3), 40.0, quality="I_LOW")])
        )
        self.assertEqual(summary.ok_count, 0)
        self.assertIsNone(summary.median_resistance_kohm)

    def test_resistance_is_reported_without_a_verdict(self):
        # ADR-0026 removed the fixed 200 ohm - 2 kohm window: the measured trunk
        # baseline median is 9.4 ohm, so the band flagged every real scan.
        summary = capture_view.frame_summary(reciprocal_frame(forward_mv=200.0))
        self.assertAlmostEqual(summary.median_resistance_kohm, 1.0)
        self.assertFalse(hasattr(summary, "in_target_window"))

    def test_a_low_resistance_specimen_is_not_flagged_for_being_low(self):
        # 17 ohm on the cut trunk is normal; the old window called it an error.
        summary = capture_view.frame_summary(reciprocal_frame(forward_mv=3.4))
        self.assertLess(summary.median_resistance_kohm, 0.02)
        self.assertFalse(summary.quantisation_limited)

    def test_interleaved_polarity_passes(self):
        self.assertTrue(capture_view.frame_summary(reciprocal_frame()).polarity_alternates)

    def test_two_forwards_in_a_row_flags_polarisation_risk(self):
        summary = capture_view.frame_summary(
            frame(
                [
                    record("FWD", (0, 1), (2, 3), 40.0),
                    record("FWD", (0, 1), (3, 4), 40.0),
                    record("REV", (1, 0), (2, 3), -40.0),
                ]
            )
        )
        self.assertFalse(summary.polarity_alternates)

    def test_single_record_frame_is_not_reported_as_non_alternating(self):
        summary = capture_view.frame_summary(
            frame([record("FWD", (0, 1), (2, 3), 40.0)])
        )
        self.assertTrue(summary.polarity_alternates)


class QuantisationTests(unittest.TestCase):
    """The check that replaced the fixed resistance window (ADR-0026).

    It detects the failure recorded in docs/validity-audit.md on 2026-08-27:
    forward and reverse returning identical counts because one ADC step was
    larger than the IR drop, collapsing the differential to exactly zero.
    """

    def test_range_selection_mirrors_the_firmware(self):
        # Finest range whose full scale covers the magnitude with 1.25 headroom.
        self.assertAlmostEqual(capture_view.voltage_lsb_mv(1.0), 256.0 / 32768.0)
        self.assertAlmostEqual(capture_view.voltage_lsb_mv(200.0), 256.0 / 32768.0)
        # 205 * 1.25 = 256.25, just past the finest range.
        self.assertAlmostEqual(capture_view.voltage_lsb_mv(205.0), 512.0 / 32768.0)
        self.assertAlmostEqual(capture_view.voltage_lsb_mv(3000.0), 4096.0 / 32768.0)

    def test_widest_range_is_the_fallback_not_an_error(self):
        self.assertAlmostEqual(capture_view.voltage_lsb_mv(1e9), 4096.0 / 32768.0)

    def test_identical_forward_and_reverse_is_fully_quantised(self):
        # The exact 2026-08-27 signature: fwd = rev = +60.000 mV.
        report = capture_view.quantisation_report(
            frame(
                [
                    record("FWD", (0, 1), (2, 3), 60.0),
                    record("REV", (1, 0), (2, 3), 60.0),
                ]
            )
        )
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.quantised_pairs, 1)
        self.assertAlmostEqual(report.min_counts, 0.0)
        self.assertTrue(report.limited)

    def test_a_healthy_differential_is_many_steps(self):
        report = capture_view.quantisation_report(reciprocal_frame(forward_mv=200.0))
        self.assertGreater(report.min_counts, capture_view.MIN_DIFFERENTIAL_COUNTS)
        self.assertEqual(report.quantised_pairs, 0)
        self.assertFalse(report.limited)

    def test_a_low_voltage_specimen_can_still_be_healthy(self):
        # 17 ohm at 364 uA is about 6 mV -- low resistance, plenty of steps.
        report = capture_view.quantisation_report(
            reciprocal_frame(forward_mv=6.2, current_ua=364.0)
        )
        self.assertFalse(report.limited)

    def test_a_few_weak_pairs_do_not_condemn_the_frame(self):
        # Distant pairs in an adjacent sweep are legitimately small.
        records = []
        for index in range(20):
            mv = 0.0001 if index == 0 else 50.0
            records.append(record("FWD", (0, 1), (index + 2, index + 3), mv))
            records.append(record("REV", (1, 0), (index + 2, index + 3), -mv))
        report = capture_view.quantisation_report(frame(records))
        self.assertEqual(report.quantised_pairs, 1)
        self.assertAlmostEqual(report.quantised_fraction, 0.05)
        self.assertFalse(report.limited)

    def test_flagged_records_are_not_scored(self):
        # Their voltage is not trustworthy enough to judge anything by.
        report = capture_view.quantisation_report(
            frame(
                [
                    record("FWD", (0, 1), (2, 3), 60.0, quality="I_LOW"),
                    record("REV", (1, 0), (2, 3), 60.0, quality="I_LOW"),
                ]
            )
        )
        self.assertEqual(report.pair_count, 0)
        self.assertFalse(report.limited)

    def test_a_lone_polarity_has_no_differential_to_score(self):
        report = capture_view.quantisation_report(
            frame([record("FWD", (0, 1), (2, 3), 60.0)])
        )
        self.assertEqual(report.pair_count, 0)

    def test_empty_frame_is_not_reported_as_limited(self):
        report = capture_view.quantisation_report(frame([]))
        self.assertEqual(report.pair_count, 0)
        self.assertFalse(report.limited)
        self.assertAlmostEqual(report.quantised_fraction, 0.0)


class ReciprocityTests(unittest.TestCase):
    def test_matched_pair_scores_near_zero(self):
        summary = capture_view.reciprocity_summary([reciprocal_frame(200.0, 200.0)])
        self.assertEqual(summary.pair_count, 1)
        self.assertLess(summary.median_error_percent, 1e-6)
        self.assertEqual(summary.sign_flip_count, 0)

    def test_mismatched_pair_reports_error_against_the_larger_magnitude(self):
        summary = capture_view.reciprocity_summary([reciprocal_frame(200.0, 100.0)])
        self.assertAlmostEqual(summary.median_error_percent, 50.0, places=6)

    def test_sign_flip_is_counted_separately_from_magnitude(self):
        # ADR-0008: a flipped sign means something different from a magnitude
        # error, so it must not be folded into the percentage.
        summary = capture_view.reciprocity_summary([reciprocal_frame(200.0, -200.0)])
        self.assertEqual(summary.sign_flip_count, 1)
        self.assertAlmostEqual(summary.median_error_percent, 0.0, places=6)
        self.assertAlmostEqual(summary.sign_flip_fraction, 1.0)

    def test_no_reciprocal_pair_gives_none_rather_than_a_fake_zero(self):
        only_one_way = frame(
            [
                record("FWD", (0, 1), (2, 3), 40.0),
                record("REV", (1, 0), (2, 3), -40.0),
            ]
        )
        self.assertIsNone(capture_view.reciprocity_summary([only_one_way]))

    def test_empty_frame_list_is_none(self):
        self.assertIsNone(capture_view.reciprocity_summary([]))


class AveragePairValueTests(unittest.TestCase):
    def test_values_are_averaged_across_frames(self):
        values = capture_view.average_pair_values(
            [reciprocal_frame(forward_mv=100.0), reciprocal_frame(forward_mv=300.0)]
        )
        self.assertAlmostEqual(abs(values[((0, 1), (2, 3))]), 1.0)

    def test_pair_present_in_only_one_frame_is_still_reported(self):
        # Dropping it would silently shrink the pair set whenever one frame had
        # a single weak record.
        partial = frame(
            [
                record("FWD", (0, 1), (2, 3), 40.0),
                record("REV", (1, 0), (2, 3), -40.0),
            ]
        )
        values = capture_view.average_pair_values([reciprocal_frame(), partial])
        self.assertIn(((0, 1), (2, 3)), values)
        self.assertIn(((2, 3), (0, 1)), values)


class NoiseSummaryTests(unittest.TestCase):
    def test_single_frame_has_no_noise_estimate(self):
        self.assertIsNone(capture_view.noise_summary([reciprocal_frame()]))

    def test_identical_frames_give_a_zero_floor(self):
        noise = capture_view.noise_summary([reciprocal_frame(), reciprocal_frame()])
        self.assertEqual(noise.frame_count, 2)
        self.assertAlmostEqual(noise.median_pair_std_kohm, 0.0)
        self.assertAlmostEqual(noise.median_pair_relative_percent, 0.0)

    def test_spread_between_frames_becomes_the_floor(self):
        noise = capture_view.noise_summary(
            [reciprocal_frame(forward_mv=100.0), reciprocal_frame(forward_mv=300.0)]
        )
        # Values 0.5 and 1.5 kohm: sample sd is 1/sqrt(2) ~= 0.7071 about a mean of 1.0
        self.assertAlmostEqual(noise.median_pair_std_kohm, 0.70710678, places=6)
        self.assertAlmostEqual(noise.median_pair_relative_percent, 70.710678, places=4)

    def test_relative_figure_is_reported_alongside_the_absolute_one(self):
        # D-03: an absolute drift threshold alone fails legitimate baselines,
        # because 1% of a large signal exceeds any fixed absolute bound.
        small = capture_view.noise_summary(
            [reciprocal_frame(forward_mv=10.0), reciprocal_frame(forward_mv=11.0)]
        )
        large = capture_view.noise_summary(
            [reciprocal_frame(forward_mv=1000.0), reciprocal_frame(forward_mv=1100.0)]
        )
        self.assertLess(small.median_pair_std_kohm, large.median_pair_std_kohm)
        self.assertAlmostEqual(
            small.median_pair_relative_percent,
            large.median_pair_relative_percent,
            places=6,
        )


class SessionSummaryTests(unittest.TestCase):
    def test_summary_combines_reciprocity_and_noise(self):
        summary = capture_view.session_summary([reciprocal_frame(), reciprocal_frame()])
        self.assertEqual(summary.frame_count, 2)
        self.assertIsNotNone(summary.reciprocity)
        self.assertIsNotNone(summary.noise)

    def test_empty_session_reports_nothing_rather_than_raising(self):
        summary = capture_view.session_summary([])
        self.assertEqual(summary.frame_count, 0)
        self.assertIsNone(summary.reciprocity)
        self.assertIsNone(summary.noise)


class FormattingTests(unittest.TestCase):
    def test_frame_line_reports_counts_current_and_resistance(self):
        line = capture_view.format_frame_summary(
            capture_view.frame_summary(reciprocal_frame(forward_mv=200.0))
        )
        self.assertIn("4/4 OK", line)
        self.assertIn("R med 1.0000 kohm", line)
        self.assertIn("LSB", line)
        # ADR-0026: no verdict is attached to the resistance itself.
        self.assertNotIn("WINDOW", line)

    def test_quantisation_limited_frame_is_shouted(self):
        line = capture_view.format_frame_summary(
            capture_view.frame_summary(
                frame(
                    [
                        record("FWD", (0, 1), (2, 3), 60.0),
                        record("REV", (1, 0), (2, 3), 60.0),
                    ]
                )
            )
        )
        self.assertIn("QUANTISATION LIMITED", line)

    def test_quality_flags_are_listed(self):
        line = capture_view.format_frame_summary(
            capture_view.frame_summary(
                frame([record("FWD", (0, 1), (2, 3), 1.0, quality="I_LOW")])
            )
        )
        self.assertIn("I_LOW", line)

    def test_non_interleaved_polarity_is_shouted(self):
        line = capture_view.format_frame_summary(
            capture_view.frame_summary(
                frame(
                    [
                        record("FWD", (0, 1), (2, 3), 40.0),
                        record("FWD", (0, 1), (3, 4), 40.0),
                    ]
                )
            )
        )
        self.assertIn("POLARITY NOT INTERLEAVED", line)

    def test_session_text_reports_both_headline_numbers(self):
        text = capture_view.format_session_summary(
            capture_view.session_summary([reciprocal_frame(), reciprocal_frame()])
        )
        self.assertIn("Reciprocity:", text)
        self.assertIn("Noise floor:", text)

    def test_session_text_says_why_a_number_is_missing(self):
        text = capture_view.format_session_summary(
            capture_view.session_summary([reciprocal_frame()])
        )
        self.assertIn("needs at least 2 frames", text)


if __name__ == "__main__":
    unittest.main()
