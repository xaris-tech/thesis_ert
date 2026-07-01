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


if __name__ == "__main__":
    unittest.main()
