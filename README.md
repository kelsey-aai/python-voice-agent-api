# Real-time Python voice agent with tool calling

Companion code for the AssemblyAI blog post **[Build a real-time voice agent in Python with tool calling](https://www.assemblyai.com/blog/python-voice-agent-tool-calling)**.

A minimal, runnable voice agent in three short files. Microphone in, speaker out, and Python tool calls in between. It runs on AssemblyAI's speech stack:

- **Listen:** [Universal-3.6 Pro Realtime](https://www.assemblyai.com/blog/universal-3-6-pro-realtime) streaming speech-to-text (`universal-3-6-pro`), with turn detection built in
- **Think:** an LLM through [LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart), with OpenAI-style [tool calling](https://www.assemblyai.com/docs/llm-gateway/tool-calling)
- **Speak:** the [AssemblyAI Text-to-Speech API](https://www.assemblyai.com/products/text-to-speech), one session for the whole conversation, with barge-in

All three run on one `ASSEMBLYAI_API_KEY` and the `assemblyai` Python SDK (1.8.2 or later). Fork it, swap the tools, ship it.

---

## Quickstart

### 1. System dependencies

`portaudio` is required for PyAudio:

```bash
# macOS
brew install portaudio

# Debian / Ubuntu
sudo apt-get install -y portaudio19-dev
```

### 2. Python dependencies

Python 3.9 or later.

```bash
git clone https://github.com/kelsey-aai/python-voice-agent-api
cd python-voice-agent-api
pip install -U -r requirements.txt
```

Text-to-speech is in the AssemblyAI Python SDK from version 1.8.2, so upgrade with `-U` if you already have it installed.

### 3. API key

```bash
cp .env.example .env
# edit .env and add your AssemblyAI key
```

Get a key at [assemblyai.com/dashboard/signup](https://www.assemblyai.com/dashboard/signup). LLM Gateway uses the same key; check that your plan includes it.

### 4. Run

```bash
python agent.py
```

Use headphones: a laptop mic picks up the agent's own voice, and the agent will interrupt itself. The agent greets you. Try:

- "What's the weather in San Francisco?"
- "Remember that my passport expires in March."
- "What did I ask you to remember?"
- Start a long question, then talk over the agent's answer to interrupt it.

Ctrl+C to exit.

---

## Files

| File | Purpose |
|---|---|
| `agent.py` | The three clients (speech-to-text, LLM Gateway, text-to-speech), turn handling and barge-in, the tool-calling loop, and the main loop. |
| `audio.py` | `Mic` (16 kHz capture) and `Speaker` (24 kHz playback) wrappers around PyAudio. |
| `tools.py` | Tool definitions (OpenAI-style JSON schemas) and the Python dispatcher. |
| `requirements.txt` | Python deps. |
| `.env.example` | Required env vars. |

---

## How it works

```
Microphone
   │  16 kHz 16-bit mono PCM
   ▼
Universal-3.6 Pro Realtime (streaming speech-to-text)
   │  Turn events: partials, then end_of_turn
   ▼
Your Python script ──► LLM Gateway (chat completions + tools)
   │                        │
   │   tool_calls ◄─────────┘
   ├─► dispatch_tool() runs your Python function
   │   result ─────────────► LLM Gateway again
   ▼
AssemblyAI Text-to-Speech (one session for the conversation)
   │  24 kHz 16-bit mono PCM, streamed
   ▼
Speaker
```

Your script owns the loop:

1. **Listen.** `RealTimeTranscriber` streams mic audio to Universal-3.6 Pro Realtime and fires `Turn` events. When one arrives with `end_of_turn` set, `on_turn` queues the transcript.
2. **Think.** `think()` sends the conversation and the `TOOLS` list to LLM Gateway. If the response has tool calls, it runs each one with `dispatch_tool()`, appends the result as a `tool` message, and calls the LLM again, until the model answers in plain text.
3. **Speak.** `speak()` sends the reply to the `TTSSession` and plays chunks as they arrive. After each reply it updates `agent_context` on the speech-to-text session, so a short answer ("yes", an email, an order number) is transcribed in the context of what the agent just asked.
4. **Barge-in.** While the agent is speaking, a `Turn` transcript with real content sets the `interrupted` flag. Backchannels like "mhm" or "yeah" are filtered out first. `speak()` checks the flag before each chunk and calls `tts.cancel()`, which drops the rest of the reply.

Two details in the tool loop are easy to miss:

- **Read every choice.** Some providers put the model's text in one choice and the tool call in another, so `think()` collects both across all choices.
- **Arguments arrive as a JSON string.** Parse `call.function.arguments` with `json.loads()`, and echo `call.id` back as `tool_call_id`.

---

## Adding your own tools

Edit `tools.py`. Add a JSON schema to `TOOLS`:

```python
{
    "type": "function",
    "function": {
        "name": "create_ticket",
        "description": "Create a support ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "med", "high"]},
            },
            "required": ["title"],
        },
    },
},
```

Then add the dispatcher branch:

```python
if name == "create_ticket":
    # Call your real ticketing API here
    ticket_id = create_ticket_in_your_system(args["title"], args.get("priority", "med"))
    return f"Created ticket #{ticket_id}."
```

The agent starts using the tool the next time you run it.

---

## Customizing

- **LLM:** change `LLM_MODEL` in `agent.py` to any tool-capable model on the [available models list](https://www.assemblyai.com/docs/llm-gateway/available-models), or swap the `llm` client for the `openai` client pointed at OpenAI directly. The message and tool formats stay the same.
- **Voice:** the agent uses Audrey (`voice_id="49c443a4-8a1d-5f7e-b70b-98bdbd9823c3"`). Change `voice_id` to any voice from the voice library, and set `language` to match your users: English, Spanish, French, German, Italian, or Portuguese. See [Voices](https://www.assemblyai.com/docs/tts/voices).
- **Backchannels:** edit the `BACKCHANNELS` set for your domain. "Yes" and "no" are deliberately left out, because in a booking flow a bare "yes" is a real answer.

---

## Latency

- **End of turn.** Send audio in small chunks (50 ms reads, as `audio.py` does) so the model always has the latest audio.
- **The LLM.** Pick a fast model for conversational turns and keep `max_tokens` low. For the lowest time to first audio, stream tokens into the TTS session with `generate()` and `flush()` instead of waiting for the full reply; see the [text-to-speech quickstart](https://www.assemblyai.com/docs/tts/getting-started/quickstart).
- **Text-to-speech.** One session per conversation means no new connection per reply. Play chunks as they arrive.
- **Your tools.** A slow tool call becomes audible silence. Cache hot data, set tight timeouts, or have the agent say "let me check" before a slow lookup.

---

## Going to production

**Phone calls.** Bridge through Twilio Media Streams, which carry 8 kHz μ-law audio. Both services accept that format directly:

```python
import assemblyai as aai
from assemblyai.streaming.v3 import Encoding, RealTimeParameters

stt_params = RealTimeParameters(
    speech_model="universal-3-6-pro",
    encoding=Encoding.pcm_mulaw,
    sample_rate=8000,
)
tts_config = aai.TTSConfig(
    voice_id="49c443a4-8a1d-5f7e-b70b-98bdbd9823c3",  # Audrey
    encoding="pcm_mulaw",
    sample_rate=8000,  # resampled on the server from the native 24 kHz
)
```

**Web apps.** Capture audio in the browser and keep your API key on the server. Mint a [temporary token](https://www.assemblyai.com/docs/streaming/authenticate-with-a-temporary-token) for any client that connects directly.

**Long calls.** A text-to-speech session lasts up to an hour and closes after two idle minutes, which is why the main loop calls `keep_alive()`. See [limits](https://www.assemblyai.com/docs/tts/limits).

**Orchestrators.** Already on LiveKit or Pipecat? Both have AssemblyAI plugins for streaming speech-to-text and text-to-speech ([LiveKit](https://www.assemblyai.com/docs/tts/livekit), [Pipecat](https://www.assemblyai.com/docs/tts/pipecat)).

---

## Resources

- Blog post: [Build a real-time voice agent in Python with tool calling](https://www.assemblyai.com/blog/python-voice-agent-tool-calling)
- [Voice agent best practices](https://www.assemblyai.com/docs/voice-agents/best-practices)
- [LLM Gateway tool calling](https://www.assemblyai.com/docs/llm-gateway/tool-calling)
- [Text-to-speech quickstart](https://www.assemblyai.com/docs/tts/getting-started/quickstart)
- [AssemblyAI pricing](https://www.assemblyai.com/pricing)

---

## License

MIT.
