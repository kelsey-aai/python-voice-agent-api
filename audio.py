"""PyAudio wrappers for the mic and speaker."""

import threading
from queue import Queue

import pyaudio

SAMPLE_RATE = 16000
CHUNK_SIZE = 3200  # 200ms at 16kHz 16-bit


class Mic:
    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self.queue: Queue[bytes] = Queue()
        self._running = False

    def start(self):
        self._running = True
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            try:
                self.queue.put(
                    self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                )
            except Exception:
                break

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._pa.terminate()


class Speaker:
    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
        )

    def play(self, audio_bytes: bytes):
        self._stream.write(audio_bytes)

    def flush(self):
        # Best-effort interruption: stop and reopen the stream.
        try:
            self._stream.stop_stream()
            self._stream.close()
        except Exception:
            pass
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
        )

    def close(self):
        try:
            self._stream.stop_stream()
            self._stream.close()
        except Exception:
            pass
        self._pa.terminate()
