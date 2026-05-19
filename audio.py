"""PyAudio wrappers for the mic and speaker.

Default Voice Agent API audio encoding is `audio/pcm`: 16-bit signed
little-endian PCM at 24 kHz, mono. See:
https://www.assemblyai.com/docs/voice-agents/voice-agent-api/audio-format
"""

import threading
from queue import Queue

import pyaudio

SAMPLE_RATE = 24000
CHUNK_SIZE = 1200  # 50ms at 24kHz 16-bit mono — per docs recommendation


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

    def flush_and_restart(self):
        """Discard any queued playback and reopen the stream.

        Called when the agent is interrupted (barge-in) so the user doesn't
        keep hearing stale speech after they've started talking.
        """
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
