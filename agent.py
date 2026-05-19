"""
Real-time Python voice agent built on the AssemblyAI Voice Agent API.

Run: python agent.py

API surface: https://www.assemblyai.com/docs/voice-agents/voice-agent-api/events-reference
"""

import asyncio
import base64
import json
import os
import sys

import websockets
from dotenv import load_dotenv

from audio import Mic, Speaker
from prompts import SYSTEM_PROMPT
from tools import TOOLS, dispatch_tool

load_dotenv()

ASSEMBLYAI_API_KEY = os.environ["ASSEMBLYAI_API_KEY"]
VOICE_AGENT_WS_URL = "wss://agents.assemblyai.com/v1/ws"
GREETING = "Hi! How can I help?"


async def run():
    mic = Mic()
    speaker = Speaker()

    session_config = {
        "type": "session.update",
        "session": {
            "system_prompt": SYSTEM_PROMPT,
            "greeting": GREETING,
            "tools": TOOLS,
            "output": {"voice": "ivy"},
        },
    }

    async with websockets.connect(
        VOICE_AGENT_WS_URL,
        additional_headers={"Authorization": f"Bearer {ASSEMBLYAI_API_KEY}"},
    ) as ws:
        await ws.send(json.dumps(session_config))

        ready = asyncio.Event()
        pending_tools: list[dict] = []
        loop = asyncio.get_event_loop()

        async def send_audio():
            await ready.wait()
            mic.start()
            while True:
                chunk = await loop.run_in_executor(None, mic.queue.get)
                await ws.send(json.dumps({
                    "type": "input.audio",
                    "audio": base64.b64encode(chunk).decode(),
                }))

        async def receive_events():
            async for raw in ws:
                event = json.loads(raw)
                kind = event.get("type")

                if kind == "session.ready":
                    ready.set()
                    print(f"Session ready: {event.get('session_id')}")

                elif kind == "reply.audio":
                    speaker.play(base64.b64decode(event["data"]))

                elif kind == "tool.call":
                    result = dispatch_tool(
                        event["name"], event.get("arguments", {})
                    )
                    # Accumulate — don't send until reply.done.
                    pending_tools.append({
                        "call_id": event["call_id"],
                        "result": result,
                    })

                elif kind == "reply.done":
                    if event.get("status") == "interrupted":
                        # User barged in — drop pending results and flush playback.
                        pending_tools.clear()
                        speaker.flush_and_restart()
                    elif pending_tools:
                        for tool in pending_tools:
                            value = tool["result"]
                            if not isinstance(value, str):
                                value = json.dumps(value)
                            await ws.send(json.dumps({
                                "type": "tool.result",
                                "call_id": tool["call_id"],
                                "result": value,
                            }))
                        pending_tools.clear()

                elif kind == "transcript.user":
                    print(f"You:   {event['text']}")

                elif kind == "transcript.agent":
                    print(f"Agent: {event['text']}")

                elif kind == "session.error":
                    print(
                        f"Session error [{event.get('code')}]: "
                        f"{event.get('message')}"
                    )

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
