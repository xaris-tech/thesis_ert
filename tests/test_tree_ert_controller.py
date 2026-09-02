from dataclasses import replace
import unittest

import numpy as np

from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.controller import (
    CaptureStopped,
    ControllerState,
    DebugController,
    drift_tuning_candidates,
)
from tree_ert.settings import UiSettings


class TestCaptureReciprocity(unittest.TestCase):
    def test_scores_pairs_without_needing_a_baseline(self):
        # Reciprocity is an internal consistency check on the instrument, not a
        # comparison against a reference state, so it must run straight after
        # configure - before any baseline exists.
        controller = DebugController(DemoAcquisition())
        settings = replace(
            UiSettings.default(), pattern="adjacent", frames=2, warmup_frames=0
        )

        controller.connect(settings)
        controller.configure(settings)
        scores = controller.capture_reciprocity(settings)

        self.assertIsNone(controller.baseline_result)
        self.assertTrue(scores)
        for score in scores.values():
            self.assertGreaterEqual(score.error_percent, 0.0)
            self.assertLessEqual(score.error_percent, 100.0)
            self.assertIsInstance(score.sign_flipped, bool)

    def test_each_reciprocal_pair_is_scored_once(self):
        controller = DebugController(DemoAcquisition())
        settings = replace(
            UiSettings.default(), pattern="adjacent", frames=1, warmup_frames=0
        )

        controller.connect(settings)
        controller.configure(settings)
        scores = controller.capture_reciprocity(settings)

        for (i_pair, v_pair) in scores:
            self.assertNotIn((v_pair, i_pair), scores)


class StopDuringCaptureAcquisition(DemoAcquisition):
    def __init__(self, stop_on_capture: int) -> None:
        super().__init__()
        self.stop_on_capture = stop_on_capture
        self.capture_count = 0
        self.stop_count = 0
        self.controller: DebugController | None = None

    def capture_frame(self):
        self.capture_count += 1
        frame = super().capture_frame()
        if self.capture_count == self.stop_on_capture:
            if self.controller is None:
                raise AssertionError("controller must be assigned before capture")
            self.controller.stop()
        return frame

    def stop(self) -> None:
        self.stop_count += 1
        super().stop()


class BadRecordAcquisition(DemoAcquisition):
    """Demo frames with one measurement flagged bad by the firmware.

    A different record is spoiled each frame, so every pair is measured by at
    least one frame - the case lenient capture is meant to rescue.
    """

    def capture_frame(self):
        frame = super().capture_frame()
        spoiled = list(frame.records)
        index = (self.frame_id * 2) % len(spoiled)
        spoiled[index] = replace(spoiled[index], quality="I_LOW", current_ua=0.2)
        return replace(frame, records=spoiled)


class FailingStopSerial:
    def __init__(self) -> None:
        self.closed = False

    def write(self, data: bytes) -> None:
        if data == b"x\n":
            raise OSError("stop command failed")

    def close(self) -> None:
        self.closed = True


