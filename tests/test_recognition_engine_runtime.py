import unittest
from unittest.mock import Mock, patch

import numpy as np

from recognition.engine_runtime import (
    OfflineLatencyTracker,
    emit_subtitle,
    timed_transcribe_offline,
    transcribe_offline,
    transcribe_streaming,
)


class EmitSubtitleTests(unittest.TestCase):
    def test_emits_converted_text_when_not_empty(self) -> None:
        signals = Mock()
        emit_subtitle(signals, "我来了")
        signals.subtitle.emit.assert_called_once_with("吾辈来了")

    def test_skips_empty_text(self) -> None:
        signals = Mock()
        emit_subtitle(signals, "   ")
        signals.subtitle.emit.assert_not_called()


class TranscribeOfflineTests(unittest.TestCase):
    def test_returns_empty_for_empty_audio(self) -> None:
        result = transcribe_offline(Mock(), np.empty(0, dtype=np.float32), samplerate=16000, error_signal=Mock())
        self.assertEqual(result, "")

    def test_falls_back_when_batch_size_not_supported(self) -> None:
        model = Mock()
        model.generate.side_effect = [TypeError("no batch"), {"text": "hello"}]

        result = transcribe_offline(model, np.array([1.0], dtype=np.float32), samplerate=16000, error_signal=Mock())

        self.assertEqual(result, "hello")
        self.assertEqual(model.generate.call_count, 2)

    def test_emits_error_on_failure(self) -> None:
        model = Mock()
        model.generate.side_effect = RuntimeError("boom")
        error_signal = Mock()

        result = transcribe_offline(model, np.array([1.0], dtype=np.float32), samplerate=16000, error_signal=error_signal)

        self.assertEqual(result, "")
        error_signal.emit.assert_called_once()


class TranscribeStreamingTests(unittest.TestCase):
    def test_passes_streaming_generate_kwargs(self) -> None:
        model = Mock()
        model.generate.return_value = {"text": "hello"}

        result = transcribe_streaming(
            model,
            np.array([1.0], dtype=np.float32),
            {"a": 1},
            is_final=True,
            samplerate=16000,
            chunk_size=[0, 10, 5],
            encoder_chunk_look_back=4,
            decoder_chunk_look_back=1,
            error_signal=Mock(),
        )

        self.assertEqual(result, "hello")
        model.generate.assert_called_once()


class TimedTranscribeOfflineTests(unittest.TestCase):
    def test_returns_text_and_elapsed_ms(self) -> None:
        with patch("recognition.engine_runtime.transcribe_offline", return_value="ok") as transcribe_mock, patch(
            "recognition.engine_runtime.time.perf_counter", side_effect=[10.0, 10.25]
        ):
            text, elapsed = timed_transcribe_offline(
                Mock(),
                np.array([1.0], dtype=np.float32),
                samplerate=16000,
                error_signal=Mock(),
            )

        self.assertEqual(text, "ok")
        self.assertEqual(elapsed, 250.0)
        transcribe_mock.assert_called_once()


class OfflineLatencyTrackerTests(unittest.TestCase):
    def test_percentile_returns_zero_for_empty_values(self) -> None:
        self.assertEqual(OfflineLatencyTracker.percentile([], 0.95), 0.0)

    def test_log_accumulates_final_metrics(self) -> None:
        tracker = OfflineLatencyTracker(report_every=2)
        with patch("recognition.engine_runtime.time.perf_counter", side_effect=[2.0, 3.0]), patch(
            "recognition.engine_runtime.LOGGER.info"
        ) as log_info:
            tracker.log(
                stage="final",
                reason="silence",
                speech_started_at=1.0,
                last_audio_at=1.5,
                segment_samples=16000,
                infer_ms=120.0,
                chars=4,
                samplerate=16000,
            )
            tracker.log(
                stage="final",
                reason="silence",
                speech_started_at=2.0,
                last_audio_at=2.5,
                segment_samples=16000,
                infer_ms=80.0,
                chars=2,
                samplerate=16000,
            )

        self.assertEqual(tracker.final_count, 2)
        self.assertEqual(len(tracker.final_total_ms), 2)
        self.assertGreaterEqual(log_info.call_count, 3)
