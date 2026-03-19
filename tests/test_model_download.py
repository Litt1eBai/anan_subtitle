import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from core.model_download import (
    cleanup_incomplete_model_cache,
    ensure_model_download_ready,
    is_usable_downloaded_model_dir,
)


class ModelDownloadTests(unittest.TestCase):
    def test_is_usable_downloaded_model_dir_requires_model_config(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            model_dir = tmpdir / "model"
            model_dir.mkdir(parents=True, exist_ok=True)
            self.assertFalse(is_usable_downloaded_model_dir(model_dir))
            (model_dir / "config.yaml").write_text("model: ParaformerStreaming\n", encoding="utf-8")
            self.assertTrue(is_usable_downloaded_model_dir(model_dir))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cleanup_incomplete_model_cache_removes_model_temp_and_lock(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            cache_root = tmpdir / "modelscope" / "hub"
            model_dir = cache_root / "models" / "iic" / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
            temp_dir = cache_root / "models" / "._____temp" / "iic" / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
            lock_file = cache_root / ".lock" / "iic___speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
            model_dir.mkdir(parents=True, exist_ok=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            (model_dir / ".mdl").write_text("partial", encoding="utf-8")
            (temp_dir / "partial.tmp").write_text("partial", encoding="utf-8")
            lock_file.write_text("locked", encoding="utf-8")

            cleanup_incomplete_model_cache("paraformer-zh-streaming", cache_root)

            self.assertFalse(model_dir.exists())
            self.assertFalse(temp_dir.exists())
            self.assertFalse(lock_file.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ensure_model_download_ready_retries_after_cleanup(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            cache_root = tmpdir / "modelscope" / "hub"
            broken_dir = cache_root / "models" / "iic" / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
            broken_dir.mkdir(parents=True, exist_ok=True)
            (broken_dir / ".mdl").write_text("partial", encoding="utf-8")

            recovered_dir = tmpdir / "recovered"
            recovered_dir.mkdir(parents=True, exist_ok=True)
            (recovered_dir / "config.yaml").write_text("model: ParaformerStreaming\n", encoding="utf-8")

            calls = {"count": 0}

            def fake_downloader(**kwargs):
                calls["count"] += 1
                if calls["count"] == 1:
                    return {"model": kwargs["model"], "model_path": str(broken_dir)}
                return {"model": kwargs["model"], "model_path": str(recovered_dir)}

            result = ensure_model_download_ready(
                {"model": "paraformer-zh-streaming", "disable_update": True},
                downloader=fake_downloader,
                modelscope_cache_dir=cache_root,
            )

            self.assertEqual(calls["count"], 2)
            self.assertEqual(result["model_path"], str(recovered_dir))
            self.assertFalse(broken_dir.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ensure_model_download_ready_falls_back_to_hf(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            recovered_dir = tmpdir / "hf_model"
            recovered_dir.mkdir(parents=True, exist_ok=True)
            (recovered_dir / "config.yaml").write_text("model: ParaformerStreaming\n", encoding="utf-8")

            calls: list[str] = []

            def fake_download(download_kwargs, hub):
                calls.append(hub)
                if hub == "ms":
                    raise RuntimeError("modelscope unavailable")
                return {"model": download_kwargs["model"], "model_path": str(recovered_dir)}

            with patch('core.model_download._download_and_resolve_model', side_effect=fake_download):
                result = ensure_model_download_ready({"model": "paraformer-zh-streaming", "disable_update": True})

            self.assertEqual(calls, ["ms", "ms", "hf"])
            self.assertEqual(result["model_path"], str(recovered_dir))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ensure_model_download_ready_raises_when_model_dir_is_still_invalid(self) -> None:
        tmpdir = Path("tests") / ("tmp_" + uuid.uuid4().hex)
        try:
            cache_root = tmpdir / "modelscope" / "hub"
            broken_dir = cache_root / "models" / "iic" / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
            broken_dir.mkdir(parents=True, exist_ok=True)

            def fake_downloader(**kwargs):
                return {"model": kwargs["model"], "model_path": str(broken_dir)}

            with self.assertRaises(RuntimeError) as ctx:
                ensure_model_download_ready(
                    {"model": "paraformer-zh-streaming", "disable_update": True},
                    downloader=fake_downloader,
                    modelscope_cache_dir=cache_root,
                )

            self.assertIn("usable model directory", str(ctx.exception))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