class TestDebugController(unittest.TestCase):
    def test_drift_tuning_candidates_focus_near_stable_profile(self):
        settings = replace(UiSettings.default(), settle_ms=30, samples=4, warmup_frames=10, baseline_frames=10, frames=20)

        candidates = drift_tuning_candidates(settings)
        profiles = [
            (
                candidate.settle_ms,
                candidate.samples,
                candidate.warmup_frames,
                candidate.baseline_frames,
                candidate.frames,
            )
            for candidate in candidates
        ]

        self.assertIn((100, 16, 20, 10, 10), profiles)
        self.assertIn((100, 16, 30, 15, 10), profiles)
        self.assertIn((150, 16, 30, 20, 10), profiles)
        self.assertIn((200, 32, 30, 20, 10), profiles)

    def test_tune_drift_runs_candidate_settings_and_picks_best(self):
        messages = []
        controller = DebugController(DemoAcquisition(), progress=messages.append)
        settings = replace(UiSettings.default(), warmup_frames=0, baseline_frames=2, frames=2)

        controller.connect(settings)
        result = controller.tune_drift(settings)

        self.assertGreaterEqual(len(result.attempts), 2)
        self.assertIsNotNone(result.best)
        self.assertIn("Tune attempt", "\n".join(messages))
        self.assertIn("Tune best", "\n".join(messages))

    def test_controller_emits_live_progress_messages(self):
        messages = []
        controller = DebugController(DemoAcquisition(), progress=messages.append)
        settings = replace(UiSettings.default(), warmup_frames=1, baseline_frames=2, frames=2)

        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)
        controller.capture_control(settings)
        controller.capture_target(settings)

        self.assertIn("Connecting to demo acquisition", messages)
        self.assertIn("Configuring pattern=adjacent dac=100 settle=30ms samples=4", messages)
        # Progress lines carry a trailing time estimate, so match on the prefix.
        for prefix in (
            "Warmup frame 1/1",
            "Baseline frame 2/2",
            "Control drift frame 2/2",
            "Target frame 2/2",
        ):
            self.assertTrue(
                any(message.startswith(prefix) for message in messages),
                f"no progress message starting with {prefix!r}",
            )
        self.assertTrue(
            any(message.strip().startswith("running stability:") for message in messages),
            "baseline should report running stability before it finishes",
        )

    def test_controller_streams_target_reconstructions_as_they_are_created(self):
        previews = []
        controller = DebugController(DemoAcquisition(), target_preview=previews.append)
        settings = replace(UiSettings.default(), warmup_frames=0, baseline_frames=2, frames=3)

        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)
        target = controller.capture_target(settings)

        self.assertEqual([len(preview) for preview in previews], [1, 2, 3])
        self.assertEqual(len(target.reconstructions), 3)

    def test_demo_controller_captures_baseline_then_target(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        baseline = controller.capture_baseline(settings)
        self.assertEqual(controller.state, ControllerState.BASELINE_READY)
        self.assertGreater(len(baseline), 0)
        target = controller.capture_target(settings)
        self.assertEqual(controller.state, ControllerState.TARGET_READY)
        self.assertEqual(len(target.reconstructions), settings.frames)

    def test_probe_frame_reports_diagnostics_without_baseline(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)

        diagnostics = controller.probe_frame(settings)

        self.assertGreater(diagnostics.probe.total_records, 0)
        self.assertEqual(diagnostics.probe.quality_counts, {"OK": diagnostics.probe.total_records})
        self.assertEqual(len(diagnostics.electrodes), 12)
        self.assertIsNone(controller.baseline_result)

    def test_probe_frame_requires_configure(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)

        with self.assertRaisesRegex(RuntimeError, "configure"):
            controller.probe_frame(settings)

    def test_lenient_capture_survives_a_bad_measurement(self):
        settings = replace(
            UiSettings.default(), warmup_frames=0, baseline_frames=3, frames=1
        )
        strict_controller = DebugController(BadRecordAcquisition())
        strict_controller.connect(settings)
        strict_controller.configure(settings)

        with self.assertRaises(ValueError):
            strict_controller.capture_baseline(settings)

        lenient = replace(settings, lenient_quality=True)
        lenient_controller = DebugController(BadRecordAcquisition())
        lenient_controller.connect(lenient)
        lenient_controller.configure(lenient)

        result = lenient_controller.capture_baseline(lenient)

        self.assertEqual(lenient_controller.state, ControllerState.BASELINE_READY)
        self.assertFalse(bool(np.isnan(result.baseline).any()))

    def test_emergency_stop_idles_hardware_and_drops_connection(self):
        acquisition = DemoAcquisition()
        controller = DebugController(acquisition)
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)

        errors = controller.emergency_stop()

        self.assertEqual(errors, [])
        self.assertTrue(acquisition.stopped)
        self.assertEqual(controller.state, ControllerState.DISCONNECTED)
        self.assertIsNone(controller.protocol)
        self.assertIsNone(controller.baseline_result)

    def test_emergency_stop_continues_after_a_failing_step(self):
        class BrokenStop(DemoAcquisition):
            def stop(self):
                raise OSError("port vanished")

        acquisition = BrokenStop()
        controller = DebugController(acquisition)
        settings = UiSettings.default()
        controller.connect(settings)

        errors = controller.emergency_stop()

        # close() also routes through stop(), so both steps report the failure;
        # the point is that neither one aborts the sequence.
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("port vanished" in error for error in errors))
        self.assertEqual(controller.state, ControllerState.DISCONNECTED)

    def test_stopped_capture_keeps_partial_frames(self):
        acquisition = StopDuringCaptureAcquisition(stop_on_capture=3)
        controller = DebugController(acquisition)
        acquisition.controller = controller
        settings = replace(
            UiSettings.default(), warmup_frames=0, baseline_frames=6, frames=2
        )
        controller.connect(settings)
        controller.configure(settings)

        with self.assertRaises(CaptureStopped) as caught:
            controller.capture_baseline(settings)

        self.assertEqual(len(caught.exception.partial), 2)

    def test_target_capture_discards_warmup_frames_after_insertion(self):
        settings = replace(
            UiSettings.default(),
            warmup_frames=0,
            baseline_frames=2,
            target_warmup_frames=3,
            frames=2,
        )
        acquisition = DemoAcquisition()
        messages = []
        controller = DebugController(acquisition, progress=messages.append)
        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)
        before = acquisition.frame_id

        result = controller.capture_target(settings)

        # 3 discarded plus 2 kept, and only the kept ones reconstruct.
        self.assertEqual(acquisition.frame_id - before, 5)
        self.assertEqual(len(result.reconstructions), 2)
        self.assertTrue(
            any(m.startswith("Target warmup frame 3/3") for m in messages),
            "target warmup should be reported",
        )

    def test_substitution_can_be_disabled_for_target_capture(self):
        settings = replace(
            UiSettings.default(), warmup_frames=0, baseline_frames=2, frames=1
        )
        messages = []
        controller = DebugController(DemoAcquisition(), progress=messages.append)
        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)

        controller.capture_target(replace(settings, filter_pairs=False))

        self.assertTrue(
            any("substitution=off" in message for message in messages),
            "target capture should report whether substitution was applied",
        )

    def test_send_command_passes_through_to_acquisition(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)

        self.assertEqual(controller.send_command("ma"), ["[demo] ma"])
        with self.assertRaisesRegex(ValueError, "command"):
            controller.send_command("   ")

    def test_target_requires_baseline(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        with self.assertRaisesRegex(RuntimeError, "baseline"):
            controller.capture_target(settings)

    def test_stop_calls_acquisition_stop(self):
        acquisition = DemoAcquisition()
        controller = DebugController(acquisition)
        controller.stop()
        self.assertTrue(acquisition.stopped)
        self.assertEqual(controller.state, ControllerState.STOPPED)

    def test_stop_cancels_active_baseline_before_next_frame_request(self):
        acquisition = StopDuringCaptureAcquisition(stop_on_capture=2)
        controller = DebugController(acquisition)
        acquisition.controller = controller
        settings = replace(UiSettings.default(), warmup_frames=0, baseline_frames=5)
        controller.connect(settings)
        controller.configure(settings)

        with self.assertRaisesRegex(RuntimeError, "stopped"):
            controller.capture_baseline(settings)

        self.assertEqual(acquisition.capture_count, 2)
        self.assertEqual(acquisition.stop_count, 1)
        self.assertIsNone(controller.baseline_result)
        self.assertEqual(controller.state, ControllerState.STOPPED)

    def test_stop_cancels_active_control_before_next_frame_request(self):
        acquisition = StopDuringCaptureAcquisition(stop_on_capture=22)
        controller = DebugController(acquisition)
        acquisition.controller = controller
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)

        with self.assertRaisesRegex(RuntimeError, "stopped"):
            controller.capture_control(settings)

        self.assertEqual(acquisition.capture_count, 22)
        self.assertEqual(acquisition.stop_count, 1)
        self.assertEqual(controller.state, ControllerState.STOPPED)

    def test_stop_cancels_active_target_before_next_frame_request(self):
        acquisition = StopDuringCaptureAcquisition(stop_on_capture=22)
        controller = DebugController(acquisition)
        acquisition.controller = controller
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)

        with self.assertRaisesRegex(RuntimeError, "stopped"):
            controller.capture_target(settings)

        self.assertEqual(acquisition.capture_count, 22)
        self.assertEqual(acquisition.stop_count, 1)
        self.assertEqual(controller.state, ControllerState.STOPPED)

    def test_configure_invalidates_stale_baseline(self):
        controller = DebugController(DemoAcquisition())
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)

        controller.configure(replace(settings, dac=settings.dac + 1))

        self.assertIsNone(controller.baseline_result)
        self.assertEqual(controller.state, ControllerState.CONFIGURED)
        with self.assertRaisesRegex(RuntimeError, "baseline"):
            controller.capture_target(settings)

    def test_connect_and_close_clear_baseline(self):
        acquisition = DemoAcquisition()
        controller = DebugController(acquisition)
        settings = UiSettings.default()
        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)

        controller.connect(settings)
        self.assertIsNone(controller.baseline_result)
        with self.assertRaisesRegex(RuntimeError, "configure"):
            controller.capture_baseline(settings)

        controller.configure(settings)
        controller.capture_baseline(settings)
        controller.close()
        self.assertIsNone(controller.baseline_result)
        self.assertEqual(controller.state, ControllerState.DISCONNECTED)

    def test_demo_frame_reflects_current_settings(self):
        acquisition = DemoAcquisition()
        settings = replace(UiSettings.default(), dac=321, settle_ms=45, samples=7)
        acquisition.connect(settings)

        frame = acquisition.capture_frame()

        self.assertEqual(frame.dac_code, 321)
        self.assertEqual(frame.settle_ms, 45)
        self.assertEqual(frame.sample_count, 7)

    def test_serial_close_releases_handle_when_stop_command_fails(self):
        acquisition = SerialAcquisition()
        fake_serial = FailingStopSerial()
        acquisition._serial = fake_serial

        with self.assertRaisesRegex(OSError, "stop command failed"):
            acquisition.close()

        self.assertTrue(fake_serial.closed)
        self.assertIsNone(acquisition._serial)


