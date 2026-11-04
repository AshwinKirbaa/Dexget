"""Restricted SSH controls for the user's Tailscale-only Ubuntu server."""
from __future__ import annotations

import base64
import ipaddress
import os
import posixpath
import re
import shlex
import subprocess
from typing import Optional

from jarvis.security.permissions import redact_secrets
from jarvis.tools.base import RiskLevel, Tool, ToolResult

SERVER_ROOT = "/opt/homeserver"
TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$")
BLOCKED_TERMINAL = re.compile(
    r"(?:^|[;&|]\s*|\bsudo\s+)(?:rm|rmdir|unlink|shred|truncate|dd|mkfs|fdisk|parted|"
    r"shutdown|reboot|poweroff|halt|iptables|ip6tables|nft|ufw|firewall-cmd|ip|ifconfig|"
    r"nmcli|netplan|route|systemctl\s+(?:reboot|poweroff))\b|\bfind\b[^;&|]*\s-delete\b",
    re.IGNORECASE,
)


def _config() -> tuple[str, str, str]:
    host = os.environ.get("JARVIS_SERVER_HOST", "100.106.129.0").strip()
    user = os.environ.get("JARVIS_SERVER_USER", "ashwin_server").strip()
    key = os.path.expandvars(os.path.expanduser(os.environ.get(
        "JARVIS_SERVER_SSH_KEY", r"%USERPROFILE%\.ssh\ashwinserver_ed25519"
    )))
    try:
        if ipaddress.ip_address(host) not in TAILSCALE_NET:
            raise ValueError("server address is not inside Tailscale CGNAT space")
    except ValueError as exc:
        raise ValueError(f"Unsafe JARVIS_SERVER_HOST '{host}': {exc}") from exc
    if not SAFE_NAME.fullmatch(user):
        raise ValueError("Unsafe SSH username")
    if not os.path.isfile(key):
        raise FileNotFoundError(f"SSH key not found: {key}")
    return host, user, key


