"""Shared fixtures. Everything runs offline: network calls go to tests/fake_api.py and Java is tests/fakejava."""

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(HERE)]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fake_api  # noqa: E402

fake_api.install()

FAKE_JAVA = HERE / "fakejava" / "bin" / "java"


@pytest.fixture
def fake_java(monkeypatch):
    FAKE_JAVA.chmod(0o755)
    monkeypatch.setenv("PATH", str(FAKE_JAVA.parent) + os.pathsep + os.environ["PATH"])
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda n, *a, **k: "/usr/bin/git" if n == "git" else real_which(n, *a, **k))
    return str(FAKE_JAVA)


@pytest.fixture
def no_downloads(monkeypatch):
    """Replace real downloads with tiny placeholder files; returns the list of requested URLs."""
    import mcsi.core.installer as I
    got = []

    def fake_download(url, dest, on_progress=None, is_cancelled=lambda: False, **hashes):
        got.append(url)
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_text("jar")
        if on_progress:
            on_progress(3, 3)

    monkeypatch.setattr(I, "download", fake_download)
    return got


@pytest.fixture
def no_upnp(monkeypatch):
    """Pretend the router answered UPnP and opened every port."""
    from mcsi.core import upnp
    calls = []

    def fake_forward(rules, desc="", log=lambda s: None, gateway=None):
        calls.append(list(rules))
        return upnp.ForwardResult(True, gateway="192.168.0.1", local_ip="192.168.0.10", external_ip="203.0.113.7",
                                  opened=[f"{p}/{pr}" for p, pr in rules])

    monkeypatch.setattr(upnp, "forward_ports", fake_forward)
    return calls
