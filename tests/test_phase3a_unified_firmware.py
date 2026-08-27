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
        self.assertIn("shuntMv / shuntOhms", self.source)

    def test_shunt_value_is_runtime_settable(self):
        self.assertIn("constexpr float DEFAULT_SHUNT_OHMS", self.source)
        self.assertIn("float shuntOhms = DEFAULT_SHUNT_OHMS;", self.source)
        self.assertIn("case 'j':", self.source)

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
        self.assertIn('emitMeasurement("FWD"', self.source)
        self.assertIn('emitMeasurement("REV"', self.source)
        self.assertIn("iRet, iSrc", self.source)

    def test_forward_and_reverse_are_interleaved_per_sense_pair(self):
        function = re.search(
            r"void emitInjectionPair\([^)]*\)\s*\{(?P<body>.*?)\n\}",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        forward = body.index('emitMeasurement("FWD"')
        reverse = body.index('emitMeasurement("REV"')
        # Both polarities must sit inside the same sense-pair loop so net DC per
        # electrode stays near zero; running one polarity to completion first is
        # what let polarisation accumulate.
        self.assertLess(forward, reverse)
        self.assertIn("for (uint8_t vp = 0; vp < ELECTRODE_COUNT; ++vp)", body)

    def test_current_range_enforces_its_own_dac_ceiling(self):
        self.assertIn("enum class CurrentRange", self.source)
        self.assertIn('{"LOW", 68.0f, 420}', self.source)
        self.assertIn('{"MEDIUM", 22.0f, 680}', self.source)
        self.assertIn('{"HIGH", 10.0f, 620}', self.source)
        self.assertIn("min<uint16_t>(code, maxDacCode())", self.source)
        self.assertIn('line == "el"', self.source)
        self.assertIn('line == "em"', self.source)
        self.assertIn('line == "eh"', self.source)

    def test_electrode_voltage_pga_autoranges(self):
        self.assertIn("struct VoltageRangeSpec", self.source)
        self.assertIn("{GAIN_SIXTEEN, 256.0f}", self.source)
        self.assertIn("{GAIN_EIGHT, 512.0f}", self.source)
        self.assertIn("{GAIN_ONE, 4096.0f}", self.source)
        self.assertIn("size_t selectVoltageRange(float magnitudeMv)", self.source)
        self.assertIn("bool voltageAutorange = true;", self.source)
        self.assertIn("case 'a':", self.source)
        # The fixed GAIN_ONE read is what wasted ~94 percent of the ADC range.
        self.assertNotIn("ads.setGain(GAIN_ONE);", self.source)

    def test_autorange_falls_back_when_the_tight_range_clips(self):
        function = re.search(
            r"float readVoltageMv\(\)\s*\{(?P<body>.*?)\n\}",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(function)
        body = function.group("body")
        self.assertIn("VOLTAGE_RANGE_FALLBACK", body)
        self.assertIn("0.99f", body)

    def test_discharge_interval_is_configurable(self):
        self.assertIn("uint16_t dischargeMs = DEFAULT_DISCHARGE_MS;", self.source)
        self.assertIn("if (dischargeMs > 0) delay(dischargeMs);", self.source)
        self.assertIn("case 'c':", self.source)

    def test_fatal_i2c_messages_report_the_configured_address(self):
        self.assertIn("Serial.println(MCP4725_ADDRESS, HEX);", self.source)
        self.assertIn("Serial.println(ADS1115_ADDRESS, HEX);", self.source)

    def test_supports_adjacent_opposite_skip_one_and_skip_two_runtime_modes(self):
        self.assertIn("enum class DrivePattern", self.source)
        self.assertIn("DrivePattern::ADJACENT", self.source)
        self.assertIn("DrivePattern::OPPOSITE", self.source)
        self.assertIn("DrivePattern::SKIP_1", self.source)
        self.assertIn("DrivePattern::SKIP_2", self.source)
        self.assertIn('line == "ma"', self.source)
        self.assertIn('line == "mo"', self.source)
        self.assertIn('line == "ms"', self.source)
        self.assertIn('line == "mk"', self.source)

    def test_status_and_i2c_diagnostic_include_hardware_constants(self):
        self.assertIn('Serial.print(",SHUNT_OHMS,")', self.source)
        self.assertIn('Serial.print(",RANGE,")', self.source)
        self.assertIn('Serial.print(",RS_OHMS,")', self.source)
        self.assertIn('Serial.print(",MAX_DAC_CODE,")', self.source)
        self.assertIn('Serial.print(",DISCHARGE,")', self.source)
        self.assertIn('Serial.print(",VGAIN_AUTO,")', self.source)
        self.assertIn('Serial.print(",VRANGE_MV,")', self.source)
        self.assertIn("void printI2CScan()", self.source)
        self.assertIn('Serial.println("I2C_SCAN,BEGIN")', self.source)
        self.assertIn("case 'i': printI2CScan(); break;", self.source)

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
