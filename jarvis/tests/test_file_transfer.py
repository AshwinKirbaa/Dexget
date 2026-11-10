import os
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

from jarvis.file_transfer import TransferServer, pairing_payload, parse_wifi_credentials


def test_wifi_pairing_payload_contains_endpoint_and_credentials():
    payload = pairing_payload(
        "http://192.168.1.5:8000/token/", ("Home WiFi", "secret pass"))
    assert payload.startswith("dexget://pair?")
    assert "endpoint=http%3A%2F%2F192.168.1.5%3A8000%2Ftoken%2F" in payload
    assert "ssid=Home+WiFi" in payload
    assert "password=secret+pass" in payload


def test_parse_wifi_credentials_from_netsh_output():
    assert parse_wifi_credentials(
        "    SSID                   : HomeFiber_5Ghz\n",
        "    Key Content            : correct horse battery staple\n",
    ) == ("HomeFiber_5Ghz", "correct horse battery staple")


def test_transfer_server_requires_token_and_moves_files_both_ways(tmp_path):
    shared = tmp_path / "from-laptop.txt"
    shared.write_text("hello phone", encoding="utf-8")
    incoming = tmp_path / "incoming"
    server = TransferServer([shared], incoming)
    url = server.start()
    parsed = urlsplit(url)
    # Exercise the same listener through loopback; managed test sandboxes can
    # block a process from connecting back through its own LAN address.
    url = urlunsplit((parsed.scheme, f"127.0.0.1:{parsed.port}",
                      parsed.path, parsed.query, parsed.fragment))
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            page = response.read().decode("utf-8")
        assert "from-laptop.txt" in page

        with urllib.request.urlopen(url + "api/files", timeout=3) as response:
            files = json.loads(response.read())["files"]
        assert files == [{"index": 0, "name": "from-laptop.txt", "size": 11}]

        with urllib.request.urlopen(url + "download/0", timeout=3) as response:
            assert response.read() == b"hello phone"

        boundary = "----DexgetTestBoundary"
        payload = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="files"; filename="phone.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "hello laptop\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        request = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(request, timeout=3) as response:
            assert b"Received 1 file" in response.read()
        assert (incoming / "phone.txt").read_text(encoding="utf-8") == "hello laptop"
        assert server.received_files == [str(incoming / "phone.txt")]

        bad_url = url.replace(f"/{server.token}/", "/invalid-token/")
        try:
            urllib.request.urlopen(bad_url, timeout=3)
            assert False, "invalid token unexpectedly succeeded"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.stop()
    assert not server.running

