from jarvis.router import route
from jarvis.command_normalizer import CommandNormalizer

commands = [
    "open discord",
    "open chrome",
    "open calculator",
    "open file explorer",
    "open local disk D",
    "open movies folder",
    "open anime folder in D drive",
    "create folder tester in projects folder",
    "play Dexter S07E02 from Movies",
    "open brave in default and search hotstar",
    "switch to performance mode",
    "what is RAG",
    "remember that my favorite color is blue",
    "what is my favorite color",
    "open discord, join Hangout voice call and turn camera on",
    "join Hangout voice call in Discord",
    "open calculator and do 2+2"
]

for cmd in commands:
    print(f"\n--- {cmd} ---")
    norm = CommandNormalizer.normalize(cmd)
    res = route(norm)
    print(f"RouteType: {res.route_type}")
    print(f"ToolName: {res.tool_name}")
    print(f"ToolArgs: {res.tool_args}")
    print(f"Label: {res.label}")
    if res.tool_calls:
        for c in res.tool_calls:
            print(f"  Call: {c.name} {c.args}")
    if res.text:
        print(f"Text: {res.text[:100]}")

