import unittest
from pathlib import Path
from unittest.mock import patch

from presentation.qt.settings_window_actions import (
    build_overlay_config_updates,
    build_settings_config_updates,
    run_model_download_requests,
    write_settings_config,
)
from presentation.qt.settings_window_models import build_model_selection_state


class BuildOverlayConfigUpdatesTests(unittest.TestCase):
    def test_filters_to_overlay_persist_keys(self) -> None:
        updates = build_overlay_config_updates(
            {
                "x": 10,
                "y": 20,
                "font_size": 32,
                "ignored": "value",
            }
        )

        self.assertEqual(updates, {"x": 10, "y": 20, "font_size": 32})


class BuildSettingsConfigUpdatesTests(unittest.TestCase):
    def test_combines_overlay_and_model_updates(self) -> None:
        selection = build_model_selection_state(
            model="asr",
            detector_model="detector",
            vad_model="vad",
            punc_model="punc",
            disable_vad_model=False,
            disable_punc_model=True,
        )

        updates = build_settings_config_updates(
            {"x": 1, "height": 2, "ignored": 3},
            model_profile="hybrid",
            model_download_on_startup=True,
            selection=selection,
        )

        self.assertEqual(updates["x"], 1)
        self.assertEqual(updates["height"], 2)
        self.assertEqual(updates["model_profile"], "hybrid")
        self.assertTrue(updates["model_download_on_startup"])
        self.assertEqual(updates["model"], "asr")
        self.assertEqual(updates["detector_model"], "detector")
        self.assertNotIn("ignored", updates)


class WriteSettingsConfigTests(unittest.TestCase):
    def test_delegates_merged_updates_to_runtime_writer(self) -> None:
        selection = build_model_selection_state(
            model="asr",
            detector_model="detector",
            vad_model="vad",
            punc_model="punc",
            disable_vad_model=False,
            disable_punc_model=False,
        )
        config_path = Path("config/app.yaml")

        with patch("presentation.qt.settings_window_actions.write_config_values") as write_mock:
            write_settings_config(
                config_path,
                {"x": 1, "font_size": 30, "ignored": 99},
                model_profile="custom",
                model_download_on_startup=False,
                selection=selection,
            )

        write_mock.assert_called_once_with(
            config_path,
            {
                "x": 1,
                "font_size": 30,
                "model_profile": "custom",
                "model_download_on_startup": False,
                "model_profile_prompted": True,
                "model": "asr",
                "detector_model": "detector",
                "vad_model": "vad",
                "punc_model": "punc",
                "disable_vad_model": False,
                "disable_punc_model": False,
            },
        )


class RunModelDownloadRequestsTests(unittest.TestCase):
    def test_uses_injected_loader_and_returns_elapsed(self) -> None:
        calls: list[dict[str, str]] = []

        def fake_loader(**kwargs: str) -> None:
            calls.append(kwargs)

        perf_values = iter([10.0, 12.5])

        elapsed = run_model_download_requests(
            [{"model": "a"}, {"model": "b"}],
            model_loader=fake_loader,
            perf_counter=lambda: next(perf_values),
        )

        self.assertEqual(calls, [{"model": "a"}, {"model": "b"}])
        self.assertEqual(elapsed, 2.5)
