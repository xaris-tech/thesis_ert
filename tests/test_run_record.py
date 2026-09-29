import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_record
from run_record import Conditions, RunRecorder, create_run, list_runs, load_run


@dataclass(frozen=True)
class FakeRecord:
    polarity: str
    i_pair: tuple[int, int]
    v_pair: tuple[int, int]
    voltage_mv: float
    current_ua: float
    quality: str


@dataclass(frozen=True)
class FakeFrame:
    frame_id: int
    pattern: str
    dac_code: int
    settle_ms: int
    sample_count: int
    records: list


def make_frame(frame_id: int = 1, voltage: float = -12.345) -> FakeFrame:
    return FakeFrame(
        frame_id=frame_id,
        pattern="ADJACENT",
        dac_code=100,
        settle_ms=10,
        sample_count=4,
        records=[
            FakeRecord("FWD", (0, 1), (2, 3), voltage, 210.0, "OK"),
            FakeRecord("REV", (1, 0), (2, 3), -voltage, 208.5, "OK"),
        ],
    )


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_replaces_separators(self):
        self.assertEqual(run_record.slugify("Titration Step 3"), "titration-step-3")

    def test_collapses_runs_and_strips_edges(self):
        self.assertEqual(run_record.slugify("--A  //  B--"), "a-b")

    def test_empty_label_is_not_an_empty_dirname(self):
        self.assertEqual(run_record.slugify("   "), "run")

    def test_truncates_long_labels(self):
        self.assertLessEqual(len(run_record.slugify("x" * 200)), 60)


class ConditionsTests(unittest.TestCase):
    def test_defaults_report_missing_medium_and_grounding(self):
        problems = Conditions().validate()
        self.assertIn("medium is not set", problems)
        self.assertTrue(any("grounding" in p for p in problems))

    def test_complete_conditions_have_no_problems(self):
        conditions = Conditions(
            medium="saline tank", grounding=run_record.GROUNDING_FLOATING
        )
        self.assertEqual(conditions.validate(), [])

    def test_negative_physical_quantities_are_flagged(self):
        conditions = Conditions(
            medium="saline tank",
            grounding="grounded",
            saline_g_per_l=-1.0,
            fill_depth_mm=-2.0,
            electrode_protrusion_mm=-3.0,
        )
        self.assertEqual(len(conditions.validate()), 3)

    def test_validate_never_raises_so_a_capture_is_always_recordable(self):
        # A run already taken must be writable even when under-documented.
        self.assertIsInstance(Conditions(medium="").validate(), list)


class RunRecorderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def open_run(self, **kwargs) -> RunRecorder:
        recorder = create_run(
            self.root,
            kwargs.pop("label", "titration step 3"),
            when=kwargs.pop("when", datetime(2026, 9, 11, 20, 30, 0)),
            **kwargs,
        )
        self.addCleanup(recorder.close)
        return recorder

    def test_run_directory_is_named_by_timestamp_and_label(self):
        recorder = self.open_run()
        self.assertEqual(recorder.path.name, "20260911-203000-titration-step-3")
        self.assertTrue(recorder.path.is_dir())

    def test_conditions_are_written_on_open_not_on_close(self):
        # A session that crashes mid-capture must still be interpretable.
        recorder = self.open_run(conditions=Conditions(medium="saline tank"))
        payload = json.loads((recorder.path / "conditions.json").read_text())
        self.assertEqual(payload["conditions"]["medium"], "saline tank")
        self.assertTrue((recorder.path / "conditions.md").is_file())

    def test_every_frame_is_kept_unaveraged(self):
        recorder = self.open_run()
        for index in range(3):
            recorder.write_frame(make_frame(frame_id=index + 1, voltage=-10.0 - index))
        rows = (recorder.path / "frames.csv").read_text().strip().splitlines()
        self.assertEqual(len(rows), 1 + 3 * 2)  # header + 3 frames x 2 records
        self.assertEqual(recorder.frames_written, 3)

    def test_frame_rows_carry_electrode_labels_and_frame_index(self):
        recorder = self.open_run()
        recorder.write_frame(make_frame())
        header, first, second = (
            (recorder.path / "frames.csv").read_text().strip().splitlines()
        )
        self.assertEqual(header.split(","), run_record.FRAME_CSV_COLUMNS)
        columns = dict(zip(run_record.FRAME_CSV_COLUMNS, first.split(",")))
        self.assertEqual(columns["frame_index"], "0")
        self.assertEqual(columns["i_plus"], "E1")
        self.assertEqual(columns["i_minus"], "E2")
        self.assertEqual(columns["v_plus"], "E3")
        self.assertEqual(columns["v_minus"], "E4")
        self.assertEqual(columns["polarity"], "FWD")
        self.assertEqual(second.split(",")[7], "REV")

    def test_frames_are_flushed_per_frame(self):
        recorder = self.open_run()
        recorder.write_frame(make_frame())
        # Readable without closing: a crash after frame one keeps frame one.
        self.assertEqual(
            len((recorder.path / "frames.csv").read_text().strip().splitlines()), 3
        )

    def test_raw_serial_text_is_stored_verbatim(self):
        recorder = self.open_run()
        lines = ["FRAME,2,1,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4\r\n", "END,1\n"]
        recorder.write_frame(make_frame(), raw_lines=lines)
        raw = (recorder.raw_dir / "frame-001.txt").read_text()
        self.assertEqual(raw, "FRAME,2,1,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4\nEND,1\n")

    def test_attach_copies_ground_truth_media(self):
        source = self.root / "tank.jpg"
        source.write_bytes(b"not-really-a-jpeg")
        recorder = self.open_run()
        destination = recorder.attach(source)
        self.assertEqual(destination.parent, recorder.media_dir)
        self.assertEqual(destination.read_bytes(), b"not-really-a-jpeg")

    def test_update_conditions_rewrites_both_files(self):
        recorder = self.open_run(conditions=Conditions(medium="tap water"))
        recorder.update_conditions(
            Conditions(medium="saline tank", saline_g_per_l=2.5, grounding="floating")
        )
        payload = json.loads((recorder.path / "conditions.json").read_text())
        self.assertEqual(payload["conditions"]["saline_g_per_l"], 2.5)
        self.assertEqual(payload["incomplete"], [])
        self.assertIn("2.5", (recorder.path / "conditions.md").read_text())

    def test_incomplete_fields_are_named_in_the_record(self):
        recorder = self.open_run(conditions=Conditions())
        payload = json.loads((recorder.path / "conditions.json").read_text())
        self.assertIn("medium is not set", payload["incomplete"])
        self.assertIn("Incomplete", (recorder.path / "conditions.md").read_text())

    def test_settings_snapshot_is_recorded(self):
        recorder = self.open_run(settings={"pattern": "adjacent", "dac": 100})
        payload = json.loads((recorder.path / "conditions.json").read_text())
        self.assertEqual(payload["settings"]["dac"], 100)
        self.assertIn("| dac | 100 |", (recorder.path / "conditions.md").read_text())

    def test_context_manager_closes_the_handle(self):
        with create_run(self.root, "ctx") as recorder:
            recorder.write_frame(make_frame())
            path = recorder.path
        self.assertTrue((path / "frames.csv").is_file())

    def test_write_text_drops_a_report_into_the_run(self):
        recorder = self.open_run()
        path = recorder.write_text("reciprocity.csv", "a,b\n1,2\n")
        self.assertEqual(path.parent, recorder.path)
        self.assertEqual(path.read_text(), "a,b\n1,2\n")


class SessionLogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_entries_are_timestamped_and_flushed_immediately(self):
        log = run_record.SessionLog(self.root)
        self.addCleanup(log.close)
        log.write("hello", when=datetime(2026, 9, 16, 14, 40, 22))
        # Readable without closing: a crash must not lose the session.
        self.assertEqual(log.path.read_text(), "2026-09-16 14:40:22  hello\n")

    def test_log_appends_across_sessions(self):
        first = run_record.SessionLog(self.root)
        first.write("session one")
        first.close()
        second = run_record.SessionLog(self.root)
        self.addCleanup(second.close)
        second.write("session two")
        text = second.path.read_text()
        self.assertIn("session one", text)
        self.assertIn("session two", text)

    def test_banner_separates_entries(self):
        log = run_record.SessionLog(self.root)
        self.addCleanup(log.close)
        log.write("before")
        log.banner("Run 20260916-144022-step-1")
        lines = log.path.read_text().splitlines()
        self.assertIn("-" * 72, lines)
        self.assertTrue(lines[-1].endswith("Run 20260916-144022-step-1"))

    def test_context_manager_closes(self):
        with run_record.SessionLog(self.root) as log:
            log.write("x")
            path = log.path
        self.assertTrue(path.is_file())

    def test_creates_the_root_if_it_does_not_exist(self):
        log = run_record.SessionLog(self.root / "brand" / "new")
        self.addCleanup(log.close)
        self.assertTrue(log.path.parent.is_dir())


class ScanIndexTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_empty_index_reads_as_no_scans(self):
        self.assertEqual(run_record.read_index(self.root), [])

    def test_header_is_written_once(self):
        run_record.append_index_row(self.root, {"run_id": "a"})
        run_record.append_index_row(self.root, {"run_id": "b"})
        lines = (self.root / run_record.INDEX_FILENAME).read_text().strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].split(","), run_record.INDEX_COLUMNS)

    def test_missing_values_are_written_empty_not_as_none(self):
        run_record.append_index_row(self.root, {"run_id": "a"})
        row = run_record.read_index(self.root)[0]
        self.assertEqual(row["run_id"], "a")
        self.assertEqual(row["water_temp_c"], "")

    def test_unknown_keys_are_ignored(self):
        # Adding a column later must not break reading older files, and an
        # unexpected key must not shift every other column along.
        run_record.append_index_row(self.root, {"run_id": "a", "not_a_column": "x"})
        row = run_record.read_index(self.root)[0]
        self.assertEqual(row["run_id"], "a")
        self.assertNotIn("not_a_column", row)

    def test_floats_are_written_without_noise_digits(self):
        run_record.append_index_row(self.root, {"saline_g_per_l": 0.1 + 0.2})
        self.assertEqual(run_record.read_index(self.root)[0]["saline_g_per_l"], "0.3")

    def test_rows_read_back_oldest_first(self):
        for name in ("a", "b", "c"):
            run_record.append_index_row(self.root, {"run_id": name})
        self.assertEqual(
            [r["run_id"] for r in run_record.read_index(self.root)], ["a", "b", "c"]
        )


class IndexRowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_row_is_built_from_the_run_itself(self):
        conditions = Conditions(
            medium="saline tank",
            saline_g_per_l=2.5,
            grounding="floating",
            target_description="steel rod at E3",
        )
        recorder = create_run(
            self.root,
            "step-4",
            conditions=conditions,
            settings={"pattern": "adjacent", "dac": 100, "samples": 16},
            when=datetime(2026, 9, 16, 14, 40, 22),
        )
        self.addCleanup(recorder.close)
        recorder.write_frame(make_frame())
        row = recorder.index_row(outcome="complete")
        self.assertEqual(row["run_id"], "20260916-144022-step-4")
        self.assertEqual(row["saline_g_per_l"], 2.5)
        self.assertEqual(row["grounding"], "floating")
        self.assertEqual(row["target"], "steel rod at E3")
        self.assertEqual(row["pattern"], "adjacent")
        self.assertEqual(row["samples"], 16)
        self.assertEqual(row["frames"], 1)
        self.assertEqual(row["outcome"], "complete")

    def test_frames_reflects_what_was_actually_written(self):
        recorder = create_run(self.root, "partial")
        self.addCleanup(recorder.close)
        for _ in range(3):
            recorder.write_frame(make_frame())
        self.assertEqual(recorder.index_row()["frames"], 3)

    def test_metrics_override_nothing_by_accident(self):
        recorder = create_run(self.root, "m")
        self.addCleanup(recorder.close)
        row = recorder.index_row(reciprocity_median_percent=57.5)
        self.assertEqual(row["reciprocity_median_percent"], 57.5)
        self.assertEqual(row["label"], "m")


