import argparse
import logging
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.runtime_env import apply_runtime_environment, build_model_cache_environment, configure_logging


class RuntimeEnvTests(unittest.TestCase):
    def test_build_model_cache_environment_uses_expected_subdirs(self) -> None:
        env = build_model_cache_environment(Path("C:/temp/data"))

        self.assertRegex(env["MODELSCOPE_CACHE"], r"modelscope[\\/]hub$")
        self.assertRegex(env["HUGGINGFACE_HUB_CACHE"], r"huggingface[\\/]hub$")
        self.assertTrue(env["TORCH_HOME"].endswith("torch"))

    def test_apply_runtime_environment_sets_paths_on_args(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            args = argparse.Namespace(data_dir=str((tmpdir / "data").resolve()), log_dir=str((tmpdir / "logs").resolve()))
            apply_runtime_environment(args)
            self.assertTrue(Path(args.data_dir).exists())
            self.assertTrue(Path(args.log_dir).exists())
            self.assertIn("modelscope", args.modelscope_cache_dir)
            self.assertTrue(args.log_file.endswith("desktop_subtitle.log"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_configure_logging_creates_log_file(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            log_file = configure_logging((tmpdir / "logs").resolve())
            logging.getLogger("desktop_subtitle").info("hello")
            self.assertTrue(log_file.exists())
            self.assertIn("hello", log_file.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
