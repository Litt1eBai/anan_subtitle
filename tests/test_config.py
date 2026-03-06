import argparse
import shutil
import unittest
import uuid
from pathlib import Path

from desktop_subtitle.config import (
    apply_model_profile_to_args,
    apply_model_profile_to_settings,
    ensure_valid_image,
    normalize_config,
    parse_chunk_size,
)
from desktop_subtitle.constants import MODEL_PROFILE_OFFLINE, MODEL_PROFILE_REALTIME


class ParseChunkSizeTests(unittest.TestCase):
    def test_parse_chunk_size_from_string(self) -> None:
        self.assertEqual(parse_chunk_size("0,10,5"), [0, 10, 5])

    def test_parse_chunk_size_requires_three_values(self) -> None:
        with self.assertRaises(ValueError):
            parse_chunk_size("0,10")


class NormalizeConfigTests(unittest.TestCase):
    def test_normalize_config_coerces_types(self) -> None:
        normalized = normalize_config(
            {
                "x": "1",
                "opacity": "0.8",
                "stay_on_top": "true",
                "chunk_size": "0,10,5",
                "model_profile": "offline",
            }
        )
        self.assertEqual(normalized["x"], 1)
        self.assertEqual(normalized["opacity"], 0.8)
        self.assertIs(normalized["stay_on_top"], True)
        self.assertEqual(normalized["chunk_size"], [0, 10, 5])
        self.assertEqual(normalized["model_profile"], MODEL_PROFILE_OFFLINE)

    def test_normalize_config_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            normalize_config({"unknown_key": 1})


class ModelProfileTests(unittest.TestCase):
    def test_apply_model_profile_to_settings_overrides_preset_fields(self) -> None:
        settings = {
            "model_profile": MODEL_PROFILE_OFFLINE,
            "model": "custom-model",
            "detector_model": "custom-detector",
            "vad_model": "custom-vad",
            "punc_model": "custom-punc",
            "disable_vad_model": True,
            "disable_punc_model": True,
        }
        updated = apply_model_profile_to_settings(settings)
        self.assertEqual(updated["model_profile"], MODEL_PROFILE_OFFLINE)
        self.assertEqual(updated["model"], "paraformer-zh")
        self.assertEqual(updated["detector_model"], "paraformer-zh-streaming")
        self.assertIs(updated["disable_vad_model"], False)
        self.assertIs(updated["disable_punc_model"], False)

    def test_apply_model_profile_to_args_updates_namespace(self) -> None:
        args = argparse.Namespace(
            model_profile=MODEL_PROFILE_REALTIME,
            model="old",
            detector_model="old-detector",
            vad_model="old-vad",
            punc_model="old-punc",
            disable_vad_model=False,
            disable_punc_model=False,
        )
        apply_model_profile_to_args(args)
        self.assertEqual(args.model, "paraformer-zh-streaming")
        self.assertEqual(args.detector_model, "paraformer-zh-streaming")
        self.assertIs(args.disable_vad_model, True)
        self.assertIs(args.disable_punc_model, True)


class EnsureValidImageTests(unittest.TestCase):
    def test_ensure_valid_image_finds_relative_path_next_to_config(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            config_dir = tmpdir / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            image_path = config_dir / "base.png"
            image_path.write_bytes(b"png")
            config_path = config_dir / "app.yaml"
            config_path.write_text("{}", encoding="utf-8")

            resolved = ensure_valid_image("base.png", config_path)

            self.assertEqual(resolved, str(image_path.resolve()))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
