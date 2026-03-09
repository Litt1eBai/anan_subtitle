import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.bootstrap import prompt_model_profile_on_first_run


class PromptModelProfileTests(unittest.TestCase):
    def test_prompt_skips_when_stdin_is_missing(self) -> None:
        args = SimpleNamespace(
            model_profile_prompt_on_first_run=True,
            model_profile_prompted=False,
        )

        with patch("app.bootstrap.sys.stdin", None), patch("builtins.input") as mock_input:
            prompt_model_profile_on_first_run(args, Path("config/app.yaml"))

        mock_input.assert_not_called()


if __name__ == "__main__":
    unittest.main()
