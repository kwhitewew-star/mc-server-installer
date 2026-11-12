"""Downloads continue (HTTP Range) when the server stalls or drops the connection."""

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mcsi.core import net

DATA = bytes(range(256)) * 4096          # 1 MiB


class Server:
    def __init__(self, mode, ranges=True):
        self.mode, self.ranges, self.requests = mode, ranges, []
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                rng = self.headers.get("Range")
                srv.requests.append(rng)
                start = int(rng.split("=")[1].rstrip("-")) if rng and srv.ranges else 0
                body = DATA[start:]
                self.send_response(206 if start else 200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                first = len(srv.requests) == 1
                if first and srv.mode == "drop":           # close after 300 KB
                    self.wfile.write(body[:300_000])
                    self.wfile.flush()
                    self.connection.close()
                    return
                if first and srv.mode == "stall":          # send 300 KB, then go silent
                    self.wfile.write(body[:300_000])
                    self.wfile.flush()
                    threading.Event().wait(3)
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/server.jar"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.mark.parametrize("mode, ranges", [("drop", True), ("stall", True), ("drop", False)])
def test_resumes(tmp_path, monkeypatch, mode, ranges):
    monkeypatch.setattr(net, "STALL_SEC", 1)
    s = Server(mode, ranges)
    logs = []
    try:
        net.download(s.url, tmp_path / "server.jar", sha256=hashlib.sha256(DATA).hexdigest(), log=logs.append)
    finally:
        s.close()
    assert (tmp_path / "server.jar").read_bytes() == DATA
    assert s.requests[0] is None and len(s.requests) >= 2 and s.requests[1].startswith("bytes=")
    assert any("MB/s" in m for m in logs)
    assert not (tmp_path / "server.jar.part").exists()
