"""Compile check for the active sketch (ADR-0016).

Skips rather than fails when no Arduino toolchain is installed, so the suite
still passes on a machine that has never flashed this project.
"""

import os
import unittest
from pathlib import Path

import firmware_compile as fc


class TestParseSizes(unittest.TestCase):
    SUMMARY = (
        "Sketch uses 325593 bytes (24%) of program storage space. "
        "Maximum is 1310720 bytes.\n"
        "Global variables use 14920 bytes (4%) of dynamic memory, leaving "
        "312760 bytes for local variables. Maximum is 327680 bytes.\n"
    )

    def test_reads_flash_and_ram_from_the_summary(self):
        self.assertEqual(fc.parse_sizes(self.SUMMARY), (325593, 14920))

    def test_unrecognised_output_yields_no_sizes_rather_than_raising(self):
        # A changed size-line format must not fail a compile that succeeded.
        self.assertEqual(fc.parse_sizes("built fine\n"), (None, None))


class TestFindArduinoCli(unittest.TestCase):
    def test_env_override_pointing_nowhere_reports_missing(self):
        original = os.environ.get("ARDUINO_CLI")
        os.environ["ARDUINO_CLI"] = str(Path("no") / "such" / "arduino-cli")
        try:
            self.assertIsNone(fc.find_arduino_cli())
        finally:
            if original is None:
                del os.environ["ARDUINO_CLI"]
            else:
                os.environ["ARDUINO_CLI"] = original


class TestActiveSketchCompiles(unittest.TestCase):
    def setUp(self):
        self.cli = fc.find_arduino_cli()
        if self.cli is None:
            self.skipTest("arduino-cli not installed; set ARDUINO_CLI to enable")

    def test_the_active_sketch_builds(self):
        """The check ADR-0005's text assertions cannot make.

        Text matching cannot tell a sketch that builds from one that does not,
        and the only other way to find out is to flash a board attached to a
        tree.
        """
        result = fc.compile_sketch(cli=self.cli)
        self.assertTrue(
            result.ok,
            "active firmware sketch failed to compile:\n" + result.output[-4000:],
        )

    def test_the_build_fits_the_esp32s3(self):
        result = fc.compile_sketch(cli=self.cli)
        self.assertTrue(result.ok, result.output[-2000:])
        self.assertIsNotNone(result.flash_bytes)
        self.assertLess(result.flash_bytes, 1310720)
        self.assertLess(result.ram_bytes, 327680)


if __name__ == "__main__":
    unittest.main()
