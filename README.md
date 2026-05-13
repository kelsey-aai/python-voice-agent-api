# Python voice agent with the AssemblyAI Voice Agent API

A minimal, runnable real-time voice agent in Python. Microphone in, speaker out, tool calls in between — all over one WebSocket at $4.50/hour flat.

**Stack**

- **Voice Agent API:** AssemblyAI (one WebSocket = STT + LLM + TTS + turn detection + tool calling)
- **Audio:** PyAudio (16kHz PCM in and out)
- **Tools:** Example `get_weather`, `remember`, `recall_memory`

**~200 lines of Python.** Fork it, swap the tools, ship it.

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

```bash
pip install -r requirements.txt
```

### 3. API key

```bash
cp .env.example .env
# edit .env and add your AssemblyAI key
```

Get a key at [assemblyai.com/dashboard/signup](https://www.assemblyai.com/dashboard/signup).

### 4. Run

```bash
python agent.py
```

The agent greets you. Try:

- "What's the weather in San Francisco?"
- "Remember that my passport expires in March."
- "What did I just tell you to remember?"

Ctrl+C to exit.

---

## Files

| File | Purpose |
|---|---|
| `agent.py` | Main loop. Opens the WebSocket, pumps mic in / speaker out, dispatches tool calls. |
| `audio.py` | `Mic` and `Speaker` wrappers around PyAudio. |
| `tools.py` | Tool definitions (JSON schemas) and the Python dispatcher. |
| `prompts.py` | System prompt. |
| `requirements.txt` | Python deps. |
| `.env.example` | Required env vars. |

---

## How it works

```
  mic.read() ──► audio.input event ──► Voice Agent API
                                          │
                              ┌───────────┴───────────┐
                              │ STT → LLM + tools → TTS │
                              └───────────┬───────────┘
                                          │
  speaker.play() ◄── audio.output event ──┤
                                          │
  dispatch_tool() ◄── tool.call event ────┤
                                          │
                              tool.result ┘
```

Two coroutines run concurrently:

1. **send_audio** — pulls chunks from the mic queue and ships them as `audio.input` events
2. **receive_events** — reads events from the WebSocket and routes them: `audio.output` → speaker, `tool.call` → dispatcher → `tool.result`, transcripts → stdout

---

## Adding your own tools

Edit `tools.py`. Add a JSON schema to `TOOLS`:

```python
{
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
```

Then implement the dispatcher branch:

```python
if name == "create_ticket":
    # Call your real ticketing API here.
    ticket_id = create_in_zendesk(args["title"], args.get("priority", "med"))
    return f"Created ticket #{ticket_id}."
```

The agent will start using the tool the next time you run it.

---

## Latency

Typical end-to-end perceived latency on this stack: **450–950ms** from when you stop talking to when you hear the reply.

To stay under 500ms:

- Keep mic chunks small (200ms or less — the default in `audio.py`)
- Never block in `dispatch_tool`. If a tool needs more than 500ms, cache or pre-compute, or return a stall ("Let me check on that") while the real call resolves
- Play `audio.output` chunks as they arrive — never buffer the full reply

---

## Going further

For phone calls, swap the `Mic` and `Speaker` in `audio.py` for a Twilio Media Streams bridge (use `pcm_mulaw` at 8kHz — no resampling). For browser-based audio, swap them for a WebSocket bridge from the browser's `MediaRecorder` or `AudioWorklet`.

---

## License

MIT.
