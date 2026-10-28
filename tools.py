# tools.py
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save something the user wants you to remember.",
            "parameters": {
                "type": "object",
                "properties": {"fact": {"type": "string"}},
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "List everything the user has asked you to remember.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_memory = []


def dispatch_tool(name, args):
    if name == "get_weather":
        # In production: call a real weather API
        return f"It's 68°F and partly cloudy in {args['city']}."
    if name == "remember":
        _memory.append(args["fact"])
        return f"Saved: {args['fact']}"
    if name == "recall":
        return _memory or "Nothing saved yet."
    return f"Unknown tool: {name}"
