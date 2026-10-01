"""Process management tools, built on psutil (already a dependency of the legacy jarvis.py)."""
from __future__ import annotations

from jarvis.tools.base import RiskLevel, Tool, ToolResult

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only when psutil truly missing
    psutil = None


def list_processes(name_contains: str = "") -> ToolResult:
    if psutil is None:
        return ToolResult(False, error="psutil_missing", observation="psutil is not installed")
    needle = (name_contains or "").lower()
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        name = (p.info.get("name") or "")
        if needle in name.lower():
            procs.append({"pid": p.info.get("pid"), "name": name})
    return ToolResult(True, output=procs, observation=f"Found {len(procs)} matching process(es)")


def kill_process(pid: int) -> ToolResult:
    if psutil is None:
        return ToolResult(False, error="psutil_missing", observation="psutil is not installed")
    try:
        p = psutil.Process(int(pid))
        name = p.name()
        p.terminate()
        return ToolResult(True, output=pid, observation=f"Terminated process {name} (pid {pid})")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, error=str(exc), observation=f"Could not terminate pid {pid}: {exc}")


def get_process_info() -> ToolResult:
    if psutil is None:
        return ToolResult(False, error="psutil_missing", observation="psutil is not installed")
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "ram_percent": round(p.info.get("memory_percent", 0) or 0, 2),
                "cpu_percent": round(p.info.get("cpu_percent", 0) or 0, 2)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    # Sort by ram usage descending and keep top 20 to avoid huge output
    procs.sort(key=lambda x: x["ram_percent"], reverse=True)
    return ToolResult(True, output=procs[:20], observation=f"Found {len(procs)} processes, returning top 20 by RAM usage.")

def get_application_info(app_name: str = "", query: str = "") -> ToolResult:
    if not app_name and query:
        # If it's a general query like "what applications are running", just return process info
        return get_process_info()
        
    try:
        from jarvis.tools.application_resolver import resolve_application, find_installed_application, check_running_process
        target = resolve_application(app_name)
        app_info = find_installed_application(target)
        is_running = check_running_process(target)
        return ToolResult(True, output={
            "app_name": target,
            "installed": app_info.get("installed", False),
            "command": app_info.get("command"),
            "running": is_running
        }, observation=f"Checked {target}")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=str(exc))

def register(registry) -> None:
    registry.register(Tool("sys_get_process", "Get info about running processes.", {}, RiskLevel.LOW, get_process_info, "system"))
    registry.register(Tool("sys_get_application", "Check if an app is installed or running.", {"app_name": {"type": "str"}, "query": {"type": "str"}}, RiskLevel.LOW, get_application_info, "system"))
    registry.register(Tool(
        name="process_list", description="List running processes, optionally filtered by name substring.",
        parameters={"name_contains": {"type": "str"}},
        risk_level=RiskLevel.LOW, func=list_processes, category="process"))
    registry.register(Tool(
        name="process_kill", description="Terminate a process by PID.",
        parameters={"pid": {"type": "int", "required": True}},
        risk_level=RiskLevel.HIGH, func=kill_process, category="process"))
