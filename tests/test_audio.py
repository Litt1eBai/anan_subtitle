import queue
import unittest

import numpy as np

from recognition.audio_source import build_audio_callback


class AudioCallbackTests(unittest.TestCase):
    def test_callback_pushes_mono_audio_into_queue(self) -> None:
        audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2)
        callback = build_audio_callback(audio_queue)

        callback(np.array([[0.1], [0.2]], dtype=np.float32), 2, None, None)

        queued = audio_queue.get_nowait()
        self.assertTrue(np.array_equal(queued, np.array([0.1, 0.2], dtype=np.float32)))

    def test_callback_drops_oldest_chunk_when_queue_is_full(self) -> None:
        audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
        callback = build_audio_callback(audio_queue)
        audio_queue.put_nowait(np.array([0.0, 0.0], dtype=np.float32))

        callback(np.array([[1.0], [2.0]], dtype=np.float32), 2, None, None)

        queued = audio_queue.get_nowait()
        self.assertTrue(np.array_equal(queued, np.array([1.0, 2.0], dtype=np.float32)))


if __name__ == "__main__":
    unittest.main()
