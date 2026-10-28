# agent.py
import json
import os
import queue
import string
import threading
import time

import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeSessionParameters,
    RealTimeTranscriber,
    RealTimeTranscriberOptions,
    TurnEvent,
)
from dotenv import load_dotenv

from audio import MIC_RATE, Mic, Speaker
from tools import TOOLS, dispatch_tool

load_dotenv()
API_KEY = os.environ["ASSEMBLYAI_API_KEY"]

LLM_MODEL = "claude-haiku-4-5-20251001"  # any tool-capable model on LLM Gateway
MAX_TOOL_ROUNDS = 3
GREETING = "Hi! I can check the weather or remember things for you. What do you need?"
SYSTEM_PROMPT = f"""You are a helpful voice assistant.
Your replies are spoken aloud: one or two short sentences, no lists or markdown.
Use the available tools when they help answer the question.
You have already greeted the user with: {GREETING}"""

# Listen: Universal-3.6 Pro Realtime streaming speech-to-text
stt = RealTimeTranscriber(RealTimeTranscriberOptions(), api_key=API_KEY)

# Think: an LLM through LLM Gateway, on the same API key
llm = aai.LLMGateway(api_key=API_KEY)

# Speak: one text-to-speech session for the whole conversation
tts = aai.TTSSession(
    aai.TTSConfig(
        voice_id="49c443a4-8a1d-5f7e-b70b-98bdbd9823c3",  # Audrey
        language="english",
    ),
    api_key=API_KEY,
)

mic = Mic()
speaker = Speaker()
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
turns = queue.Queue()             # finished user turns, in order
speaking = threading.Event()      # set while agent audio is playing
interrupted = threading.Event()   # set when the user talks over the agent
last_spoke_at = 0.0
# --- Listening and barge-in ---
BACKCHANNELS = frozenset({
    "mhm", "mm", "mmhm", "uh", "uhhuh", "huh", "um", "umm", "hmm", "hm",
    "ah", "oh", "yeah", "yep", "yup", "okay", "ok", "right", "alright", "gotcha",
})
_PUNCT = str.maketrans("", "", string.punctuation)


def is_filler(text, min_words):
    tokens = text.lower().translate(_PUNCT).split()
    return len(tokens) < min_words or all(t in BACKCHANNELS for t in tokens)


def on_begin(client, event: BeginEvent):
    print(f"Listening (session {event.id})")


def on_turn(client, event: TurnEvent):
    text = event.transcript.strip()
    if not text:
        return
    if speaking.is_set():
        if is_filler(text, min_words=2):
            return             # "mhm", "yeah": let the agent keep talking
        interrupted.set()      # a real interruption: stop the reply
    elif time.monotonic() - last_spoke_at < 1.0 and is_filler(text, min_words=1):
        return                 # a trailing "mhm" right after the agent finished
    if event.end_of_turn:
        print(f"You:   {text}")
        turns.put(text)


def on_error(client, error: RealTimeError):
    print(f"Speech-to-text error: {error}")
# --- The LLM and tool calls ---
def tool_call_message(text, calls):
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in calls
        ],
    }


def think(user_text):
    messages.append({"role": "user", "content": user_text})
    for _ in range(MAX_TOOL_ROUNDS):
        completion = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=TOOLS,
            max_tokens=300,
        )
        # Text and tool calls can arrive in separate choices, so read them all
        text = " ".join(c.message.content for c in completion.choices if c.message.content).strip()
        calls = [call for c in completion.choices for call in (c.message.tool_calls or [])]
        if not calls:
            messages.append({"role": "assistant", "content": text})
            return text

        messages.append(tool_call_message(text, calls))
        for call in calls:
            args = json.loads(call.function.arguments or "{}")
            result = dispatch_tool(call.function.name, args)
            print(f"Tool:  {call.function.name}({args}) -> {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps({"result": result}),
            })
    return "Sorry, I couldn't finish that. Could you ask me again?"
# --- Speaking, and the main loop ---
def speak(text):
    global last_spoke_at
    if not text:
        return
    print(f"Agent: {text}")
    interrupted.clear()
    speaking.set()
    try:
        for chunk in tts.speak(text):
            if interrupted.is_set():
                tts.cancel()  # barge-in: the server drops the rest of this reply
                print("       (interrupted)")
                break
            speaker.play(chunk)
    finally:
        speaking.clear()
        last_spoke_at = time.monotonic()
    # Tell speech-to-text what the agent just said, so a short answer
    # ("yes", an email, an order number) is transcribed in context
    stt.set_params(RealTimeSessionParameters(agent_context=text[-1750:]))


def main():
    stt.on(RealTimeEvents.Begin, on_begin)
    stt.on(RealTimeEvents.Turn, on_turn)
    stt.on(RealTimeEvents.Error, on_error)
    stt.connect(
        RealTimeParameters(
            speech_model="universal-3-6-pro",
            sample_rate=MIC_RATE,
            agent_context=GREETING,
        )
    )
    tts.connect()
    mic.start()
    threading.Thread(target=stt.stream, args=(mic.chunks(),), daemon=True).start()

    speak(GREETING)
    try:
        while True:
            try:
                user_text = turns.get(timeout=30)
            except queue.Empty:
                tts.keep_alive()  # the TTS session closes after 2 idle minutes
                continue
            speak(think(user_text))
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        mic.stop()
        stt.disconnect(terminate=True)
        tts.terminate()
        speaker.close()


if __name__ == "__main__":
    main()
