import logging
import queue
from typing import Any

import numpy as np

LOGGER = logging.getLogger("desktop_subtitle")

def build_audio_callback(
    audio_queue: "queue.Queue[np.ndarray]",
) -> Any:
    dropped_chunks = 0

    def callback(indata, frames, time_info, status) -> None:
        nonlocal dropped_chunks
        del frames, time_info, status
        mono = np.squeeze(indata).astype(np.float32, copy=True)
        try:
            audio_queue.put_nowait(mono)
        except queue.Full:
            dropped_chunks += 1
            if dropped_chunks == 1 or dropped_chunks % 50 == 0:
                LOGGER.warning("Audio queue overflow, dropped chunks=%d", dropped_chunks)
            try:
                audio_queue.get_nowait()
                audio_queue.put_nowait(mono)
            except queue.Empty:
                pass

    return callback
