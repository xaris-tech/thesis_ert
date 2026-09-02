import unittest
from dataclasses import replace

import numpy as np

import phase3a_unified_reconstruct as unified
from tree_ert import selftest
from tree_ert.acquisition import DemoAcquisition
from tree_ert.controller import DebugController
from tree_ert.settings import UiSettings


STATUS_LINE = (
    "STATUS,2,MODE,ADJACENT,DAC,100,SETTLE,30,DISCHARGE,0,SAMPLES,4,"
    "RANGE,LOW,RS_OHMS,68.0,MAX_DAC_CODE,420,SHUNT_OHMS,97.90,DAC_ADDR,0x61,"
    "VGAIN_AUTO,1,VRANGE_MV,256.0,MIN_CURRENT_UA,10.0,MAX_CURRENT_UA,1250.0"
)


def demo_frame(pattern: str = "adjacent") -> unified.UnifiedFrame:
    acquisition = DemoAcquisition()
    acquisition.connect(replace(UiSettings.default(), pattern=pattern))
    return acquisition.capture_frame()


class TestParseStatus(unittest.TestCase):
    def test_parses_every_reported_field(self):
        status = unified.parse_status(["boot banner", STATUS_LINE])

        self.assertEqual(status.pattern, "adjacent")
        self.assertEqual(status.dac_code, 100)
        self.assertEqual(status.settle_ms, 30)
        self.assertEqual(status.sample_count, 4)
        self.assertEqual(status.current_range, "LOW")
        self.assertEqual(status.max_dac_code, 420)
        self.assertAlmostEqual(status.shunt_ohms, 97.90)
        self.assertEqual(status.dac_address, 0x61)
        self.assertTrue(status.voltage_autorange)

    def test_rejects_a_reply_without_a_v2_status_line(self):
        with self.assertRaisesRegex(ValueError, "No v2 STATUS line"):
            unified.parse_status(["STATUS,1,MODE,ADJACENT", "help text"])

    def test_rejects_a_truncated_status_line(self):
        with self.assertRaisesRegex(ValueError, "Malformed STATUS line"):
            unified.parse_status(["STATUS,2,MODE,ADJACENT,DAC,100"])


class TestHostChecks(unittest.TestCase):
    def test_protocol_check_counts_measurements(self):
        result = selftest.check_protocol("adjacent")

        self.assertIs(result.status, selftest.CheckStatus.PASS)
        self.assertIn("108 measurements", result.detail)

    def test_protocol_check_fails_on_an_unknown_pattern(self):
        result = selftest.check_protocol("diagonal")

        self.assertIs(result.status, selftest.CheckStatus.FAIL)

    def test_solver_and_sign_checks_pass_on_the_shipped_conventions(self):
        self.assertIs(selftest.check_solver("adjacent").status, selftest.CheckStatus.PASS)
        self.assertIs(
            selftest.check_reconstruction_forward_model("adjacent").status,
            selftest.CheckStatus.PASS,
        )


class TestFirmwareChecks(unittest.TestCase):
    def setUp(self):
        self.status = unified.parse_status([STATUS_LINE])

    def test_status_missing_is_a_failure_carrying_the_reason(self):
        result = selftest.check_status_reply(None, "no reply")

        self.assertIs(result.status, selftest.CheckStatus.FAIL)
        self.assertIn("no reply", result.detail)

    def test_i2c_check_requires_both_parts(self):
        self.assertIs(
            selftest.check_i2c_devices([0x48, 0x61]).status, selftest.CheckStatus.PASS
        )
        self.assertIs(
            selftest.check_i2c_devices([0x61]).status, selftest.CheckStatus.FAIL
        )
        self.assertIs(
            selftest.check_i2c_devices([0x48]).status, selftest.CheckStatus.FAIL
        )

    def test_i2c_check_fails_when_two_dac_addresses_answer(self):
        result = selftest.check_i2c_devices([0x48, 0x60, 0x61])

        self.assertIs(result.status, selftest.CheckStatus.FAIL)

    def test_dac_binding_fails_when_firmware_and_bus_disagree(self):
        result = selftest.check_dac_binding(self.status, [0x48, 0x60])

        self.assertIs(result.status, selftest.CheckStatus.FAIL)
        self.assertIn("b60", result.remedy)

    def test_shunt_mismatch_is_a_failure_and_a_match_is_not(self):
        self.assertIs(
            selftest.check_shunt(self.status, 97.9).status, selftest.CheckStatus.PASS
        )
        self.assertIs(
            selftest.check_shunt(self.status, 10.0).status, selftest.CheckStatus.FAIL
        )

    def test_shunt_warns_when_no_expected_value_is_configured(self):
        result = selftest.check_shunt(self.status, None)

        self.assertIs(result.status, selftest.CheckStatus.WARN)

    def test_dac_above_the_range_ceiling_fails(self):
        self.assertIs(
            selftest.check_current_range(self.status, 100).status,
            selftest.CheckStatus.PASS,
        )
        result = selftest.check_current_range(self.status, 600)
        self.assertIs(result.status, selftest.CheckStatus.FAIL)
        self.assertIn("clipped", result.detail)

    def test_dac_differing_from_the_ui_only_warns(self):
        result = selftest.check_current_range(self.status, 90)

        self.assertIs(result.status, selftest.CheckStatus.WARN)

    def test_autorange_disabled_fails(self):
        disabled = replace(self.status, voltage_autorange=False)

        self.assertIs(
            selftest.check_voltage_autorange(self.status).status,
            selftest.CheckStatus.PASS,
        )
        self.assertIs(
            selftest.check_voltage_autorange(disabled).status, selftest.CheckStatus.FAIL
        )


