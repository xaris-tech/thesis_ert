import unittest

from tree_ert.acquisition import DemoAcquisition
from tree_ert.controller import DebugController, ControllerState
from tree_ert.settings import UiSettings


class TestDebugController(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
