"""Qt front-end tests.

Run offscreen so they work in CI and over SSH. The widget layer is deliberately
thin -- the logic worth testing lives in ``tree_ert.capture_view`` and
``run_record`` and is tested there -- so these cover construction, the settings
and conditions round-trip, and one end-to-end demo capture through the worker.

The worker is driven synchronously by calling ``run()`` directly rather than
starting a QThread: the thread is Qt's concern, the sequence is ours, and a
threaded test would trade determinism for coverage of code we did not write.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication

    PYQT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on a box without PyQt6
    PYQT_AVAILABLE = False

import run_record
from run_record import Conditions
from tree_ert.acquisition import DemoAcquisition
from tree_ert.settings import UiSettings

if PYQT_AVAILABLE:
    from tree_ert.qt import theme
    from tree_ert.qt.main_window import ConditionsPanel, MainWindow, SettingsPanel
    from tree_ert.qt.worker import (
        CaptureRequest,
        CaptureWorker,
        SessionBaseline,
        available_ports,
    )


def demo_settings(**overrides) -> UiSettings:
    base = UiSettings(
        port="DEMO",
        pattern="adjacent",
        current_range="high",
        dac=100,
        settle_ms=10,
        samples=4,
        warmup_frames=0,
        frames=3,
    )
    if overrides:
        from dataclasses import replace

        base = replace(base, **overrides)
    return base


@unittest.skipUnless(PYQT_AVAILABLE, "PyQt6 is not installed")
class QtTestCase(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


class PortEnumerationTests(QtTestCase):
    def test_available_ports_returns_pairs_without_raising(self):
        # Cross-platform enumeration; on a box with no serial hardware this is
        # legitimately empty, which must not be an error.
        ports = available_ports()
        self.assertIsInstance(ports, list)
        for entry in ports:
            self.assertEqual(len(entry), 2)


class ThemeTests(QtTestCase):
    """Status colour is semantic: it must track states the instrument defines."""

    @staticmethod
    def summary(**overrides):
        import phase3a_unified_reconstruct as unified
        from tree_ert import capture_view

        records = overrides.pop(
            "records",
            [
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 200.0, 200.0, "OK"),
                unified.MeasurementRecord("REV", (1, 0), (2, 3), -200.0, 200.0, "OK"),
            ],
        )
        frame = unified.UnifiedFrame(
            frame_id=1,
            pattern="ADJACENT",
            dac_code=100,
            settle_ms=10,
            sample_count=4,
            records=records,
        )
        return capture_view.frame_summary(frame)

    def test_healthy_in_window_frame_is_ok(self):
        self.assertEqual(theme.frame_state(self.summary()), "ok")

    def test_quantisation_limited_is_a_warning_not_a_failure(self):
        # The records are valid; they are just at the converter's resolution.
        # The measurement is real, but a difference image built on it would be
        # dominated by rounding (ADR-0026).
        import phase3a_unified_reconstruct as unified

        summary = self.summary(
            records=[
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 60.0, 200.0, "OK"),
                unified.MeasurementRecord("REV", (1, 0), (2, 3), 60.0, 200.0, "OK"),
            ]
        )
        self.assertTrue(summary.quantisation_limited)
        self.assertEqual(theme.frame_state(summary), "warn")

    def test_a_low_resistance_specimen_is_still_ok(self):
        # 17 ohm on the cut trunk is normal. The old fixed window called it a
        # warning on every single scan.
        import phase3a_unified_reconstruct as unified

        summary = self.summary(
            records=[
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 6.2, 364.0, "OK"),
                unified.MeasurementRecord("REV", (1, 0), (2, 3), -6.2, 364.0, "OK"),
            ]
        )
        self.assertLess(summary.median_resistance_kohm, 0.02)
        self.assertEqual(theme.frame_state(summary), "ok")

    def test_a_flagged_record_makes_the_whole_frame_bad(self):
        import phase3a_unified_reconstruct as unified

        summary = self.summary(
            records=[
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 200.0, 200.0, "OK"),
                unified.MeasurementRecord("REV", (1, 0), (2, 3), -200.0, 0.0, "I_LOW"),
            ]
        )
        self.assertEqual(theme.frame_state(summary), "bad")

    def test_broken_polarity_interleaving_is_bad_even_when_all_records_pass(self):
        import phase3a_unified_reconstruct as unified

        summary = self.summary(
            records=[
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 200.0, 200.0, "OK"),
                unified.MeasurementRecord("FWD", (0, 1), (3, 4), 200.0, 200.0, "OK"),
            ]
        )
        self.assertEqual(theme.frame_state(summary), "bad")

    def test_empty_frame_has_no_state_rather_than_a_reassuring_one(self):
        summary = self.summary(records=[])
        self.assertEqual(theme.frame_state(summary), "")

    def test_apply_state_sets_the_property_qt_styles_on(self):
        from PyQt6.QtWidgets import QLabel

        label = QLabel()
        theme.apply_state(label, "bad")
        self.assertEqual(label.property("state"), "bad")
        theme.apply_state(label, None)
        self.assertEqual(label.property("state"), "")

    def test_stylesheet_defines_every_state_the_mapping_can_return(self):
        for state in ("ok", "warn", "bad", "busy"):
            self.assertIn(f'state="{state}"', theme.STYLESHEET)

    def test_arrow_icons_are_generated_at_the_declared_size(self):
        from PyQt6.QtGui import QPixmap

        path = theme.arrow_icon("down", theme.TEXT_MUTED)
        pixmap = QPixmap(path)
        self.assertFalse(pixmap.isNull(), "arrow icon failed to render")
        self.assertEqual(pixmap.width(), theme.ARROW_WIDTH)
        self.assertEqual(pixmap.height(), theme.ARROW_HEIGHT)

    def test_up_and_down_arrows_are_distinct_files(self):
        self.assertNotEqual(
            theme.arrow_icon("up", theme.TEXT_MUTED),
            theme.arrow_icon("down", theme.TEXT_MUTED),
        )

    def test_stylesheet_resolves_every_arrow_token(self):
        # An unresolved token leaves Qt with url(__ARROW_DOWN__), which it
        # silently fails to load -- the arrow just disappears.
        resolved = theme.stylesheet()
        self.assertNotIn("__ARROW", resolved)
        self.assertIn("url(", resolved)

    def test_arrow_paths_use_forward_slashes_for_qss(self):
        # Qt stylesheet url() does not accept Windows backslashes.
        self.assertNotIn("\\", theme.arrow_icon("down", theme.TEXT_MUTED))


class ConditionsPanelTests(QtTestCase):
    def test_unfilled_numbers_are_recorded_as_not_measured(self):
        panel = ConditionsPanel()
        conditions = panel.conditions()
        self.assertIsNone(conditions.saline_g_per_l)
        self.assertIsNone(conditions.water_temp_c)
        self.assertIsNone(conditions.fill_depth_mm)

    def test_filled_numbers_round_trip(self):
        panel = ConditionsPanel()
        panel.saline.setValue(2.5)
        panel.fill_depth.setValue(40.0)
        panel.temperature.setValue(28.5)
        panel.protrusion.setValue(4.0)
        panel.grounding.setCurrentText("floating")
        panel.medium.setText("saline tank")
        conditions = panel.conditions()
        self.assertAlmostEqual(conditions.saline_g_per_l, 2.5)
        self.assertAlmostEqual(conditions.fill_depth_mm, 40.0)
        self.assertAlmostEqual(conditions.water_temp_c, 28.5)
        self.assertAlmostEqual(conditions.electrode_protrusion_mm, 4.0)
        self.assertEqual(conditions.grounding, "floating")
        self.assertEqual(conditions.validate(), [])

    def test_blank_medium_falls_back_to_unknown_and_is_flagged(self):
        panel = ConditionsPanel()
        panel.medium.setText("   ")
        conditions = panel.conditions()
        self.assertEqual(conditions.medium, "unknown")
        self.assertIn("medium is not set", conditions.validate())

    def test_default_grounding_is_flagged_as_unrecorded(self):
        # Grounding is the CMRR discriminator; silence about it is a defect.
        problems = ConditionsPanel().conditions().validate()
        self.assertTrue(any("grounding" in p for p in problems))


class SettingsPanelTests(QtTestCase):
    def test_dac_ceiling_follows_the_current_range(self):
        panel = SettingsPanel(demo_settings())
        panel.current_range.setCurrentText("low")
        self.assertEqual(panel.dac.maximum(), 420)
        panel.current_range.setCurrentText("medium")
        self.assertEqual(panel.dac.maximum(), 680)
        panel.current_range.setCurrentText("high")
        self.assertEqual(panel.dac.maximum(), 620)

    def test_settings_round_trip_through_the_widgets(self):
        panel = SettingsPanel(demo_settings())
        panel.port.setEditText("/dev/ttyUSB0")
        panel.settle.setValue(25)
        panel.samples.setValue(16)
        panel.frames.setValue(7)
        settings = panel.settings()
        self.assertEqual(settings.port, "/dev/ttyUSB0")
        self.assertEqual(settings.settle_ms, 25)
        self.assertEqual(settings.samples, 16)
        self.assertEqual(settings.frames, 7)
        settings.validate()

    def test_unexposed_settings_keep_their_stored_values(self):
        # A setting that is not on screen must still be recorded, not reset.
        base = demo_settings(expected_shunt_ohms=97.9, electrode_offset=3)
        settings = SettingsPanel(base).settings()
        self.assertEqual(settings.expected_shunt_ohms, 97.9)
        self.assertEqual(settings.electrode_offset, 3)


class CaptureWorkerTests(QtTestCase):
    def make_worker(self, **overrides) -> CaptureWorker:
        request = CaptureRequest(
            settings=demo_settings(**overrides.pop("settings", {})),
            conditions=overrides.pop(
                "conditions",
                Conditions(medium="saline tank", grounding="floating"),
            ),
            label=overrides.pop("label", "demo"),
            frames=overrides.pop("frames", 3),
            warmup_frames=overrides.pop("warmup_frames", 2),
        )
        return CaptureWorker(DemoAcquisition(), request, self.log_dir)

    def collect(self, worker: CaptureWorker) -> dict:
        events = {"frames": [], "warmups": [], "finished": [], "failed": []}
        worker.frame_captured.connect(
            lambda frame, index, text: events["frames"].append((index, text))
        )
        worker.warmup_frame.connect(
            lambda done, total, text: events["warmups"].append((done, total))
        )
        worker.finished.connect(
            lambda path, summary: events["finished"].append((path, summary))
        )
        worker.failed.connect(lambda message: events["failed"].append(message))
        worker.run()
        return events

    def test_demo_capture_writes_a_complete_run(self):
        events = self.collect(self.make_worker(frames=3, warmup_frames=2))
        self.assertEqual(events["failed"], [])
        self.assertEqual(len(events["frames"]), 3)
        self.assertEqual(len(events["warmups"]), 2)
        self.assertEqual(len(events["finished"]), 1)

        runs = run_record.list_runs(self.log_dir)
        self.assertEqual(len(runs), 1)
        run = runs[0]
        for name in ("conditions.json", "conditions.md", "frames.csv", "summary.txt"):
            self.assertTrue((run / name).is_file(), f"{name} missing")

    def test_every_frame_reaches_the_csv_unaveraged(self):
        self.collect(self.make_worker(frames=4, warmup_frames=0))
        run = run_record.list_runs(self.log_dir)[0]
        rows = (run / "frames.csv").read_text().strip().splitlines()
        indexes = {line.split(",")[0] for line in rows[1:]}
        self.assertEqual(indexes, {"0", "1", "2", "3"})

    def test_warmup_frames_are_reported_but_not_recorded(self):
        self.collect(self.make_worker(frames=1, warmup_frames=3))
        run = run_record.list_runs(self.log_dir)[0]
        rows = (run / "frames.csv").read_text().strip().splitlines()
        self.assertEqual({line.split(",")[0] for line in rows[1:]}, {"0"})

    def test_conditions_and_settings_are_recorded_with_the_run(self):
        self.collect(
            self.make_worker(
                conditions=Conditions(
                    medium="saline tank", saline_g_per_l=2.5, grounding="grounded"
                )
            )
        )
        payload = run_record.load_run(run_record.list_runs(self.log_dir)[0])
        self.assertEqual(payload["conditions"].saline_g_per_l, 2.5)
        self.assertEqual(payload["conditions"].grounding, "grounded")
        self.assertEqual(payload["settings"]["pattern"], "adjacent")
        self.assertEqual(payload["incomplete"], [])

    def test_completed_run_is_appended_to_the_scans_index(self):
        self.collect(self.make_worker(frames=3, warmup_frames=0, label="step-1"))
        rows = run_record.read_index(self.log_dir)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["outcome"], "complete")
        self.assertEqual(row["frames"], "3")
        self.assertEqual(row["pattern"], "adjacent")
        self.assertEqual(row["grounding"], "floating")
        self.assertIn("step-1", row["run_id"])

    def test_index_accumulates_one_row_per_scan(self):
        # The titration series is read as a table; one row per step is the point.
        for step in range(3):
            self.collect(
                self.make_worker(
                    frames=2,
                    warmup_frames=0,
                    label=f"step-{step}",
                    conditions=Conditions(
                        medium="saline tank",
                        grounding="floating",
                        saline_g_per_l=float(step),
                    ),
                )
            )
        rows = run_record.read_index(self.log_dir)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["saline_g_per_l"] for r in rows], ["0", "1", "2"])

    def test_cancelled_run_is_indexed_as_cancelled(self):
        worker = self.make_worker(frames=10, warmup_frames=0)
        worker.frame_captured.connect(lambda *_: worker.cancel())
        self.collect(worker)
        rows = run_record.read_index(self.log_dir)
        self.assertEqual(rows[0]["outcome"], "cancelled")
        self.assertEqual(rows[0]["frames"], "1")

    def test_failed_run_still_reaches_the_index(self):
        # A failed scan happened, and the index is the only place a later
        # reader would see that it did.
        class FailingAcquisition(DemoAcquisition):
            def capture_frame(self):
                raise RuntimeError("serial port vanished")

        request = CaptureRequest(
            settings=demo_settings(),
            conditions=Conditions(medium="saline tank", grounding="floating"),
            label="doomed",
            frames=5,
            warmup_frames=0,
        )
        worker = CaptureWorker(FailingAcquisition(), request, self.log_dir)
        self.collect(worker)
        rows = run_record.read_index(self.log_dir)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "failed")

    def test_index_carries_the_headline_metrics(self):
        self.collect(self.make_worker(frames=3, warmup_frames=0))
        row = run_record.read_index(self.log_dir)[0]
        for column in (
            "reciprocity_median_percent",
            "reciprocity_sign_flips",
            "noise_median_kohm",
            "noise_median_percent",
        ):
            self.assertIn(column, row)

    def test_summary_reports_reciprocity_and_noise(self):
        events = self.collect(self.make_worker(frames=3, warmup_frames=0))
        summary = events["finished"][0][1]
        self.assertIn("Reciprocity:", summary)
        self.assertIn("Noise floor:", summary)

    def test_cancel_keeps_the_frames_already_captured(self):
        worker = self.make_worker(frames=10, warmup_frames=0)
        # Cancel as soon as the first frame lands: a cancelled run is still data.
        worker.frame_captured.connect(lambda *_: worker.cancel())
        events = self.collect(worker)
        self.assertEqual(events["failed"], [])
        self.assertEqual(len(events["frames"]), 1)
        run = run_record.list_runs(self.log_dir)[0]
        self.assertTrue((run / "frames.csv").is_file())
        self.assertTrue((run / "conditions.json").is_file())

    def test_invalid_settings_fail_without_raising_into_qt(self):
        worker = self.make_worker(settings={"port": "  "})
        events = self.collect(worker)
        self.assertEqual(events["finished"], [])
        self.assertEqual(len(events["failed"]), 1)
        self.assertIn("port is required", events["failed"][0])

    def test_a_failure_mid_capture_still_leaves_the_run_readable(self):
        class FailingAcquisition(DemoAcquisition):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def capture_frame(self):
                self.calls += 1
                if self.calls > 2:
                    raise RuntimeError("serial port vanished")
                return super().capture_frame()

        request = CaptureRequest(
            settings=demo_settings(),
            conditions=Conditions(medium="saline tank", grounding="floating"),
            label="interrupted",
            frames=10,
            warmup_frames=0,
        )
        worker = CaptureWorker(FailingAcquisition(), request, self.log_dir)
        events = self.collect(worker)
        self.assertEqual(len(events["failed"]), 1)
        self.assertIn("serial port vanished", events["failed"][0])

        run = run_record.list_runs(self.log_dir)[0]
        rows = (run / "frames.csv").read_text().strip().splitlines()
        self.assertEqual({line.split(",")[0] for line in rows[1:]}, {"0", "1"})
        self.assertTrue((run / "conditions.json").is_file())


class ReconstructionFlowTests(QtTestCase):
    """The session-baseline model: first run is the reference, later runs image."""

    def capture(self, worker: CaptureWorker) -> dict:
        events = {
            "frames": [],
            "images": [],
            "skipped": [],
            "failed": [],
            "finished": [],
        }
        worker.frame_captured.connect(
            lambda frame, index, text: events["frames"].append(frame)
        )
        worker.reconstructed.connect(
            lambda path, result: events["images"].append((path, result))
        )
        worker.reconstruction_skipped.connect(
            lambda reason: events["skipped"].append(reason)
        )
        worker.failed.connect(lambda message: events["failed"].append(message))
        worker.finished.connect(
            lambda path, summary: events["finished"].append(path)
        )
        worker.run()
        return events

    def make_worker(self, baseline=None, label="run", **overrides) -> CaptureWorker:
        request = CaptureRequest(
            settings=demo_settings(**overrides.pop("settings", {})),
            conditions=Conditions(medium="coconut trunk", grounding="floating"),
            label=label,
            frames=overrides.pop("frames", 2),
            warmup_frames=0,
            baseline=baseline,
        )
        return CaptureWorker(DemoAcquisition(), request, self.log_dir)

    def test_a_baseline_run_produces_no_image_and_says_why(self):
        # A baseline has nothing to differ from. That is correct, not a gap --
        # but it must never be silent.
        events = self.capture(self.make_worker(baseline=None, label="baseline"))
        self.assertEqual(events["images"], [])
        self.assertEqual(len(events["skipped"]), 1)
        self.assertIn("baseline", events["skipped"][0].lower())

    def test_a_baseline_run_saves_its_control_image_not_a_reconstruction(self):
        self.capture(self.make_worker(baseline=None, label="baseline", frames=4))
        run = run_record.list_runs(self.log_dir)[0]
        for name in ("control.png", "control.npz", "control.txt"):
            self.assertTrue((run / name).is_file(), f"{name} missing")
        self.assertFalse((run / "reconstruction.png").exists())
        self.assertIn("noise", (run / "control.txt").read_text(encoding="utf-8"))

    def test_a_short_baseline_saves_no_control_and_does_not_fail(self):
        events = self.capture(self.make_worker(baseline=None, label="baseline"))
        self.assertEqual(events["failed"], [])
        run = run_record.list_runs(self.log_dir)[0]
        self.assertFalse((run / "control.png").exists())

    def test_a_later_run_is_differenced_against_the_baseline(self):
        from tree_ert.settings import settings_to_dict

        first = self.make_worker(baseline=None, label="baseline")
        baseline_events = self.capture(first)
        baseline = SessionBaseline(
            run_id="baseline-run",
            frames=baseline_events["frames"],
            settings=settings_to_dict(demo_settings()),
        )

        events = self.capture(self.make_worker(baseline=baseline, label="target"))
        self.assertEqual(events["failed"], [])
        self.assertEqual(len(events["images"]), 1)
        image_path, result = events["images"][0]
        self.assertTrue(Path(image_path).is_file())
        self.assertEqual(Path(image_path).name, "reconstruction.png")
        self.assertGreater(result.total_pairs, 0)

    def gated_target(self, override: bool):
        """Target run against a baseline, with the reciprocity gate forced to fail."""
        from unittest import mock
        from tree_ert import reconstruction as recon
        from tree_ert.settings import settings_to_dict

        baseline_events = self.capture(self.make_worker(label="baseline", frames=4))
        baseline = SessionBaseline(
            "baseline-run", baseline_events["frames"], settings_to_dict(demo_settings())
        )
        worker = self.make_worker(baseline=baseline, label="target", frames=4)
        worker._request = type(worker._request)(
            **{**worker._request.__dict__, "override_reciprocity": override}
        )
        with mock.patch.object(
            recon, "reciprocity_gate", return_value="median reciprocity error 79.1% exceeds 10%"
        ):
            events = self.capture(worker)
        run = [r for r in run_record.list_runs(self.log_dir) if "target" in r.name][0]
        return events, run

    def test_failed_reciprocity_refuses_the_image_but_keeps_the_frames(self):
        events, run = self.gated_target(override=False)
        self.assertEqual(events["failed"], [])
        self.assertEqual(events["images"], [])
        self.assertIn("Reciprocity check failed", events["skipped"][-1])
        self.assertTrue((run / "frames.csv").is_file())
        self.assertFalse((run / "reconstruction.png").exists())
        row = [r for r in run_record.read_index(self.log_dir) if "target" in r["run_id"]][0]
        self.assertEqual(row["reciprocity_gate"], "fail")

    def test_override_images_anyway_and_stamps_it_everywhere(self):
        events, run = self.gated_target(override=True)
        self.assertEqual(len(events["images"]), 1)
        text = (run / "reconstruction.txt").read_text(encoding="utf-8")
        self.assertIn("RECIPROCITY OVERRIDDEN - NOT VALID DATA", text)
        row = [r for r in run_record.read_index(self.log_dir) if "target" in r["run_id"]][0]
        self.assertEqual(row["reciprocity_gate"], "overridden")

    def test_demo_data_passes_the_gate(self):
        from tree_ert.settings import settings_to_dict

        baseline_events = self.capture(self.make_worker(label="baseline", frames=4))
        baseline = SessionBaseline(
            "baseline-run", baseline_events["frames"], settings_to_dict(demo_settings())
        )
        events = self.capture(self.make_worker(baseline=baseline, label="target", frames=4))
        self.assertEqual(len(events["images"]), 1)
        row = [r for r in run_record.read_index(self.log_dir) if "target" in r["run_id"]][0]
        self.assertEqual(row["reciprocity_gate"], "pass")

    def test_the_image_and_its_data_land_in_the_run_folder(self):
        from tree_ert.settings import settings_to_dict

        baseline_events = self.capture(self.make_worker(label="baseline"))
        baseline = SessionBaseline(
            "baseline-run",
            baseline_events["frames"],
            settings_to_dict(demo_settings()),
        )
        self.capture(self.make_worker(baseline=baseline, label="target"))

        target_run = [
            run for run in run_record.list_runs(self.log_dir) if "target" in run.name
        ][0]
        for name in ("reconstruction.png", "reconstruction.npz", "reconstruction.txt"):
            self.assertTrue((target_run / name).is_file(), f"{name} missing")

    def test_the_baseline_run_id_is_recorded_in_the_index(self):
        from tree_ert.settings import settings_to_dict

        baseline_events = self.capture(self.make_worker(label="baseline"))
        baseline = SessionBaseline(
            "20260916-000000-baseline",
            baseline_events["frames"],
            settings_to_dict(demo_settings()),
        )
        self.capture(self.make_worker(baseline=baseline, label="target"))

        rows = run_record.read_index(self.log_dir)
        self.assertEqual(rows[0]["baseline_run"], "")
        self.assertEqual(rows[1]["baseline_run"], "20260916-000000-baseline")
        self.assertNotEqual(rows[1]["peak_value"], "")

    def test_mismatched_settings_refuse_to_reconstruct(self):
        # Hard block: an image built on incomparable data is worse than none.
        from tree_ert.settings import settings_to_dict

        baseline_events = self.capture(self.make_worker(label="baseline"))
        baseline = SessionBaseline(
            "baseline-run",
            baseline_events["frames"],
            settings_to_dict(demo_settings(dac=400)),
        )
        events = self.capture(self.make_worker(baseline=baseline, label="target"))
        self.assertEqual(events["images"], [])
        self.assertEqual(len(events["skipped"]), 1)
        self.assertIn("dac", events["skipped"][0])
        # The capture itself still succeeded and was recorded.
        self.assertEqual(len(events["finished"]), 1)

    def test_a_reconstruction_failure_does_not_fail_the_capture(self):
        # The frames are already on disk; a solver problem costs an image only.
        from tree_ert.settings import settings_to_dict

        baseline = SessionBaseline(
            "baseline-run", [], settings_to_dict(demo_settings())
        )
        events = self.capture(self.make_worker(baseline=baseline, label="target"))
        self.assertEqual(events["failed"], [])
        self.assertEqual(len(events["finished"]), 1)
        self.assertEqual(len(events["skipped"]), 1)
        self.assertIn("failed", events["skipped"][0].lower())


class MainWindowTests(QtTestCase):
    def test_window_constructs_and_starts_with_no_frames(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        self.assertTrue(window.settings_panel.demo.isChecked())
        self.assertEqual(window.table.rowCount(), 0)
        self.assertTrue(window.start_button.isEnabled())
        self.assertFalse(window.stop_button.isEnabled())

    def test_left_pane_is_never_narrower_than_its_content_can_shrink_to(self):
        # Horizontal scrolling is off, so a pane below the content's MINIMUM
        # clips the fields at the divider instead of scrolling to them. Above
        # the minimum the rows merely wrap their labels, which is intended.
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        self.assertGreaterEqual(
            window._left_width,
            window.settings_panel.minimumSizeHint().width(),
        )
        self.assertGreaterEqual(
            window._left_width,
            window.conditions_panel.minimumSizeHint().width(),
        )

    def test_table_renders_one_row_per_record_and_flags_bad_quality(self):
        import phase3a_unified_reconstruct as unified

        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        frame = unified.UnifiedFrame(
            frame_id=1,
            pattern="ADJACENT",
            dac_code=100,
            settle_ms=10,
            sample_count=4,
            records=[
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 40.0, 200.0, "OK"),
                unified.MeasurementRecord("REV", (1, 0), (2, 3), -40.0, 0.0, "I_LOW"),
            ],
        )
        window._fill_table(frame)
        self.assertEqual(window.table.rowCount(), 2)
        self.assertEqual(window.table.item(0, 2).text(), "E1")
        self.assertEqual(window.table.item(1, 9).text(), "I_LOW")
        # Zero current shows as absent, not as an infinity.
        self.assertEqual(window.table.item(1, 8).text(), "-")
        # The flagged row is tinted; the healthy one is not.
        self.assertEqual(
            window.table.item(1, 0).background().color(), theme.ROW_FLAGGED_BG
        )
        self.assertNotEqual(
            window.table.item(0, 0).background().color(), theme.ROW_FLAGGED_BG
        )

    def test_status_pill_follows_the_captured_frame(self):
        import phase3a_unified_reconstruct as unified

        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        window._expected_frames = 1
        flagged = unified.UnifiedFrame(
            frame_id=1,
            pattern="ADJACENT",
            dac_code=100,
            settle_ms=10,
            sample_count=4,
            records=[
                unified.MeasurementRecord("FWD", (0, 1), (2, 3), 200.0, 200.0, "OK"),
                unified.MeasurementRecord("REV", (1, 0), (2, 3), -200.0, 0.0, "I_LOW"),
            ],
        )
        window._on_frame(flagged, 0, "summary text")
        self.assertEqual(window.frame_status.property("state"), "bad")

    def test_failure_marks_the_run_status(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        window._set_run_status("Failed", "bad")
        self.assertEqual(window.run_status.property("state"), "bad")
        self.assertEqual(window.run_status.text(), "Failed")

    def test_log_pane_is_mirrored_to_a_file_that_survives_the_window(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        window._log("something worth keeping")
        window.close()
        text = (self.log_dir / run_record.SessionLog.FILENAME).read_text()
        self.assertIn("something worth keeping", text)
        self.assertIn("Session started", text)
        self.assertIn("Session ended", text)

    def test_session_log_appends_rather_than_truncating(self):
        # Reopening the app must not erase the previous session.
        first = MainWindow(log_dir=self.log_dir, demo=True)
        first._log("first session line")
        first.close()
        second = MainWindow(log_dir=self.log_dir, demo=True)
        second._log("second session line")
        second.close()
        text = (self.log_dir / run_record.SessionLog.FILENAME).read_text()
        self.assertIn("first session line", text)
        self.assertIn("second session line", text)

    def test_startup_reports_the_scans_folder_and_what_is_in_it(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        shown = window.log.toPlainText()
        self.assertIn(str(self.log_dir.resolve()), shown)
        self.assertIn("0 scan(s) already recorded", shown)

    def test_existing_scans_are_counted_on_startup(self):
        run_record.create_run(self.log_dir, "earlier").close()
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        self.assertIn("1 scan(s) already recorded", window.log.toPlainText())

    def test_run_path_points_into_the_scans_folder(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        window._on_started("20260916-144022-demo")
        self.assertEqual(
            window._run_path,
            self.log_dir / run_record.RUNS_DIRNAME / "20260916-144022-demo",
        )

    def test_right_pane_has_measurements_and_reconstruction_tabs(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        self.assertEqual(window.tabs.count(), 2)
        self.assertEqual(window.tabs.tabText(0), "Measurements")
        self.assertEqual(window.tabs.tabText(1), "Reconstruction")

    def test_first_finished_run_becomes_the_session_baseline(self):
        import phase3a_unified_reconstruct as unified

        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        self.assertIsNone(window._baseline)
        self.assertFalse(window.clear_baseline_button.isEnabled())

        window._frames = [
            unified.UnifiedFrame(1, "ADJACENT", 100, 10, 4, [])
        ]
        window._on_finished(str(self.log_dir / "runs" / "20260916-1-first"), "summary")
        self.assertIsNotNone(window._baseline)
        self.assertEqual(window._baseline.run_id, "20260916-1-first")
        self.assertTrue(window.clear_baseline_button.isEnabled())

    def test_a_second_run_does_not_replace_the_baseline(self):
        import phase3a_unified_reconstruct as unified

        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        window._frames = [unified.UnifiedFrame(1, "ADJACENT", 100, 10, 4, [])]
        window._on_finished(str(self.log_dir / "runs" / "first"), "s")
        window._on_finished(str(self.log_dir / "runs" / "second"), "s")
        self.assertEqual(window._baseline.run_id, "first")

    def test_clearing_the_baseline_makes_the_next_run_the_new_one(self):
        # Needed whenever the specimen or the settings change mid-session.
        import phase3a_unified_reconstruct as unified

        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        window._frames = [unified.UnifiedFrame(1, "ADJACENT", 100, 10, 4, [])]
        window._on_finished(str(self.log_dir / "runs" / "first"), "s")
        window.clear_baseline()
        self.assertIsNone(window._baseline)
        self.assertFalse(window.clear_baseline_button.isEnabled())
        window._on_finished(str(self.log_dir / "runs" / "second"), "s")
        self.assertEqual(window._baseline.run_id, "second")

    def test_a_skipped_reconstruction_states_its_reason_on_screen(self):
        window = MainWindow(log_dir=self.log_dir, demo=True)
        self.addCleanup(window.close)
        window._on_reconstruction_skipped("This run is the session baseline.")
        self.assertIn("baseline", window.image_status.text())
        self.assertIn("No reconstruction", window.log.toPlainText())

    def test_settings_are_persisted_on_close(self):
        from tree_ert.settings import load_settings, settings_path

        window = MainWindow(log_dir=self.log_dir, demo=True)
        window.settings_panel.port.setEditText("/dev/ttyUSB1")
        window.settings_panel.samples.setValue(32)
        window.close()
        stored = load_settings(settings_path(self.log_dir))
        self.assertIsNotNone(stored)
        self.assertEqual(stored.port, "/dev/ttyUSB1")
        self.assertEqual(stored.samples, 32)


class EntryPointTests(unittest.TestCase):
    def test_argument_parsing(self):
        import tree_ert_qt

        args = tree_ert_qt.parse_args(["--demo", "--port", "/dev/ttyUSB0"])
        self.assertTrue(args.demo)
        self.assertEqual(args.port, "/dev/ttyUSB0")
        self.assertEqual(args.log_dir, Path("scans"))

    def test_scans_default_is_separate_from_the_legacy_log_dir(self):
        # Everything under scans/ has a conditions sheet; phase3a_logs/ holds
        # ~190 flat CSVs that do not. Mixing them makes that uncheckable.
        import tree_ert_qt

        self.assertNotEqual(tree_ert_qt.DEFAULT_SCANS_DIR, tree_ert_qt.LEGACY_SCANS_DIR)
        self.assertEqual(tree_ert_qt.parse_args([]).log_dir, tree_ert_qt.DEFAULT_SCANS_DIR)

    def test_log_dir_can_still_be_overridden(self):
        import tree_ert_qt

        args = tree_ert_qt.parse_args(["--log-dir", "somewhere/else"])
        self.assertEqual(args.log_dir, Path("somewhere/else"))


class SettingsMigrationTests(unittest.TestCase):
    """Moving the scans root must not silently reset a dialled-in instrument."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_settings_are_seeded_from_the_legacy_folder_once(self):
        import tree_ert_qt
        from dataclasses import replace
        from tree_ert.settings import load_settings, save_settings, settings_path

        legacy = self.root / "phase3a_logs"
        target = self.root / "scans"
        save_settings(
            replace(UiSettings.default(), port="COM12", samples=32),
            settings_path(legacy),
        )

        original = tree_ert_qt.LEGACY_SCANS_DIR
        tree_ert_qt.LEGACY_SCANS_DIR = legacy
        try:
            self.assertTrue(tree_ert_qt.migrate_settings(target))
            # Second call is a no-op: it must never overwrite live settings.
            self.assertFalse(tree_ert_qt.migrate_settings(target))
        finally:
            tree_ert_qt.LEGACY_SCANS_DIR = original

        stored = load_settings(settings_path(target))
        self.assertEqual(stored.port, "COM12")
        self.assertEqual(stored.samples, 32)

    def test_migration_is_a_no_op_with_nothing_to_migrate(self):
        import tree_ert_qt

        original = tree_ert_qt.LEGACY_SCANS_DIR
        tree_ert_qt.LEGACY_SCANS_DIR = self.root / "does-not-exist"
        try:
            self.assertFalse(tree_ert_qt.migrate_settings(self.root / "scans"))
        finally:
            tree_ert_qt.LEGACY_SCANS_DIR = original

    def test_defaults(self):
        import tree_ert_qt

        args = tree_ert_qt.parse_args([])
        self.assertFalse(args.demo)
        self.assertIsNone(args.port)


if __name__ == "__main__":
    unittest.main()