class FakeDacSerial:
    """Serial stub that answers `i` with a scan and records what was written."""

    def __init__(self, scan_lines, address_reply=None):
        self.scan_lines = list(scan_lines)
        self.address_reply = list(address_reply or ["[INFO] MCP4725 attached at 0x61"])
        self.written = []
        self._pending = []

    def write(self, payload):
        text = payload.decode().strip()
        self.written.append(text)
        if text == "i":
            self._pending = list(self.scan_lines)
        elif text.startswith("b"):
            self._pending = list(self.address_reply)

    def readline(self):
        if not self._pending:
            return b""
        return (self._pending.pop(0) + "\n").encode()

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


SCAN_0X61 = ["I2C_SCAN,BEGIN", "I2C_DEVICE,0x48", "I2C_DEVICE,0x61", "I2C_SCAN,END,FOUND,2"]
SCAN_0X60 = ["I2C_SCAN,BEGIN", "I2C_DEVICE,0x48", "I2C_DEVICE,0x60", "I2C_SCAN,END,FOUND,2"]
SCAN_BOTH = [
    "I2C_SCAN,BEGIN", "I2C_DEVICE,0x48",
    "I2C_DEVICE,0x60", "I2C_DEVICE,0x61", "I2C_SCAN,END,FOUND,3",
]


