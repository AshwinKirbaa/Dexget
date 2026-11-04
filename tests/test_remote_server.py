from jarvis.router import RouteType, route
from jarvis.tools import remote_server


def test_remote_routes():
    cases = {
        "check ashwin_server": "server_ping",
        "show docker containers on ashwin_server": "server_docker_list",
        "get docker logs for jellyfin on ashwin_server": "server_docker_logs",
        "restart container jellyfin on ashwin_server": "server_docker_action",
        "check service docker status on ashwin_server": "server_service_status",
        "show system stats on ashwin_server": "server_monitor",
        "reboot ashwin_server": "server_power",
    }
    for command, tool in cases.items():
        result = route(command)
        assert result.route_type == RouteType.FAST
        assert result.tool_name == tool


def test_remote_path_is_confined():
    assert remote_server._safe_path("compose/app.yml") == "/opt/homeserver/compose/app.yml"
    try:
        remote_server._safe_path("../../etc/passwd")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")


def test_remote_terminal_blocks_forbidden_controls(monkeypatch):
    monkeypatch.setattr(remote_server, "_ssh", lambda command, timeout=30, stdin=None: None)
    for command in (
        "rm notes.txt", "sudo reboot", "ufw disable", "ip link set eth0 down",
        "find /opt/homeserver -delete",
    ):
        result = remote_server.server_terminal(command)
        assert result is not None and not result.success
        assert result.error == "blocked_command"


def test_remote_power_requires_confirmation_in_registry():
    from jarvis.agent.tool_registry import build_default_registry

    registry = build_default_registry(confirm_fn=lambda prompt: False)
    result = registry.execute("server_power", action="reboot")
    assert not result.success
    assert result.error == "confirmation_declined"
