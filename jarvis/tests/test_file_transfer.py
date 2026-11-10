import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

from jarvis.file_transfer import TransferServer


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

