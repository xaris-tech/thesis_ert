"""Intact-disc survey arithmetic (ADR-0035, ADR-0038), on synthetic recorded runs."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import run_record
from tree_ert import survey
from tree_ert.reconstruction import SettingsMismatch

SETTINGS = {
    "pattern": "adjacent",
    "current_range": "high",
    "dac": 620,
    "settle_ms": 30,
    "samples": 32,
    "electrode_offset": 0,
    "electrode_reversed": False,
}


def base_vector() -> np.ndarray:
    """A plausible disc: a uniform disc's response scaled to ~10 ohm."""
    return np.asarray(survey.homogeneous_response("adjacent")) * 0.01


def perturbed(seed: int, size: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return base_vector() * (1.0 + size * rng.standard_normal(108))


class RunWriter:
    """Writes runs in the exact on-disk shape RunRecorder produces."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs = root / run_record.RUNS_DIRNAME
        self.runs.mkdir(parents=True)

    def write(
        self,
        run_id: str,
        vector: np.ndarray,
        specimen: str = "disc-01",
        target: str = "",
        medium: str = "cut disc",
        created_at: str = "2026-09-29T15:00:00",
        frames: int = 3,
        noise: float = 0.0,
        offset_mv: float = 7.0,
        dead_cells: tuple[int, ...] = (),
        settings: dict | None = None,
    ) -> Path:
        run_dir = self.runs / run_id
        run_dir.mkdir()
        (run_dir / "conditions.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "created_at": created_at,
                    "conditions": {
                        "medium": medium,
                        "specimen_id": specimen,
                        "target_description": target,
                    },
                    "settings": settings or SETTINGS,
                }
            ),
            encoding="utf-8",
        )
        protocol_cells = survey.cell_labels("adjacent")
        rng = np.random.default_rng(len(run_id))
        with (run_dir / "frames.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(run_record.FRAME_CSV_COLUMNS)
            for frame in range(frames):
                record = 0
                for cell, label in enumerate(protocol_cells):
                    drive, sense = label.split("|")
                    i_plus, i_minus = drive.split("-")
                    v_plus, v_minus = sense.split("-")
                    value = vector[cell] * (1.0 + noise * rng.standard_normal())
                    current = 350.0
                    quality = "I_LOW" if cell in dead_cells else "OK"
                    # frame_to_vector returns -(V_fwd/I - V_rev/I)/2, so these
                    # voltages round-trip to `value`; the offset cancels.
                    for polarity, pp, pm, volts in (
                        ("FWD", i_plus, i_minus, -value * current + offset_mv),
                        ("REV", i_minus, i_plus, value * current + offset_mv),
                    ):
                        writer.writerow(
                            [frame, frame + 1, "adjacent", 620, 30, 32, record,
                             polarity, pp, pm, v_plus, v_minus, volts, current, quality]
                        )
                        record += 1
        return run_dir


class SurveyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.writer = RunWriter(self.root)


class LoadingTests(SurveyTestCase):
    def test_a_recorded_run_round_trips_to_its_transfer_resistances(self):
        vector = base_vector()
        run_dir = self.writer.write("r1", vector)
        scan = survey.load_scan(run_dir, "disc-01", survey.STATE_INTACT)
        np.testing.assert_allclose(scan.vector, vector, rtol=1e-9)
        self.assertEqual(scan.frames, 3)
        self.assertEqual(scan.bad_cells, 0)

    def test_a_cell_bad_in_every_frame_is_missing_not_filled(self):
        run_dir = self.writer.write("r1", base_vector(), dead_cells=(4,))
        scan = survey.load_scan(run_dir, "disc-01", survey.STATE_INTACT)
        self.assertTrue(np.isnan(scan.vector[4]))
        self.assertEqual(scan.bad_cells, 1)

    def test_an_unknown_state_is_refused(self):
        run_dir = self.writer.write("r1", base_vector())
        with self.assertRaises(ValueError):
            survey.load_scan(run_dir, "disc-01", "drilled")


class ArithmeticTests(unittest.TestCase):
    def test_normalising_cancels_resistivity_and_size(self):
        # A wetter or smaller disc scales every cell; the comparison must not see it.
        vector = base_vector()
        self.assertAlmostEqual(
            survey.distance(survey.normalise(vector), survey.normalise(vector * 7.3)), 0.0
        )

    def test_distance_skips_cells_either_side_is_missing(self):
        a = np.array([1.0, 1.0, np.nan])
        b = np.array([1.0, 1.0, 5.0])
        self.assertEqual(survey.distance(a, b), 0.0)

    def test_a_uniform_disc_has_no_contrast(self):
        geometry = np.asarray(survey.homogeneous_response("adjacent"))
        result = survey.contrast(geometry * 0.01, geometry)
        self.assertAlmostEqual(result.ratio, 1.0)
        self.assertAlmostEqual(result.spread, 0.0)

    def test_contrast_ignores_how_big_the_disc_is(self):
        geometry = np.asarray(survey.homogeneous_response("adjacent"))
        vector = perturbed(1, 0.1)
        self.assertAlmostEqual(
            survey.contrast(vector, geometry).ratio,
            survey.contrast(vector * 4.0, geometry).ratio,
        )


class AnalysisTests(SurveyTestCase):
    def _cohort(self):
        scans = []
        for index, specimen in enumerate(("disc-01", "disc-02", "disc-03")):
            vector = perturbed(index, 0.05)
            for repeat in range(2):
                run_dir = self.writer.write(
                    f"{specimen}-intact-{repeat}", vector, specimen=specimen, noise=0.002
                )
                scans.append(survey.load_scan(run_dir, specimen, survey.STATE_INTACT))
        drilled = perturbed(0, 0.05) * (1.0 + 0.5 * (np.arange(108) % 9 == 0))
        run_dir = self.writer.write(
            "disc-01-hole", drilled, specimen="disc-01", created_at="2026-09-29T15:20:00"
        )
        scans.append(survey.load_scan(run_dir, "disc-01", survey.STATE_DEFECT))
        return scans

    def test_the_three_spreads_order_as_the_physics_says(self):
        report = survey.analyse(self._cohort())
        self.assertLess(report.s_noise, report.s_between)
        self.assertLess(report.s_between, report.s_defect)
        self.assertEqual(len(report.between_pairs), 3)
        self.assertEqual(len(report.noise_pairs), 3)

    def test_the_minutes_since_the_intact_scan_are_reported(self):
        report = survey.analyse(self._cohort())
        (_, _, _, minutes), = report.defects
        self.assertAlmostEqual(minutes, 20.0)

    def test_per_electrode_shares_sum_to_the_whole(self):
        report = survey.analyse(self._cohort())
        self.assertAlmostEqual(sum(report.electrode_share.values()), 100.0, places=6)
        self.assertEqual(set(report.electrode_share), {f"E{i}" for i in range(1, 13)})

    def test_one_specimen_gives_no_between_spread_and_says_so(self):
        run_dir = self.writer.write("a", base_vector())
        scan = survey.load_scan(run_dir, "disc-01", survey.STATE_INTACT)
        report = survey.analyse([scan])
        self.assertIsNone(report.s_between)
        self.assertTrue(any("at least two specimens" in n for n in report.notes))
        self.assertIn("no verdict", survey.verdict(report))

    def test_a_defect_without_an_intact_scan_is_noted_not_compared(self):
        run_dir = self.writer.write("hole", base_vector())
        scan = survey.load_scan(run_dir, "disc-09", survey.STATE_DEFECT)
        report = survey.analyse([scan])
        self.assertEqual(report.defects, [])
        self.assertTrue(any("no intact scan" in n for n in report.notes))

    def test_mixed_settings_are_refused(self):
        # Normalisation does not cancel a DAC change; nothing else would catch it.
        a = survey.load_scan(self.writer.write("a", base_vector()), "disc-01", "intact")
        b = survey.load_scan(
            self.writer.write("b", base_vector(), settings={**SETTINGS, "dac": 500}),
            "disc-02",
            "intact",
        )
        with self.assertRaises(SettingsMismatch) as caught:
            survey.analyse([a, b])
        self.assertIn("b dac", str(caught.exception))

    def test_the_report_formats(self):
        text = survey.format_report(survey.analyse(self._cohort()))
        self.assertIn("S_noise", text)
        self.assertIn("S_between", text)
        self.assertIn("S_defect", text)


class VerdictTests(unittest.TestCase):
    def _report(self, s_between: float, s_defect: float) -> survey.SurveyReport:
        return survey.SurveyReport(
            profile={}, scans=[], excluded=[], contrast={}, noise_pairs=[],
            between_pairs=[("a", "b", s_between)], centre_distance={},
            defects=[("r", "a", s_defect, None)], cell_share=[], electrode_share={},
        )

    def test_the_bands_committed_in_adr_0035(self):
        self.assertIn("LICENSED", survey.verdict(self._report(1.0, 3.0)))
        self.assertIn("MARGINAL", survey.verdict(self._report(1.0, 2.0)))
        self.assertIn("BELOW 1.5", survey.verdict(self._report(1.0, 1.4)))


class ManifestTests(SurveyTestCase):
    def test_a_manifest_reads_with_comments_and_notes(self):
        path = self.root / "m.csv"
        path.write_text(
            "# comment\nrun_id,specimen_id,state,note\n"
            "r1,disc-01,intact,\nr2,disc-01,Excluded,E8 lost\n",
            encoding="utf-8",
        )
        rows = survey.read_manifest(path)
        self.assertEqual([r.state for r in rows], ["intact", "excluded"])
        self.assertEqual(rows[1].note, "E8 lost")

    def test_an_unknown_state_in_a_manifest_is_refused(self):
        path = self.root / "m.csv"
        path.write_text("run_id,specimen_id,state\nr1,disc-01,drilled\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            survey.read_manifest(path)

    def test_runs_name_themselves_from_their_conditions(self):
        self.writer.write("a", base_vector(), specimen="disc-01")
        self.writer.write("b", base_vector(), specimen="disc-01", target="hole at E7")
        self.writer.write("c", base_vector(), specimen="")  # before ADR-0037
        self.writer.write("d", base_vector(), specimen="coconut-tree-1", medium="standing tree")
        rows = survey.manifest_from_conditions(self.root, medium="cut disc")
        self.assertEqual(
            [(r.run_id, r.state) for r in rows],
            [("a", survey.STATE_INTACT), ("b", survey.STATE_DEFECT)],
        )

    def test_excluded_runs_are_listed_but_not_loaded(self):
        self.writer.write("a", base_vector())
        manifest = [
            survey.ManifestRow("a", "disc-01", "intact"),
            survey.ManifestRow("missing", "disc-01", "excluded", "never recorded"),
        ]
        report = survey.run_survey(self.root, manifest)
        self.assertEqual(report.excluded, [("missing", "disc-01", "never recorded")])


class CliTests(SurveyTestCase):
    def test_the_cli_writes_text_and_json(self):
        import contextlib
        import io

        import disc_survey

        self.writer.write("a", base_vector())
        self.writer.write("b", base_vector() * 1.01)
        manifest = self.root / "m.csv"
        manifest.write_text(
            "run_id,specimen_id,state\na,disc-01,intact\nb,disc-01,intact\n",
            encoding="utf-8",
        )
        out = self.root / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            code = disc_survey.main(
                ["--manifest", str(manifest), "--scans-root", str(self.root), "--out", str(out)]
            )
        self.assertEqual(code, 0)
        payload = json.loads((out / "survey.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(payload["s_noise_percent"], 0.0, places=6)
        self.assertTrue((out / "survey.txt").is_file())


if __name__ == "__main__":
    unittest.main()
