"""
Real-time Python voice agent built on the AssemblyAI Voice Agent API.

Run: python agent.py
"""

import asyncio
import base64
import json
import os
import signal
import sys

import websockets
from dotenv import load_dotenv

from audio import Mic, Speaker, SAMPLE_RATE
from prompts import SYSTEM_PROMPT
from tools import TOOLS, dispatch_tool

load_dotenv()

ASSEMBLYAI_API_KEY = os.environ["ASSEMBLYAI_API_KEY"]
VOICE_AGENT_WS_URL = "wss://streaming.assemblyai.com/voice-agent/v1/ws"


async def run():
    mic = Mic()
    speaker = Speaker()

    config = {
        "type": "session.start",
        "system_prompt": SYSTEM_PROMPT,
        "tools": TOOLS,
        "voice": {
            "provider": "elevenlabs",
            "voice_id": os.environ.get(
                "ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"
            ),
        },
        "language": "en",
        "input_audio_format":  {"encoding": "pcm_s16le", "sample_rate": SAMPLE_RATE},
        "output_audio_format": {"encoding": "pcm_s16le", "sample_rate": SAMPLE_RATE},
    }

    async with websockets.connect(
        VOICE_AGENT_WS_URL,
        extra_headers={"Authorization": ASSEMBLYAI_API_KEY},
    ) as ws:
        await ws.send(json.dumps(config))
        mic.start()
        loop = asyncio.get_event_loop()

        async def send_audio():
            while True:
                chunk = await loop.run_in_executor(None, mic.queue.get)
                await ws.send(json.dumps({
                    "type": "audio.input",
                    "audio": base64.b64encode(chunk).decode(),
                }))

        async def receive_events():
            async for raw in ws:
                event = json.loads(raw)
                kind = event.get("type")

                if kind == "audio.output":
                    speaker.play(base64.b64decode(event["audio"]))

                elif kind == "interruption":
                    speaker.flush()

                elif kind == "tool.call":
                    result = dispatch_tool(event["name"], event.get("arguments", {}))
                    await ws.send(json.dumps({
                        "type": "tool.result",
                        "tool_call_id": event["tool_call_id"],
                        "content": result,
                    }))

                elif kind == "transcript.user.final":
                    print(f"You:   {event['text']}")

                elif kind == "transcript.agent.final":
                    print(f"Agent: {event['text']}")

                elif kind == "session.ended":
                    return

        try:
            await asyncio.gather(send_audio(), receive_events())
        finally:
            mic.stop()
            speaker.close()


def main():
    print("Voice agent ready. Start speaking. Ctrl+C to exit.\n")
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nGoodbye.")
        sys.exit(0)


if __name__ == "__main__":
    main()
