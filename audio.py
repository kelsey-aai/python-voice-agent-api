# audio.py
import threading
from queue import Queue

import pyaudio

MIC_RATE = 16000      # what we send to speech-to-text
SPEAKER_RATE = 24000  # what AssemblyAI text-to-speech sends back
MIC_CHUNK = 800       # 50 ms of 16 kHz, 16-bit mono audio


class Mic:
    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self.queue = Queue()
        self._running = False

    def start(self):
        self._running = True
        self._stream = self._pa.open(
            format=pyaudio.paInt16, channels=1, rate=MIC_RATE,
            input=True, frames_per_buffer=MIC_CHUNK,
        )
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            self.queue.put(self._stream.read(MIC_CHUNK, exception_on_overflow=False))

    def chunks(self):
        # A generator the streaming client can consume directly
        while self._running:
            yield self.queue.get()

    def stop(self):
        self._running = False
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()


class Speaker:
    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16, channels=1, rate=SPEAKER_RATE, output=True,
        )

    def play(self, audio_bytes):
        # Blocks for roughly the length of the chunk, so playback paces itself
        self._stream.write(audio_bytes)

    def close(self):
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()
