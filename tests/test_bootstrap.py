import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.bootstrap import prompt_model_profile_on_first_run


class PromptModelProfileTests(unittest.TestCase):
    def test_prompt_uses_gui_when_stdin_is_missing(self) -> None:
        args = SimpleNamespace(
            model_profile_prompt_on_first_run=True,
            model_profile_prompted=False,
        )

        with patch("app.bootstrap.sys.stdin", None), patch("app.bootstrap.prompt_model_profile_on_first_run_gui", return_value=True) as mock_gui, patch("builtins.input") as mock_input:
            result = prompt_model_profile_on_first_run(args, Path("config/app.yaml"))

        self.assertTrue(result)
        mock_gui.assert_called_once_with(args, Path("config/app.yaml"))
        mock_input.assert_not_called()

    def test_prompt_returns_false_when_gui_setup_is_cancelled(self) -> None:
        args = SimpleNamespace(
            model_profile_prompt_on_first_run=True,
            model_profile_prompted=False,
        )

        with patch("app.bootstrap.sys.stdin", None), patch("app.bootstrap.prompt_model_profile_on_first_run_gui", return_value=False):
            result = prompt_model_profile_on_first_run(args, Path("config/app.yaml"))

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
