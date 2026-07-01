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

        figure, map_ax, vector_ax = build_reconstruction_figure()

        self.assertEqual(len(figure.axes), 2)
        self.assertIs(figure.axes[0], map_ax)
        self.assertIs(figure.axes[1], vector_ax)
        self.assertEqual(map_ax.get_title(), "Average 2D map")
        self.assertEqual(vector_ax.get_title(), "Average reconstruction vector")

    def test_average_reconstruction_vector_averages_frames(self):
        import numpy as np
        from tree_ert.ui import average_reconstruction_vector

        average = average_reconstruction_vector([
            np.array([1.0, 3.0, 5.0]),
            np.array([3.0, 5.0, 7.0]),
        ])

        self.assertTrue(np.allclose(average, np.array([2.0, 4.0, 6.0])))


if __name__ == "__main__":
    unittest.main()
