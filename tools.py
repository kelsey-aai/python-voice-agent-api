"""Example tools for the Python voice agent.

Replace the stub implementations in dispatch_tool with calls to your real
backends (weather API, CRM, database, etc.).
"""

import json

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name."},
            },
            "required": ["city"],
        },
    },
    {
        "name": "remember",
        "description": "Save something the user wants you to remember.",
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact to remember."},
            },
            "required": ["fact"],
        },
    },
    {
        "name": "recall_memory",
        "description": "List things the user has asked you to remember.",
        "parameters": {"type": "object", "properties": {}},
    },
]


_memory: list[str] = []


def dispatch_tool(name: str, args) -> str:
    if isinstance(args, str):
        args = json.loads(args)

    if name == "get_weather":
        # Replace with a real weather API call.
        return f"It's 68°F and partly cloudy in {args['city']}."

    if name == "remember":
        _memory.append(args["fact"])
        return f"Got it. Remembered: {args['fact']}"

    if name == "recall_memory":
        if not _memory:
            return "You haven't asked me to remember anything yet."
        bullets = "; ".join(_memory)
        return f"Here's what I have: {bullets}"

    return f"Unknown tool: {name}"