class TestFrameChecks(unittest.TestCase):
    def setUp(self):
        self.frame = demo_frame()

    def test_frame_shape_matches_the_requested_pattern(self):
        result = selftest.check_frame_shape(self.frame, "adjacent")

        self.assertIs(result.status, selftest.CheckStatus.PASS)

    def test_frame_shape_fails_on_the_wrong_pattern(self):
        result = selftest.check_frame_shape(self.frame, "opposite")

        self.assertIs(result.status, selftest.CheckStatus.FAIL)

    def test_frame_shape_fails_when_a_reverse_record_is_missing(self):
        records = [
            record for index, record in enumerate(self.frame.records) if index != 1
        ]
        broken = replace(self.frame, records=records)

        result = selftest.check_frame_shape(broken, "adjacent")

        self.assertIs(result.status, selftest.CheckStatus.FAIL)

    def test_interleaving_check_catches_per_polarity_passes(self):
        forward = [r for r in self.frame.records if r.polarity == "FWD"]
        reverse = [r for r in self.frame.records if r.polarity == "REV"]
        grouped = replace(self.frame, records=forward + reverse)

        self.assertIs(
            selftest.check_polarity_interleaving(self.frame).status,
            selftest.CheckStatus.PASS,
        )
        self.assertIs(
            selftest.check_polarity_interleaving(grouped).status,
            selftest.CheckStatus.FAIL,
        )

    def test_current_margin_grades_on_the_weakest_record(self):
        healthy = unified.probe_frame_health(self.frame)
        self.assertIs(
            selftest.check_current_margin(healthy).status, selftest.CheckStatus.PASS
        )

        weak_records = list(self.frame.records)
        weak_records[0] = replace(weak_records[0], current_ua=2.0)
        weak = unified.probe_frame_health(replace(self.frame, records=weak_records))
        self.assertIs(
            selftest.check_current_margin(weak).status, selftest.CheckStatus.FAIL
        )

    def test_quality_flags_scale_with_how_many_records_are_bad(self):
        records = list(self.frame.records)
        records[0] = replace(records[0], quality="I_LOW")
        one_bad = unified.probe_frame_health(replace(self.frame, records=records))
        self.assertIs(
            selftest.check_quality_flags(one_bad).status, selftest.CheckStatus.WARN
        )

        many = [replace(record, quality="I_LOW") for record in self.frame.records]
        all_bad = unified.probe_frame_health(replace(self.frame, records=many))
        self.assertIs(
            selftest.check_quality_flags(all_bad).status, selftest.CheckStatus.FAIL
        )

    def test_voltage_resolution_flags_a_frame_quantised_to_the_coarse_grid(self):
        quantised = replace(self.frame, records=[
            replace(record, voltage_mv=0.125 * round(record.voltage_mv / 12.5))
            for record in self.frame.records
        ])

        self.assertIs(
            selftest.check_voltage_resolution(self.frame).status,
            selftest.CheckStatus.PASS,
        )
        self.assertIs(
            selftest.check_voltage_resolution(quantised).status,
            selftest.CheckStatus.FAIL,
        )

    def test_electrode_check_flags_a_dead_mux_channel(self):
        records = [
            replace(record, current_ua=0.5) if 3 in record.i_pair else record
            for record in self.frame.records
        ]
        healths = unified.analyze_electrode_health(replace(self.frame, records=records))

        result = selftest.check_electrodes(healths)

        self.assertIs(result.status, selftest.CheckStatus.FAIL)
        self.assertIn("E4", result.detail)

    def test_offset_check_fails_when_forward_and_reverse_stop_inverting(self):
        stuck = replace(self.frame, records=[
            replace(record, voltage_mv=abs(record.voltage_mv) + 50.0)
            for record in self.frame.records
        ])

        self.assertIs(
            selftest.check_offset_domination(
                unified.analyze_offset_domination(self.frame)
            ).status,
            selftest.CheckStatus.PASS,
        )
        self.assertIs(
            selftest.check_offset_domination(
                unified.analyze_offset_domination(stuck)
            ).status,
            selftest.CheckStatus.FAIL,
        )

    def test_repeatability_needs_two_clean_frames(self):
        self.assertIs(
            selftest.check_repeatability([np.array([1.0, 2.0])]).status,
            selftest.CheckStatus.SKIP,
        )

        vector = np.array([1.0, 2.0, 3.0, 4.0])
        self.assertIs(
            selftest.check_repeatability([vector, vector * 1.001]).status,
            selftest.CheckStatus.PASS,
        )
        self.assertIs(
            selftest.check_repeatability([vector, vector[::-1]]).status,
            selftest.CheckStatus.FAIL,
        )


