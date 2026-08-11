import csv
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.controller import DebugController, ControllerState, drift_tuning_candidates
from tree_ert.settings import UiSettings


def default_settings() -> UiSettings:
    """Base settings for controller tests.

    Logging is off: these tests exercise capture and state behaviour, not run
    labelling, and must not write CSV files into phase3a_logs as a side effect.
    """
    return replace(UiSettings.default(), log_enabled=False)


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
        settings = replace(default_settings(), settle_ms=30, samples=4, warmup_frames=10, baseline_frames=10, frames=20)

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
        settings = replace(default_settings(), warmup_frames=0, baseline_frames=2, frames=2)

        controller.connect(settings)
        result = controller.tune_drift(settings)

        self.assertGreaterEqual(len(result.attempts), 2)
        self.assertIsNotNone(result.best)
        self.assertIn("Tune attempt", "\n".join(messages))
        self.assertIn("Tune best", "\n".join(messages))

    def test_controller_emits_live_progress_messages(self):
        messages = []
        controller = DebugController(DemoAcquisition(), progress=messages.append)
        settings = replace(default_settings(), warmup_frames=1, baseline_frames=2, frames=2)

        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)
        controller.capture_control(settings)
        controller.capture_target(settings)

        self.assertIn("Connecting to demo acquisition", messages)
        self.assertIn("Configuring pattern=adjacent dac=100 settle=30ms samples=4", messages)
        self.assertIn("Warmup frame 1/1", messages)
        self.assertIn("Baseline frame 2/2", messages)
        self.assertIn("Control drift frame 2/2", messages)
        self.assertIn("Target frame 2/2", messages)

    def test_controller_streams_target_reconstructions_as_they_are_created(self):
        previews = []
        controller = DebugController(DemoAcquisition(), target_preview=previews.append)
        settings = replace(default_settings(), warmup_frames=0, baseline_frames=2, frames=3)

        controller.connect(settings)
        controller.configure(settings)
        controller.capture_baseline(settings)
        target = controller.capture_target(settings)

        self.assertEqual([len(preview) for preview in previews], [1, 2, 3])
        self.assertEqual(len(target.reconstructions), 3)

    def test_demo_controller_captures_baseline_then_target(self):
        controller = DebugController(DemoAcquisition())
        settings = default_settings()
        controller.connect(settings)
        controller.configure(settings)
        baseline = controller.capture_baseline(settings)
        self.assertEqual(controller.state, ControllerState.BASELINE_READY)
        self.assertGreater(len(baseline), 0)
        target = controller.capture_target(settings)
        self.assertEqual(controller.state, ControllerState.TARGET_READY)
        self.assertEqual(len(target.reconstructions), settings.frames)

    def test_target_requires_baseline(self):
        controller = DebugController(DemoAcquisition())
        settings = default_settings()
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
        settings = replace(default_settings(), warmup_frames=0, baseline_frames=5)
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
        settings = default_settings()
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
        settings = default_settings()
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
        settings = default_settings()
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
        settings = default_settings()
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
        settings = replace(default_settings(), dac=321, settle_ms=45, samples=7)
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


class TestCaptureLogging(unittest.TestCase):
    """Captures made through the UI controller must reach disk, labelled.

    Before this existed the controller computed reconstructions in memory and
    discarded every frame, so UI sessions left no data behind at all.
    """

    def _settings(self, log_dir: str):
        return replace(
            UiSettings.default(),
            warmup_frames=0,
            baseline_frames=2,
            frames=2,
            specimen="trunk-a",
            stage="s2-side-3cm",
            log_dir=Path(log_dir),
            log_enabled=True,
        )

    def test_baseline_and_target_write_labelled_csv_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = self._settings(tmp)
            controller = DebugController(DemoAcquisition())
            controller.connect(settings)
            controller.configure(settings)

            baseline = controller.capture_baseline(settings)
            target = controller.capture_target(settings)

            for path in (baseline.log_path, target.log_path):
                self.assertIsNotNone(path)
                self.assertTrue(path.exists())
                with path.open(newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertTrue(rows, f"{path} contains only a header")
                self.assertEqual({row["specimen"] for row in rows}, {"trunk-a"})
                self.assertEqual({row["stage"] for row in rows}, {"s2-side-3cm"})

            self.assertIn("trunk-a", baseline.log_path.name)
            self.assertIn("s2-side-3cm", baseline.log_path.name)
            self.assertNotEqual(baseline.log_path, target.log_path)

    def test_logging_disabled_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(self._settings(tmp), log_enabled=False)
            controller = DebugController(DemoAcquisition())
            controller.connect(settings)
            controller.configure(settings)

            baseline = controller.capture_baseline(settings)

            self.assertIsNone(baseline.log_path)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_every_baseline_frame_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(self._settings(tmp), baseline_frames=4)
            controller = DebugController(DemoAcquisition())
            controller.connect(settings)
            controller.configure(settings)

            baseline = controller.capture_baseline(settings)

            with baseline.log_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len({row["frame_id"] for row in rows}), 4)


if __name__ == "__main__":
    unittest.main()
