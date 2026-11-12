"""Command output in any code page must decode without crashing (Korean Windows: cp949)."""

import sys

from mcsi.core import proc


def test_decode_utf8_and_cp949(monkeypatch):
    assert proc.decode("규칙 OK".encode("utf-8")) == "규칙 OK"
    monkeypatch.setattr(proc.locale, "getpreferredencoding", lambda do_setlocale=False: "cp949")
    assert proc.decode("규칙이 없습니다".encode("cp949")) == "규칙이 없습니다"
    assert proc.decode(b"\x80\xff\x80 x")            # garbage still gives some text, never raises
    assert proc.decode(None) == "" and proc.decode(b"") == ""


def test_run_returns_text():
    r = proc.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\x80\\x81 ok')"])
    assert r.returncode == 0 and "ok" in r.stdout
