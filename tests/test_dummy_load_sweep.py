import unittest

import dummy_load_sweep as sweep


HOLD_LINE = "HOLD,1,I_SRC,E1,I_RET,E2,VP,E3,VN,E4,DAC,100,V,12.500,I,154.300,Q,OK"


class TestParseHoldLine(unittest.TestCase):
    def test_parses_a_hold_record(self):
        reading = sweep.parse_hold_line(HOLD_LINE)
        self.assertEqual(reading.dac_code, 100)
        self.assertAlmostEqual(reading.voltage_mv, 12.5)
        self.assertAlmostEqual(reading.current_ua, 154.3)
        self.assertEqual(reading.quality, "OK")

    def test_ignores_the_human_readable_lines_the_same_command_prints(self):
        self.assertIsNone(sweep.parse_hold_line("[DEBUG] Use your multimeter now!"))
        self.assertIsNone(sweep.parse_hold_line(""))

    def test_negative_current_survives_parsing(self):
        line = HOLD_LINE.replace("I,154.300", "I,-2.900")
        self.assertAlmostEqual(sweep.parse_hold_line(line).current_ua, -2.9)

    def test_rejects_an_unknown_hold_version(self):
        with self.assertRaises(ValueError):
            sweep.parse_hold_line(HOLD_LINE.replace("HOLD,1,", "HOLD,2,"))

    def test_rejects_a_record_missing_a_field(self):
        with self.assertRaises(ValueError):
            sweep.parse_hold_line("HOLD,1,DAC,100,V,12.500")


class TestFitSource(unittest.TestCase):
    def test_recovers_the_pre_repair_voltage_source(self):
        """The 2026-08-27 sweep found Rout ~= 430 ohm and Vth ~= 0.38 V.

        Feeding the model those parameters back must return them, or the fit
        cannot be trusted to say whether the ADR-0014 repair worked.
        """
        loads = [500.0, 1000.0, 2000.0, 4000.0]
        currents = [0.789 / (430.0 + load) * 1e6 for load in loads]
        fit = sweep.fit_source(loads, currents)
        self.assertAlmostEqual(fit.output_ohms, 430.0, places=3)
        self.assertAlmostEqual(fit.thevenin_mv, 789.0, places=3)

    def test_a_flat_source_reports_infinite_output_impedance(self):
        fit = sweep.fit_source([500.0, 1000.0, 2000.0], [155.0, 155.0, 155.0])
        self.assertEqual(fit.output_ohms, float("inf"))
        self.assertAlmostEqual(fit.flatness_percent, 0.0)

    def test_flatness_separates_a_current_source_from_a_voltage_source(self):
        loads = [500.0, 2000.0]
        voltage_source = [0.789 / (430.0 + load) * 1e6 for load in loads]
        current_source = [155.0, 154.5]
        self.assertGreater(sweep.fit_source(loads, voltage_source).flatness_percent, 50.0)
        self.assertLess(sweep.fit_source(loads, current_source).flatness_percent, 1.0)

    def test_one_load_cannot_fit_an_output_impedance(self):
        with self.assertRaises(ValueError):
            sweep.fit_source([1000.0, 1000.0], [154.0, 155.0])

    def test_mismatched_series_are_rejected(self):
        with self.assertRaises(ValueError):
            sweep.fit_source([500.0, 1000.0], [154.0])

    def test_a_zero_current_point_is_rejected_rather_than_dividing_by_zero(self):
        with self.assertRaises(ValueError):
            sweep.fit_source([500.0, 1000.0], [154.0, 0.0])


class TestFitByDacCode(unittest.TestCase):
    def _rows(self):
        rows = []
        for load in (500.0, 1000.0, 2000.0):
            for code, vth in ((100, 0.789), (200, 1.578)):
                rows.append({
                    "load_ohms": str(load),
                    "dac_code": str(code),
                    "current_ua": str(vth / (430.0 + load) * 1e6),
                    "quality": "OK",
                })
        return rows

    def test_fits_each_dac_code_separately(self):
        fits = sweep.fit_by_dac_code(self._rows())
        self.assertEqual([fit.dac_code for fit in fits], [100, 200])
        for fit in fits:
            self.assertAlmostEqual(fit.output_ohms, 430.0, places=2)
            self.assertEqual(fit.points, 3)

    def test_a_code_measured_at_one_load_only_is_skipped_not_fitted(self):
        rows = self._rows()
        rows.append({
            "load_ohms": "1000.0",
            "dac_code": "400",
            "current_ua": "300.0",
            "quality": "OK",
        })
        self.assertEqual([fit.dac_code for fit in sweep.fit_by_dac_code(rows)], [100, 200])


class TestFormatFitReport(unittest.TestCase):
    def test_says_so_plainly_when_there_is_nothing_to_fit(self):
        self.assertIn("nothing to fit", sweep.format_fit_report([]))

    def test_report_lists_one_row_per_dac_code(self):
        text = sweep.format_fit_report(sweep.fit_by_dac_code(TestFitByDacCode()._rows()))
        self.assertIn("100", text)
        self.assertIn("200", text)
        self.assertIn("flatness", text)


if __name__ == "__main__":
    unittest.main()
