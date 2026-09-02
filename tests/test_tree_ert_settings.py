import unittest
from dataclasses import replace

from tree_ert.settings import UiSettings, parse_int_field, parse_float_field


class TestUiSettings(unittest.TestCase):
    def test_defaults_are_safe_for_demo(self):
        settings = UiSettings.default()
        self.assertEqual(settings.port, "COM3")
        self.assertEqual(settings.baud, 115200)
        self.assertEqual(settings.pattern, "adjacent")
        self.assertEqual(settings.dac, 100)
        self.assertEqual(settings.settle_ms, 30)
        self.assertEqual(settings.samples, 4)
        self.assertEqual(settings.baseline_frames, 10)
        self.assertEqual(settings.frames, 20)

    def test_rejects_invalid_pattern_and_ranges(self):
        with self.assertRaisesRegex(ValueError, "pattern"):
            UiSettings(pattern="bad").validate()
        with self.assertRaisesRegex(ValueError, "dac"):
            UiSettings(dac=700).validate()
        with self.assertRaisesRegex(ValueError, "settle_ms"):
            UiSettings(settle_ms=0).validate()

    def test_parses_fields_with_clear_errors(self):
        self.assertEqual(parse_int_field("dac", "120", 0, 620), 120)
        self.assertEqual(parse_float_field("diameter_cm", "16.5", minimum=0.1), 16.5)
        with self.assertRaisesRegex(ValueError, "dac"):
            parse_int_field("dac", "abc", 0, 620)
        with self.assertRaisesRegex(ValueError, "diameter_cm"):
            parse_float_field("diameter_cm", "0", minimum=0.1)


if __name__ == "__main__":
    unittest.main()


class TestCurrentRange(unittest.TestCase):
    """ADR-0011: Rs is a physical jumper the firmware cannot read back, so the
    UI has to declare it or the firmware keeps its RANGE_LOW default."""

    def test_defaults_to_high_because_only_10_ohm_rs_is_fitted(self):
        self.assertEqual(UiSettings.default().current_range, "high")

    def test_range_command_is_the_firmware_selector(self):
        for name, command in (("low", b"el\n"), ("medium", b"em\n"), ("high", b"eh\n")):
            settings = replace(UiSettings.default(), current_range=name, dac=100)
            self.assertEqual(settings.range_command(), command)

    def test_dac_ceiling_follows_the_selected_range(self):
        for name, ceiling in (("low", 420), ("medium", 680), ("high", 620)):
            settings = replace(UiSettings.default(), current_range=name, dac=1)
            self.assertEqual(settings.max_dac_code(), ceiling)
            replace(settings, dac=ceiling).validate()
            with self.assertRaises(ValueError):
                replace(settings, dac=ceiling + 1).validate()

    def test_rejects_an_unknown_range(self):
        with self.assertRaises(ValueError):
            replace(UiSettings.default(), current_range="turbo").validate()
