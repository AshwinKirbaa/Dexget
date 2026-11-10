"""Temporary, token-protected LAN file transfer for Dexget."""

from __future__ import annotations

import cgi
import html
import json
import mimetypes
import os
import secrets
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlencode, urlparse


MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


def parse_wifi_credentials(interface_output: str, profile_output: str):
    """Extract the active SSID and saved key from English netsh output."""
    import re
    ssid_match = re.search(r"(?mi)^\s*SSID\s*:\s*(.+?)\s*$", interface_output or "")
    key_match = re.search(r"(?mi)^\s*Key Content\s*:\s*(.+?)\s*$", profile_output or "")
    if not ssid_match or not key_match:
        return None
    return ssid_match.group(1).strip(), key_match.group(1).strip()


def current_wifi_credentials():
    """Return the current saved Wi-Fi SSID/key when Windows permits access."""
    if os.name != "nt":
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        interfaces = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], capture_output=True,
            text=True, timeout=5, creationflags=flags).stdout
        import re
        match = re.search(r"(?mi)^\s*SSID\s*:\s*(.+?)\s*$", interfaces)
        if not match:
            return None
        ssid = match.group(1).strip()
        profile = subprocess.run(
            ["netsh", "wlan", "show", "profile", f"name={ssid}", "key=clear"],
            capture_output=True, text=True, timeout=5, creationflags=flags).stdout
        return parse_wifi_credentials(interfaces, profile)
    except (OSError, subprocess.SubprocessError):
        return None


def pairing_payload(endpoint: str, credentials=None) -> str:
    """Build a QR payload that can join Wi-Fi and then open the endpoint."""
    if not credentials:
        return endpoint
    ssid, password = credentials
    return "dexget://pair?" + urlencode({
        "endpoint": endpoint, "ssid": ssid, "password": password})


def local_ipv4() -> str:
    """Return the LAN address used to reach this computer."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


class TransferServer:
    def __init__(self, download_paths=(), upload_dir=None):
        self.token = secrets.token_urlsafe(24)
        self.download_paths = [
            str(Path(path).resolve()) for path in download_paths
            if Path(path).is_file()
        ]
        self.upload_dir = Path(upload_dir or (
            Path.home() / "Downloads" / "Dexget Transfers"))
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.received_files: list[str] = []
        self._httpd = None
        self._thread = None

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    @property
    def url(self):
        if not self._httpd:
            return ""
        return f"http://{local_ipv4()}:{self._httpd.server_port}/{self.token}/"

    def start(self):
        if self.running:
            return self.url
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def _authorized_path(self):
                parts = [part for part in urlparse(self.path).path.split("/") if part]
                return parts if parts and secrets.compare_digest(parts[0], owner.token) else None

            def _send_html(self, body, status=200):
                payload = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def _page(self, message=""):
                cards = "".join(
                    f'<a class="file" href="download/{index}"><b>{html.escape(Path(path).name)}</b>'
                    f'<small>{Path(path).stat().st_size / 1024:.1f} KB · Download</small></a>'
                    for index, path in enumerate(owner.download_paths)
                    if Path(path).is_file())
                if not cards:
                    cards = '<div class="empty">No laptop files selected yet.</div>'
                return f"""<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Dexget Transfer</title><style>
body{{margin:0;background:#07080a;color:#fff;font:16px system-ui;display:grid;place-items:center;min-height:100vh}}
main{{width:min(92vw,540px)}} h1{{margin-bottom:4px}} p,small{{color:#9b9da6}}
.file,.upload{{display:block;background:#17181c;border:1px solid #292b31;border-radius:16px;padding:16px;margin:10px 0;color:#fff;text-decoration:none}}
.file small{{display:block;margin-top:5px}} .upload{{text-align:center;border-style:dashed}}
input{{max-width:100%}} button{{background:#0a84ff;color:white;border:0;border-radius:22px;padding:12px 22px;font-weight:700;margin-top:12px}}
.ok{{color:#36d976}} .empty{{color:#777;padding:18px 0}}
</style><main><h1>Dexget Transfer</h1><p>Connected directly to this laptop.</p>
<div class=ok>{html.escape(message)}</div><h3>From laptop</h3>{cards}
<h3>Send to laptop</h3><form class=upload method=post enctype=multipart/form-data>
<input name=files type=file multiple required><br><button>Upload files</button></form></main>"""

            def do_GET(self):
                parts = self._authorized_path()
                if parts is None:
                    self._send_html("Not found", 404)
                    return
                if len(parts) == 1:
                    self._send_html(self._page())
                    return
                if len(parts) == 3 and parts[1:] == ["api", "files"]:
                    payload = json.dumps({"files": [
                        {"index": index, "name": Path(path).name,
                         "size": Path(path).stat().st_size}
                        for index, path in enumerate(owner.download_paths)
                        if Path(path).is_file()
                    ]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if len(parts) == 3 and parts[1] == "download":
                    try:
                        path = Path(owner.download_paths[int(parts[2])])
                        if not path.is_file():
                            raise ValueError
                    except (ValueError, IndexError):
                        self._send_html("Not found", 404)
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(path.name)}")
                    self.send_header("Content-Length", str(path.stat().st_size))
                    self.end_headers()
                    with path.open("rb") as source:
                        while chunk := source.read(256 * 1024):
                            self.wfile.write(chunk)
                    return
                self._send_html("Not found", 404)

            def do_POST(self):
                parts = self._authorized_path()
                if parts is None or len(parts) != 1:
                    self._send_html("Not found", 404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    self._send_html("Upload is empty or too large.", 413)
                    return
                form = cgi.FieldStorage(
                    fp=self.rfile, headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")})
                fields = form["files"] if "files" in form else []
                if not isinstance(fields, list):
                    fields = [fields]
                saved = 0
                for field in fields:
                    if not getattr(field, "filename", None):
                        continue
                    name = os.path.basename(unquote(field.filename)).strip() or "upload"
                    target = owner.upload_dir / name
                    stem, suffix, counter = target.stem, target.suffix, 1
                    while target.exists():
                        target = owner.upload_dir / f"{stem} ({counter}){suffix}"
                        counter += 1
                    with target.open("wb") as output:
                        while chunk := field.file.read(256 * 1024):
                            output.write(chunk)
                    owner.received_files.append(str(target))
                    saved += 1
                self._send_html(self._page(f"Received {saved} file(s)."))

        self._httpd = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="DexgetTransfer", daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self._httpd = None
        self._thread = None