def _ssh(command: str, timeout: int = 30, stdin: Optional[bytes] = None) -> ToolResult:
    try:
        host, user, key = _config()
        argv = [
            "ssh.exe", "-T", "-i", key,
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8",
            f"{user}@{host}", "--", f"sh -lc {shlex.quote(command)}",
        ]
        proc = subprocess.run(
            argv, input=stdin, capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = redact_secrets(proc.stdout.decode("utf-8", "replace").strip())
        err = redact_secrets(proc.stderr.decode("utf-8", "replace").strip())
        ok = proc.returncode == 0
        return ToolResult(
            ok, output={"stdout": out, "stderr": err, "returncode": proc.returncode},
            error=None if ok else (err or f"ssh exit {proc.returncode}"),
            observation=out or err or f"Remote command exited with {proc.returncode}.",
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, error="timeout", observation="ashwin_server did not respond in time.")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not connect to ashwin_server: {exc}")


def _safe_path(path: str) -> str:
    raw = (path or "").strip()
    candidate = raw if raw.startswith("/") else posixpath.join(SERVER_ROOT, raw)
    normalized = posixpath.normpath(candidate)
    if normalized != SERVER_ROOT and not normalized.startswith(SERVER_ROOT + "/"):
        raise ValueError(f"Path must stay under {SERVER_ROOT}")
    return normalized


def server_ping() -> ToolResult:
    return _ssh("printf 'ashwin_server connected'; uptime -p")


def server_terminal(command: str) -> ToolResult:
    command = (command or "").strip()
    if not command:
        return ToolResult(False, error="empty_command", observation="Remote command is empty.")
    if BLOCKED_TERMINAL.search(command):
        return ToolResult(False, error="blocked_command", observation=(
            "Blocked: remote deletion, power, disk, firewall, and network commands require dedicated controls."
        ))
    return _ssh(command, timeout=60)


def server_monitor() -> ToolResult:
    script = r"""
printf '%s\n' '== uptime ==' && uptime -p
printf '%s\n' '== cpu ==' && (LC_ALL=C top -bn1 | sed -n '3p' || true)
printf '%s\n' '== memory ==' && free -h
printf '%s\n' '== disk ==' && df -h / /opt/homeserver 2>/dev/null | awk 'NR==1 || !seen[$6]++'
printf '%s\n' '== temperature ==' && (sensors 2>/dev/null || for z in /sys/class/thermal/thermal_zone*/temp; do [ -r "$z" ] && awk '{printf "%.1f C\n", $1/1000}' "$z"; done)
printf '%s\n' '== battery ==' && (upower -e 2>/dev/null | grep -m1 battery | xargs -r upower -i 2>/dev/null | grep -E 'state|percentage|time to' || echo 'not available')
""".strip()
    return _ssh(script)


def docker_list() -> ToolResult:
    result = _ssh("docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'")
    return _docker_permission_hint(result)


def docker_logs(container: str, lines: int = 100) -> ToolResult:
    if not SAFE_NAME.fullmatch(container or ""):
        return ToolResult(False, error="invalid_container", observation="Invalid Docker container name.")
    lines = max(1, min(int(lines), 1000))
    return _docker_permission_hint(_ssh(f"docker logs --tail {lines} {shlex.quote(container)} 2>&1", timeout=60))


def docker_action(container: str, action: str) -> ToolResult:
    if not SAFE_NAME.fullmatch(container or ""):
        return ToolResult(False, error="invalid_container", observation="Invalid Docker container name.")
    if action not in {"start", "stop", "restart"}:
        return ToolResult(False, error="invalid_action", observation="Use start, stop, or restart.")
    return _docker_permission_hint(_ssh(f"docker {action} {shlex.quote(container)}", timeout=60))


def _docker_permission_hint(result: ToolResult) -> ToolResult:
    message = f"{result.error or ''} {result.observation or ''}".lower()
    if not result.success and ("docker.sock" in message or "docker api" in message):
        result.observation = (
            "ashwin_server is not in the docker group. On the server, run once: "
            "sudo usermod -aG docker ashwin_server, then sign out and back in."
        )
    return result


def service_status(service: str) -> ToolResult:
    if not SAFE_NAME.fullmatch(service or ""):
        return ToolResult(False, error="invalid_service", observation="Invalid system service name.")
    return _ssh(f"systemctl status --no-pager --lines=30 {shlex.quote(service)}")


def service_logs(service: str, lines: int = 100) -> ToolResult:
    if not SAFE_NAME.fullmatch(service or ""):
        return ToolResult(False, error="invalid_service", observation="Invalid system service name.")
    lines = max(1, min(int(lines), 1000))
    return _ssh(f"journalctl -u {shlex.quote(service)} -n {lines} --no-pager", timeout=60)


def server_list_files(path: str = SERVER_ROOT) -> ToolResult:
    try:
        safe = _safe_path(path)
    except ValueError as exc:
        return ToolResult(False, error="path_outside_root", observation=str(exc))
    return _ssh(f"find {shlex.quote(safe)} -maxdepth 1 -mindepth 1 -printf '%y %f\n' | sort")


def server_read_file(path: str) -> ToolResult:
    try:
        safe = _safe_path(path)
    except ValueError as exc:
        return ToolResult(False, error="path_outside_root", observation=str(exc))
    result = _ssh(f"base64 -w0 -- {shlex.quote(safe)}", timeout=60)
    if result.success:
        try:
            text = base64.b64decode(result.output["stdout"], validate=True).decode("utf-8", "replace")
            result.output = text
            result.observation = text[:16000]
        except Exception as exc:
            return ToolResult(False, error=str(exc), observation="Could not decode the remote file.")
    return result


def server_write_file(path: str, content: str) -> ToolResult:
    try:
        safe = _safe_path(path)
    except ValueError as exc:
        return ToolResult(False, error="path_outside_root", observation=str(exc))
    payload = base64.b64encode((content or "").encode("utf-8"))
    parent = posixpath.dirname(safe)
    command = f"mkdir -p -- {shlex.quote(parent)} && base64 -d > {shlex.quote(safe)}"
    result = _ssh(command, timeout=60, stdin=payload)
    if result.success:
        result.observation = f"Wrote {len(content.encode('utf-8'))} bytes to {safe}."
    return result


def server_power(action: str) -> ToolResult:
    if action not in {"reboot", "shutdown"}:
        return ToolResult(False, error="invalid_action", observation="Use reboot or shutdown.")
    command = "sudo -n reboot" if action == "reboot" else "sudo -n shutdown -h now"
    result = _ssh(command, timeout=15)
    if not result.success and "closed" in (result.error or "").lower():
        return ToolResult(True, observation=f"ashwin_server {action} command was sent.")
    return result


def register(registry) -> None:
    def add(name, description, parameters, risk, func):
        registry.register(Tool(name, description, parameters, risk, func, "remote_server"))

    add("server_ping", "Check the fixed ashwin_server SSH connection.", {}, RiskLevel.LOW, server_ping)
    add("server_monitor", "Get ashwin_server CPU, memory, disk, temperature, battery and uptime.", {}, RiskLevel.LOW, server_monitor)
    add("server_terminal", "Run a non-destructive command on ashwin_server; deletion, power, disk, firewall and network changes are blocked.", {"command": {"type": "str", "required": True}}, RiskLevel.HIGH, server_terminal)
    add("server_docker_list", "List Docker containers and status on ashwin_server.", {}, RiskLevel.LOW, docker_list)
    add("server_docker_logs", "Read Docker container logs on ashwin_server.", {"container": {"type": "str", "required": True}, "lines": {"type": "int", "required": False}}, RiskLevel.LOW, docker_logs)
    add("server_docker_action", "Start, stop or restart one Docker container on ashwin_server.", {"container": {"type": "str", "required": True}, "action": {"type": "str", "required": True}}, RiskLevel.MEDIUM, docker_action)
    add("server_service_status", "Read systemd service status on ashwin_server.", {"service": {"type": "str", "required": True}}, RiskLevel.LOW, service_status)
    add("server_service_logs", "Read systemd journal logs on ashwin_server.", {"service": {"type": "str", "required": True}, "lines": {"type": "int", "required": False}}, RiskLevel.LOW, service_logs)
    add("server_list_files", f"List files only under {SERVER_ROOT}.", {"path": {"type": "str", "required": False}}, RiskLevel.LOW, server_list_files)
    add("server_read_file", f"Read a UTF-8 file only under {SERVER_ROOT}.", {"path": {"type": "str", "required": True}}, RiskLevel.LOW, server_read_file)
    add("server_write_file", f"Write a UTF-8 file only under {SERVER_ROOT}; deletion is unavailable.", {"path": {"type": "str", "required": True}, "content": {"type": "str", "required": True}}, RiskLevel.MEDIUM, server_write_file)
    add("server_power", "Reboot or shut down ashwin_server. Always requires explicit confirmation.", {"action": {"type": "str", "required": True}}, RiskLevel.DESTRUCTIVE, server_power)
