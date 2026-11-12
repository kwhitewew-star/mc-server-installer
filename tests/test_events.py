"""Event loaders and the update check (offline)."""

import json
import subprocess
from datetime import date

import pytest

from mcsi.core import events as ev
from mcsi.core import update


def by_key(key):
    return next(e for e in ev.BUILTIN if e.key == key)


@pytest.mark.parametrize("key, day, active", [
    ("halloween", date(2026, 10, 31), True),
    ("halloween", date(2026, 11, 2), False),
    ("newyear", date(2026, 12, 31), True),      # window wraps the new year
    ("newyear", date(2027, 1, 3), True),
    ("newyear", date(2027, 1, 4), False),
    ("aprilfools", date(2027, 4, 1), True),
    ("aprilfools", date(2027, 4, 2), False),
    ("ufo", date(2027, 7, 2), True),
])
def test_windows(key, day, active):
    assert by_key(key).active(day) is active


def test_event_date_override(monkeypatch):
    monkeypatch.setenv("MCSI_EVENT_DATE", "2026-12-24")
    assert [e.key for e in ev.visible(ev.BUILTIN)] == ["christmas"]
    assert len(ev.visible(ev.BUILTIN, show_all=True)) == len(ev.BUILTIN)


def test_merge_remote(monkeypatch):
    monkeypatch.setattr(ev, "get_language", lambda: "en")      # independent of the language in the user's config
    remote = [
        {"key": "halloween", "windows": [[10, 1, 10, 31]], "sha256": "ab" * 32},      # changed dates
        {"key": "snow", "name": "Snow Loader", "desc": {"en": "Snow!", "ko": "눈!"}, "windows": [[1, 10, 1, 12]]},
        {"key": "ufo", "disabled": True},
        {"key": "broken", "windows": [[1, 2]]},                                          # ignored
        "nonsense",
    ]
    out = {e.key: e for e in ev.merge(remote)}
    assert out["halloween"].windows == [[10, 1, 10, 31]]
    assert out["halloween"].jar == "pumpkin-loader.jar"           # kept from the built-in entry
    assert out["snow"].name == "Snow Loader" and out["snow"].desc == "Snow!"
    assert "ufo" not in out and "broken" not in out
    monkeypatch.setattr(ev, "get_language", lambda: "ko")
    assert {e.key: e for e in ev.merge(remote)}["snow"].desc == "눈!"
    monkeypatch.setattr(ev, "get_language", lambda: "ja")      # no Japanese text -> English
    assert {e.key: e for e in ev.merge(remote)}["snow"].desc == "Snow!"


def test_every_builtin_jar_is_bundled():
    for e in ev.BUILTIN:
        assert (ev.BUNDLED / e.jar).is_file(), e.jar


def test_install_uses_bundled_jar_offline(tmp_path, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("must not download when the bundled jar matches")
    monkeypatch.setattr(ev, "download", no_net)
    folder = ev.install(by_key("halloween"), tmp_path / "Pumpkin")
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["README.txt", "pumpkin-loader.jar", "start.bat", "start.sh"]
    bat = (folder / "start.bat").read_text(encoding="utf-8")
    assert 'java -jar "pumpkin-loader.jar"' in bat and "color 06" in bat


def test_install_falls_back_to_bundled_copy(tmp_path, monkeypatch):
    e = by_key("christmas")
    e2 = ev.Event(**{**e.__dict__, "sha256": "00" * 32})          # remote says a newer jar exists
    urls = []

    def offline(url, *a, **k):
        urls.append(url)
        raise OSError("offline")
    monkeypatch.setattr(ev, "download", offline)
    assert ev.get_jar(e2, tmp_path / "x.jar") == "bundled"
    assert urls == [ev.DOWNLOAD + "event-christmas/jingle-loader.jar"]   # each loader has its own release


def test_custom_release_tag():
    e = ev.merge([{"key": "halloween", "tag": "pumpkin-2027"}])[0]
    assert e.jar_url.endswith("/releases/download/pumpkin-2027/pumpkin-loader.jar")


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "CACHE", tmp_path / "c.json")
    monkeypatch.setattr(ev, "get_json", lambda *a, **k: {"events": [{"key": "extra", "windows": [[5, 5, 5, 5]]}]})
    assert any(e.key == "extra" for e in ev.fetch())
    monkeypatch.setattr(ev, "get_json", lambda *a, **k: (_ for _ in ()).throw(ev.NetError("offline")))
    assert any(e.key == "extra" for e in ev.fetch())               # from the cache
    assert json.loads((tmp_path / "c.json").read_text())["events"][0]["key"] == "extra"


def test_jar_runs_if_java_available(tmp_path):
    try:
        subprocess.run(["java", "-version"], capture_output=True, timeout=20, check=True)
    except Exception:
        pytest.skip("no java")
    jar = ev.BUNDLED / "prank-loader.jar"
    r = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(jar), "--ascii"], capture_output=True, text=True,
                       timeout=40)
    assert r.returncode == 0
    assert "Prank Loader has finished" in r.stdout


def test_versions():
    assert update.is_newer("1.0.10", "1.0.9")
    assert update.is_newer("v2.0", "1.9.9")
    assert not update.is_newer("1.0.2", "1.0.2")
    assert not update.is_newer("1.0.1", "1.0.2")


def test_latest_ignores_older_and_prerelease(monkeypatch):
    monkeypatch.setattr(update, "get_json", lambda *a, **k: {"tag_name": "v99.0.0", "html_url": "u", "body": "b"})
    assert update.latest().version == "99.0.0"
    monkeypatch.setattr(update, "get_json", lambda *a, **k: {"tag_name": "v0.0.1"})
    assert update.latest() is None
    monkeypatch.setattr(update, "get_json", lambda *a, **k: {"tag_name": "v99.0.0", "prerelease": True})
    assert update.latest() is None