class TestSelfTestReport(unittest.TestCase):
    def _result(self, status, name="check"):
        return selftest.CheckResult("component", name, status, "detail")

    def test_worst_status_wins(self):
        passing = selftest.SelfTestReport([self._result(selftest.CheckStatus.PASS)])
        warning = selftest.SelfTestReport([
            self._result(selftest.CheckStatus.PASS),
            self._result(selftest.CheckStatus.WARN),
        ])
        failing = selftest.SelfTestReport([
            self._result(selftest.CheckStatus.WARN),
            self._result(selftest.CheckStatus.FAIL),
        ])

        self.assertIs(passing.status, selftest.CheckStatus.PASS)
        self.assertIs(warning.status, selftest.CheckStatus.WARN)
        self.assertIs(failing.status, selftest.CheckStatus.FAIL)

    def test_first_blocker_is_the_earliest_failure(self):
        report = selftest.SelfTestReport([
            self._result(selftest.CheckStatus.PASS, "a"),
            self._result(selftest.CheckStatus.FAIL, "b"),
            self._result(selftest.CheckStatus.FAIL, "c"),
        ])

        self.assertEqual(report.first_blocker().name, "b")

    def test_format_report_lists_remedies_only_for_problems(self):
        report = selftest.SelfTestReport([
            selftest.CheckResult("c", "good", selftest.CheckStatus.PASS, "d", "unused"),
            selftest.CheckResult("c", "bad", selftest.CheckStatus.FAIL, "d", "do this"),
        ])

        text = selftest.format_report(report)

        self.assertIn("do this", text)
        self.assertNotIn("unused", text)
        self.assertIn("Fix first", text)


class TestControllerSelfTest(unittest.TestCase):
    def test_disconnected_run_skips_hardware_but_still_checks_the_host(self):
        controller = DebugController(DemoAcquisition())

        report = controller.run_self_test(UiSettings.default())

        host = [r for r in report.results if r.component.startswith("Host")]
        hardware = [r for r in report.results if not r.component.startswith("Host")]
        self.assertTrue(all(r.status is selftest.CheckStatus.PASS for r in host))
        self.assertTrue(all(r.status is selftest.CheckStatus.SKIP for r in hardware))
        self.assertIs(report.status, selftest.CheckStatus.PASS)

    def test_connected_demo_run_exercises_every_check(self):
        controller = DebugController(DemoAcquisition())
        settings = replace(UiSettings.default(), expected_shunt_ohms=97.9)
        controller.connect(settings)

        report = controller.run_self_test(settings)

        self.assertEqual(report.counts()[selftest.CheckStatus.SKIP], 0)
        self.assertIs(report.status, selftest.CheckStatus.PASS)

    def test_a_shunt_mismatch_shows_up_as_the_first_blocker(self):
        controller = DebugController(DemoAcquisition())
        settings = replace(UiSettings.default(), expected_shunt_ohms=10.0)
        controller.connect(settings)

        report = controller.run_self_test(settings)

        blocker = report.first_blocker()
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker.component, "Hardware / shunt")

    def test_a_failing_serial_command_becomes_a_check_not_a_crash(self):
        class BrokenCommands(DemoAcquisition):
            def send_command(self, command: str) -> list[str]:
                raise OSError("port closed")

        controller = DebugController(BrokenCommands())
        settings = UiSettings.default()
        controller.connect(settings)

        report = controller.run_self_test(settings)

        status_check = next(r for r in report.results if r.name == "STATUS reply")
        self.assertIs(status_check.status, selftest.CheckStatus.FAIL)
        self.assertIn("port closed", status_check.detail)

    def test_reports_progress_through_the_progress_callback(self):
        messages = []
        controller = DebugController(DemoAcquisition(), progress=messages.append)
        settings = UiSettings.default()
        controller.connect(settings)

        controller.run_self_test(settings)

        self.assertTrue(any("Self test: host software" in m for m in messages))
        self.assertTrue(any(m.startswith("Self test ") and "pass=" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