class TestSerialDacAddressSelection(unittest.TestCase):
    def _acquisition(self, serial_stub):
        acquisition = SerialAcquisition()
        acquisition._serial = serial_stub
        return acquisition

    def test_binds_to_the_scanned_address(self):
        for scan, expected, command in (
            (SCAN_0X61, 0x61, "b61"),
            (SCAN_0X60, 0x60, "b60"),
        ):
            with self.subTest(expected=expected):
                stub = FakeDacSerial(scan)
                result = self._acquisition(stub).select_dac_address()

                self.assertEqual(result.address, expected)
                self.assertTrue(result.resolved)
                self.assertIn(command, stub.written)

    def test_sends_no_address_command_when_the_bus_is_ambiguous(self):
        stub = FakeDacSerial(SCAN_BOTH)

        result = self._acquisition(stub).select_dac_address()

        self.assertIsNone(result.address)
        self.assertFalse(any(text.startswith("b") for text in stub.written))
        self.assertIn("0x60", result.detail)
        self.assertIn("0x61", result.detail)

    def test_reports_an_older_flash_without_the_b_command(self):
        stub = FakeDacSerial(SCAN_0X61, ["[ERROR] unknown command; send h"])

        result = self._acquisition(stub).select_dac_address()

        self.assertIsNone(result.address)
        self.assertIn("reflash", result.detail)

    def test_reports_a_firmware_refusal(self):
        stub = FakeDacSerial(SCAN_0X61, ["[ERROR] no MCP4725 acknowledged at 0x61"])

        result = self._acquisition(stub).select_dac_address()

        self.assertIsNone(result.address)
        self.assertIn("refused", result.detail)

    def test_silent_board_leaves_the_firmware_choice_alone(self):
        stub = FakeDacSerial([])

        result = self._acquisition(stub).select_dac_address()

        self.assertIsNone(result.address)
        self.assertFalse(any(text.startswith("b") for text in stub.written))