class SpecimenGeometryTests(unittest.TestCase):
    """Geometry is recorded because reconstruction assumes it (ADR-0033)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_geometry_defaults_to_not_measured_without_complaint(self):
        # A tank run has no circumference and is not thereby incomplete.
        conditions = Conditions(medium="saline tank", grounding="floating")
        self.assertIsNone(conditions.circumference_mm)
        self.assertIsNone(conditions.thickness_mm)
        self.assertEqual(conditions.specimen_id, "")
        self.assertEqual(conditions.validate(), [])

    def test_negative_geometry_is_reported(self):
        problems = Conditions(
            medium="disc", grounding="floating", circumference_mm=-1.0
        ).validate()
        self.assertIn("circumference_mm is negative", problems)

    def test_minor_larger_than_major_is_reported(self):
        # Swapped calipers are the likeliest way this goes wrong at the bench.
        problems = Conditions(
            medium="disc",
            grounding="floating",
            major_diameter_mm=180.0,
            minor_diameter_mm=200.0,
        ).validate()
        self.assertIn("minor_diameter_mm is larger than major_diameter_mm", problems)

    def test_validate_never_raises_on_geometry(self):
        # ADR-0023: a capture already taken must always be recordable.
        conditions = Conditions(
            medium="disc",
            grounding="floating",
            circumference_mm=-5.0,
            minor_diameter_mm=999.0,
            major_diameter_mm=1.0,
        )
        self.assertIsInstance(conditions.validate(), list)

    def test_geometry_reaches_the_index_row(self):
        conditions = Conditions(
            medium="coconut disc",
            grounding="floating",
            specimen_id="disc-03",
            circumference_mm=540.0,
            thickness_mm=65.0,
            major_diameter_mm=180.0,
            minor_diameter_mm=168.0,
        )
        recorder = create_run(self.root, "disc 3 intact", conditions=conditions)
        recorder.close()
        row = recorder.index_row()
        self.assertEqual(row["specimen_id"], "disc-03")
        self.assertAlmostEqual(row["circumference_mm"], 540.0)
        self.assertAlmostEqual(row["thickness_mm"], 65.0)
        self.assertAlmostEqual(row["major_diameter_mm"], 180.0)
        self.assertAlmostEqual(row["minor_diameter_mm"], 168.0)

    def test_geometry_columns_are_appended_not_reordered(self):
        # INDEX_COLUMNS is append-only: renaming or reordering breaks every
        # row already written to an existing index.csv.
        self.assertEqual(run_record.INDEX_COLUMNS[:4],
                         ["run_id", "captured_at", "label", "medium"])
        for column in ("specimen_id", "circumference_mm", "thickness_mm",
                       "major_diameter_mm", "minor_diameter_mm"):
            self.assertIn(column, run_record.INDEX_COLUMNS)

    def test_nail_arcs_survive_in_extra_and_reach_the_sheet(self):
        conditions = Conditions(
            medium="coconut disc",
            grounding="floating",
            specimen_id="disc-03",
            extra={"nail_arc_mm": [0.0, 45.0, 90.0]},
        )
        recorder = create_run(self.root, "disc 3 intact", conditions=conditions)
        recorder.close()
        payload = json.loads((recorder.path / "conditions.json").read_text())
        self.assertEqual(
            payload["conditions"]["extra"]["nail_arc_mm"], [0.0, 45.0, 90.0]
        )
        sheet = (recorder.path / "conditions.md").read_text()
        self.assertIn("nail_arc_mm", sheet)
        self.assertIn("disc-03", sheet)


class RunDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_list_runs_is_empty_before_any_run(self):
        self.assertEqual(list_runs(self.root), [])

    def test_runs_are_listed_in_timestamp_order(self):
        for minute, label in ((0, "first"), (5, "second")):
            create_run(
                self.root, label, when=datetime(2026, 9, 11, 20, minute, 0)
            ).close()
        self.assertEqual(
            [p.name for p in list_runs(self.root)],
            ["20260911-200000-first", "20260911-200500-second"],
        )

    def test_load_run_round_trips_conditions(self):
        conditions = Conditions(
            medium="saline tank",
            saline_g_per_l=1.25,
            grounding="grounded",
            electrode_map="E1 = marked nail, clockwise from above",
        )
        recorder = create_run(self.root, "rt", conditions=conditions)
        recorder.close()
        loaded = load_run(recorder.path)
        self.assertEqual(loaded["conditions"], conditions)
        self.assertEqual(loaded["run_id"], recorder.run_id)


if __name__ == "__main__":
    unittest.main()


class NamingProblemsTests(unittest.TestCase):
    """Identity is refused rather than warned about (ADR-0037)."""

    def _conditions(self, medium="cut disc", specimen="disc-03"):
        return run_record.Conditions(medium=medium, specimen_id=specimen)

    def test_a_properly_named_run_passes(self):
        self.assertEqual(
            run_record.naming_problems(self._conditions(), "disc-03-intact"), []
        )

    def test_multi_word_specimens_pass(self):
        conditions = self._conditions(medium="standing tree", specimen="coconut-tree-1")
        self.assertEqual(
            run_record.naming_problems(conditions, "coconut-tree-1 dry 620"), []
        )

    def test_the_label_is_compared_after_slugifying(self):
        # The folder name is what survives, so that is what has to be right.
        self.assertEqual(
            run_record.naming_problems(self._conditions(), "Disc-03 Hole E7"), []
        )

    def test_an_unknown_medium_is_refused(self):
        for medium in ("unknown", "", "coconut trunk"):
            problems = run_record.naming_problems(
                self._conditions(medium=medium), "disc-03-intact"
            )
            self.assertTrue(any("medium must be one of" in p for p in problems), medium)

    def test_an_empty_specimen_is_refused(self):
        problems = run_record.naming_problems(self._conditions(specimen=""), "x")
        self.assertTrue(any("specimen ID is empty" in p for p in problems))

    def test_malformed_specimens_are_refused(self):
        for specimen in ("disc", "Disc-03", "disc_03", "disc 03", "03", "disc-03-"):
            problems = run_record.naming_problems(
                self._conditions(specimen=specimen), f"{specimen}-intact"
            )
            self.assertTrue(
                any("must be lowercase" in p for p in problems), specimen
            )

    def test_a_label_without_the_specimen_is_refused(self):
        problems = run_record.naming_problems(
            self._conditions(), "coconut-620-dry-32-samples"
        )
        self.assertTrue(any("label must start" in p for p in problems))

    def test_a_label_that_is_only_the_specimen_is_refused(self):
        # It has to say what the run is, not just which disc.
        problems = run_record.naming_problems(self._conditions(), "disc-03")
        self.assertTrue(any("label must start" in p for p in problems))

    def test_a_prefix_collision_is_refused(self):
        # disc-03 must not accept a label for disc-030.
        problems = run_record.naming_problems(self._conditions(), "disc-030-intact")
        self.assertTrue(any("label must start" in p for p in problems))


class BaselineSpecimenTests(unittest.TestCase):
    def test_the_same_specimen_is_allowed(self):
        self.assertIsNone(run_record.baseline_specimen_problem("disc-03", "disc-03"))

    def test_a_different_specimen_is_refused(self):
        problem = run_record.baseline_specimen_problem("disc-03", "disc-04")
        self.assertIn("disc-03", problem)
        self.assertIn("Clear the baseline", problem)

    def test_an_unrecorded_baseline_is_refused(self):
        problem = run_record.baseline_specimen_problem("", "disc-03")
        self.assertIn("unrecorded", problem)


class RunLabelTests(unittest.TestCase):
    """The label is generated from specimen and target (ADR-0040)."""

    def _label(self, **fields):
        return run_record.run_label(run_record.Conditions(**fields))

    def test_an_intact_disc(self):
        self.assertEqual(
            self._label(medium="cut disc", specimen_id="disc-03"), "disc-03-intact"
        )

    def test_a_target_describes_the_run(self):
        self.assertEqual(
            self._label(
                medium="cut disc", specimen_id="disc-03", target_description="Hole at E7"
            ),
            "disc-03-hole-at-e7",
        )

    def test_anything_but_a_disc_without_a_target_is_a_baseline(self):
        # "intact" would be a claim about a standing tree nobody can make.
        self.assertEqual(
            self._label(medium="standing tree", specimen_id="coconut-tree-1"),
            "coconut-tree-1-baseline",
        )

    def test_no_specimen_no_label(self):
        self.assertEqual(self._label(medium="cut disc"), "")

    def test_a_generated_label_always_passes_the_naming_rule(self):
        conditions = run_record.Conditions(
            medium="cut disc", specimen_id="disc-03", target_description="centre hole"
        )
        self.assertEqual(
            run_record.naming_problems(conditions, run_record.run_label(conditions)), []
        )
