from jarvis.tasks.browser import WebOpenTask
from jarvis.agent.tool_registry import build_default_registry

registry = build_default_registry()
task = WebOpenTask(registry)
res = task.execute('https://gmail.com', 'gmail', 'professional')
print(res.success)
print(res.observation)
print(res.error)
