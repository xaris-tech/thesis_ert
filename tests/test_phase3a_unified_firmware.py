import re
import unittest
from pathlib import Path


FIRMWARE = Path(
    "firmware/esp32s3-phase3a-unified-arduino/"
    "esp32s3_phase3a_unified/esp32s3_phase3a_unified.ino"
)


class TestUnifiedFirmwareSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FIRMWARE.read_text(encoding="utf-8")

    def test_pin_map_matches_documented_four_mux_wiring(self):
        self.assertIn("MUX_I_SRC = {4, 5, 6, 7, 37}", self.source)
        self.assertIn("MUX_I_RET = {10, 11, 12, 13, 38}", self.source)
        self.assertIn("MUX_VP = {15, 16, 17, 18, 39}", self.source)
        self.assertIn("MUX_VN = {36, 35, 41, 42, 40}", self.source)

    def test_reads_voltage_and_current_from_separate_ads_pairs(self):
        self.assertIn("readADC_Differential_0_1", self.source)
        self.assertIn("readADC_Differential_2_3", self.source)
        self.assertIn("SHUNT_OHMS = 100.0f", self.source)

    def test_switching_goes_idle_before_mux_addresses_change(self):
        function = re.search(
            r"void configureDriveAndSense\([^)]*\)\s*\{(?P<body>.*?)\n\}",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        self.assertLess(body.index("setDacRaw(0)"), body.index("disableAllMuxes()"))
        self.assertLess(body.index("disableAllMuxes()"), body.index("writeMuxAddress"))

    def test_frame_contains_forward_and_reverse_measurements(self):
        self.assertIn('emitPolarity("FWD"', self.source)
        self.assertIn('emitPolarity("REV"', self.source)
        self.assertIn("iRet, iSrc", self.source)

    def test_supports_adjacent_and_opposite_runtime_modes(self):
        self.assertIn("enum class DrivePattern", self.source)
        self.assertIn("DrivePattern::ADJACENT", self.source)
        self.assertIn("DrivePattern::OPPOSITE", self.source)
        self.assertIn('line == "ma"', self.source)
        self.assertIn('line == "mo"', self.source)

    def test_frame_records_include_voltage_current_and_quality(self):
        for field in ('",V,"', '",I,"', '",Q,"'):
            self.assertIn(field, self.source)

    def test_voltage_range_check_allows_negative_differential_values(self):
        self.assertIn("fabsf(voltageMv) > MAX_MUX_VOLTAGE_MV", self.source)

    def test_current_quality_uses_magnitude_and_reports_reversed_polarity(self):
        self.assertIn("fabsf(currentUa) < MIN_CURRENT_UA", self.source)
        self.assertIn("fabsf(currentUa) > MAX_CURRENT_UA", self.source)
        self.assertIn('currentUa < 0.0f) return "I_REVERSED"', self.source)


if __name__ == "__main__":
    unittest.main()
