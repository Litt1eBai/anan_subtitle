import argparse
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

import core.settings as settings
from core.models import MODEL_PROFILE_OFFLINE, MODEL_PROFILE_REALTIME
from core.settings import (
    DEFAULT_CONFIG_TEMPLATE_PATH,
    STORAGE_LOCATION_APP,
    STORAGE_LOCATION_CUSTOM,
    STORAGE_LOCATION_USER,
    apply_model_profile_to_args,
    apply_model_profile_to_settings,
    apply_storage_paths_to_args,
    ensure_runtime_config_file,
    ensure_runtime_config_path,
    ensure_valid_image,
    get_app_install_dir,
    get_default_runtime_config_path,
    get_user_data_dir,
    is_template_config_path,
    normalize_config,
    parse_chunk_size,
    resolve_data_dir,
    resolve_log_dir,
    resolve_runtime_config_path,
    write_config_values,
)


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
        settings_dict = {
            "model_profile": MODEL_PROFILE_OFFLINE,
            "model": "custom-model",
            "detector_model": "custom-detector",
            "vad_model": "custom-vad",
            "punc_model": "custom-punc",
            "disable_vad_model": True,
            "disable_punc_model": True,
        }
        updated = apply_model_profile_to_settings(settings_dict)
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


class RuntimeConfigPathTests(unittest.TestCase):
    def test_template_path_is_detected(self) -> None:
        self.assertTrue(is_template_config_path(DEFAULT_CONFIG_TEMPLATE_PATH))

    def test_resolve_runtime_config_path_returns_absolute_path(self) -> None:
        self.assertTrue(resolve_runtime_config_path("config/app.yaml").is_absolute())

    def test_ensure_runtime_config_path_rejects_template(self) -> None:
        with self.assertRaises(ValueError):
            ensure_runtime_config_path(DEFAULT_CONFIG_TEMPLATE_PATH)

    def test_get_default_runtime_config_path_uses_user_directory_when_frozen(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            local_app_data = (tmpdir / "LocalAppData").resolve()
            with mock.patch.object(settings.sys, "frozen", True, create=True):
                with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}, clear=False):
                    runtime_path = get_default_runtime_config_path()
            expected = (local_app_data / settings.APP_DIR_NAME / settings.DEFAULT_CONFIG_DIR / settings.DEFAULT_CONFIG_FILENAME).resolve()
            self.assertEqual(runtime_path, expected)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ensure_runtime_config_file_creates_runtime_copy_from_template(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            bundle_dir = (tmpdir / "bundle" / settings.DEFAULT_CONFIG_DIR).resolve()
            bundle_dir.mkdir(parents=True, exist_ok=True)
            template_path = bundle_dir / settings.DEFAULT_CONFIG_TEMPLATE_FILENAME
            template_path.write_text("font_size: 42\n", encoding="utf-8")
            runtime_path = (tmpdir / "user" / "app.yaml").resolve()

            with mock.patch.object(settings.sys, "_MEIPASS", str(bundle_dir.parent), create=True):
                created_path = ensure_runtime_config_file(runtime_path)

            self.assertEqual(created_path, runtime_path)
            self.assertEqual(runtime_path.read_text(encoding="utf-8"), "font_size: 42\n")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


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

    def test_ensure_valid_image_finds_packaged_default_asset(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            config_dir = tmpdir / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "app.yaml"
            config_path.write_text("{}", encoding="utf-8")
            bundle_dir = (tmpdir / "bundle" / settings.DEFAULT_CONFIG_DIR).resolve()
            bundle_dir.mkdir(parents=True, exist_ok=True)
            image_path = bundle_dir / "base.png"
            image_path.write_bytes(b"png")

            with mock.patch.object(settings.sys, "_MEIPASS", str(bundle_dir.parent), create=True):
                resolved = ensure_valid_image("", config_path)

            self.assertEqual(resolved, str(image_path.resolve()))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class StoragePathTests(unittest.TestCase):
    def test_normalize_config_accepts_storage_locations(self) -> None:
        normalized = normalize_config(
            {
                "data_dir_location": "app",
                "data_dir_custom": "D:/cache",
                "log_dir_location": "custom",
                "log_dir_custom": "D:/logs",
            }
        )
        self.assertEqual(normalized["data_dir_location"], STORAGE_LOCATION_APP)
        self.assertEqual(normalized["log_dir_location"], STORAGE_LOCATION_CUSTOM)

    def test_resolve_storage_dirs_use_expected_roots(self) -> None:
        self.assertEqual(resolve_data_dir(STORAGE_LOCATION_USER), (get_user_data_dir() / "data").resolve())
        self.assertEqual(resolve_log_dir(STORAGE_LOCATION_APP), (get_app_install_dir() / "logs").resolve())
        self.assertEqual(
            resolve_data_dir(STORAGE_LOCATION_CUSTOM, "D:/custom"),
            Path("D:/custom").expanduser().resolve() / "data",
        )

    def test_apply_storage_paths_to_args_sets_resolved_dirs(self) -> None:
        args = argparse.Namespace(
            data_dir_location=STORAGE_LOCATION_CUSTOM,
            data_dir_custom="D:/cache",
            log_dir_location=STORAGE_LOCATION_USER,
            log_dir_custom="",
        )
        apply_storage_paths_to_args(args)
        self.assertEqual(args.data_dir, str((Path("D:/cache").expanduser().resolve() / "data").resolve()))
        self.assertEqual(args.log_dir, str((get_user_data_dir() / "logs").resolve()))


class WriteConfigValuesTests(unittest.TestCase):
    def test_write_config_values_rejects_template_path(self) -> None:
        with self.assertRaises(ValueError):
            write_config_values(Path(DEFAULT_CONFIG_TEMPLATE_PATH), {"x": 1})


if __name__ == "__main__":
    unittest.main()
