import sys
import types
import unittest
from unittest.mock import patch


class TestTreeErtUiEntrypoint(unittest.TestCase):
    def test_entrypoint_parses_demo_and_port(self):
        import tree_ert_app

        with patch.object(sys, "argv", ["tree_ert_app.py", "--demo", "--port", "COM7"]):
            args = tree_ert_app.parse_args()

        self.assertTrue(args.demo)
        self.assertEqual(args.port, "COM7")

    def test_main_lazily_imports_and_dispatches_to_run_app(self):
        import tree_ert_app

        calls = []
        fake_ui = types.SimpleNamespace(
            run_app=lambda **kwargs: calls.append(kwargs),
        )

        with patch.dict(sys.modules, {"tree_ert.ui": fake_ui}):
            with patch.object(sys, "argv", ["tree_ert_app.py", "--demo", "--port", "COM7"]):
                tree_ert_app.main()

        self.assertEqual(calls, [{"demo": True, "port": "COM7"}])

    def test_reconstruction_figure_has_map_and_vector_axes(self):
        from tree_ert.ui import build_reconstruction_figure

        figure, map_ax, vector_ax, scan_axes = build_reconstruction_figure()

        self.assertEqual(len(figure.axes), 6)
        self.assertIs(figure.axes[0], map_ax)
        self.assertIs(figure.axes[1], vector_ax)
        self.assertEqual(tuple(figure.axes[2:]), scan_axes)
        self.assertEqual(map_ax.get_title(), "Average 2D map")
        self.assertEqual(vector_ax.get_title(), "Average reconstruction vector")
        self.assertEqual(scan_axes[0].get_title(), "Scan 1")

    def test_average_reconstruction_vector_averages_frames(self):
        import numpy as np
        from tree_ert.ui import average_reconstruction_vector

        average = average_reconstruction_vector([
            np.array([1.0, 3.0, 5.0]),
            np.array([3.0, 5.0, 7.0]),
        ])

        self.assertTrue(np.allclose(average, np.array([2.0, 4.0, 6.0])))

    def test_status_is_embedded_in_reconstruction_tab(self):
        from tree_ert.ui import debug_tab_titles

        self.assertEqual(debug_tab_titles(), ("Reconstruction", "Health", "Serial", "Files"))
        self.assertNotIn("Status", debug_tab_titles())

    def test_preview_indices_spread_across_reconstructions(self):
        from tree_ert.ui import preview_scan_indices

        self.assertEqual(preview_scan_indices(0), ())
        self.assertEqual(preview_scan_indices(3), (0, 1, 2))
        self.assertEqual(preview_scan_indices(20), (0, 6, 13, 19))


if __name__ == "__main__":
    unittest.main()