class TestControllerDacAddress(unittest.TestCase):
    def test_connect_reports_the_selected_address(self):
        messages = []
        controller = DebugController(DemoAcquisition(), progress=messages.append)

        controller.connect(UiSettings.default())

        self.assertEqual(controller.state, ControllerState.CONNECTED)
        self.assertTrue(any("DAC address" in message for message in messages))

    def test_connect_survives_a_failing_address_check(self):
        class BrokenSelect(DemoAcquisition):
            def select_dac_address(self):
                raise RuntimeError("scan exploded")

        messages = []
        controller = DebugController(BrokenSelect(), progress=messages.append)

        controller.connect(UiSettings.default())

        # Advisory only: the firmware already chose an address at boot, so a
        # failed correction must not cost the session.
        self.assertEqual(controller.state, ControllerState.CONNECTED)
        self.assertTrue(any("scan exploded" in message for message in messages))


class TestConfigureDeclaresCurrentRange(unittest.TestCase):
    """ADR-0011: without the range command the firmware guards against LOW's
    100 uA ceiling and flags every legitimate reading on a 10 ohm Rs as
    I_HIGH."""

    def test_range_is_sent_before_the_dac_code(self):
        import tree_ert.acquisition as acquisition
        from dataclasses import replace as _replace
        from tree_ert.settings import UiSettings

        written = []

        class FakeSerial:
            def write(self, payload):
                written.append(payload)
            def reset_input_buffer(self):
                pass

        serial_acq = acquisition.SerialAcquisition.__new__(acquisition.SerialAcquisition)
        serial_acq._serial = FakeSerial()
        serial_acq.configure(_replace(UiSettings.default(), current_range="high", dac=100))

        newline = chr(10)
        self.assertIn(("eh" + newline).encode(), written)
        self.assertLess(
            written.index(("eh" + newline).encode()),
            written.index(("p100" + newline).encode()),
        )


if __name__ == "__main__":
    unittest.main()
