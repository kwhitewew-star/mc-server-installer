"""Limited-time joke "event loaders" (Halloween, Christmas, ...).

An event loader shows up as an extra server type only during its date window. Picking it installs
instantly: a small jar that plays a console animation and exits, plus start.bat / start.sh. There is
no first run, no Java check and no port forwarding.

The list is built in, and can be extended without a new app release: ``events.json`` is published on
the repository's ``events`` GitHub release, and every loader has its own release (``event-<key>``)
holding its jar. Remote entries replace or add to the built-in ones. If the download fails, the jar
bundled with the app is used.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..i18n import _, get_language
from .java import APP_DIR
from .net import NetError, download, get_json

REPO = "kwhitewew-star/mc-server-installer"
DOWNLOAD = f"https://github.com/{REPO}/releases/download/"
EVENTS_URL = DOWNLOAD + "events/events.json"
CACHE = APP_DIR / "events_cache.json"
BUNDLED = Path(__file__).resolve().parents[1] / "assets" / "events"


@dataclass
class Event:
    key: str                         # "halloween"
    name: str                        # "Pumpkin Loader"
    desc: str                        # shown on the card
    accent: str
    icon: str
    windows: list                    # [[month, day, month, day], ...]  (may wrap the new year)
    jar: str = ""                    # file name, e.g. "pumpkin-loader.jar"
    sha256: str = ""
    console_color: str = "0F"        # Windows `color` for start.bat
    headline: str = ""               # announcement title
    fx: str = ""                     # animation: "gl:<anim key>" or "ufo"
    tag: str = ""                    # GitHub release holding the jar (default "event-<key>")
    extra: dict = field(default_factory=dict)

    @property
    def server_key(self) -> str:
        return "ev_" + self.key

    @property
    def release_tag(self) -> str:
        return self.tag or f"event-{self.key}"

    @property
    def jar_url(self) -> str:
        return f"{DOWNLOAD}{self.release_tag}/{self.jar}"

    def active(self, today: date | None = None) -> bool:
        d = today or event_today()
        md = (d.month, d.day)
        for m1, d1, m2, d2 in self.windows:
            a, b = (m1, d1), (m2, d2)
            if (a <= md <= b) if a <= b else (md >= a or md <= b):
                return True
        return False

    def window_text(self) -> str:
        m1, d1, m2, d2 = self.windows[0]
        return f"{m1}/{d1}" if (m1, d1) == (m2, d2) else f"{m1}/{d1} – {m2}/{d2}"


CURRENT: list = []          # the event list the app is using (set by the main window)


def find(key: str) -> "Event | None":
    return next((e for e in CURRENT or BUILTIN if e.key == key), None)


def default_folder_name(e: "Event") -> str:
    return e.name.replace(" ", "-") + f"-{event_today().year}"


def event_today() -> date:
    """Today, or MCSI_EVENT_DATE=YYYY-MM-DD to preview an event on another day."""
    v = os.environ.get("MCSI_EVENT_DATE", "")
    try:
        return date.fromisoformat(v) if v else date.today()
    except ValueError:
        return date.today()


BUILTIN = [
    Event("halloween", "Pumpkin Loader", _("A pumpkin grows and spins. Happy Halloween!"), "#f97316", "🎃",
          [[10, 24, 11, 1]], "pumpkin-loader.jar", console_color="06", fx="gl:ev_halloween",
          headline=_("Pumpkin Loader has arrived for Halloween!")),
    Event("christmas", "Jingle Loader", _("A Christmas tree builds itself and the ornaments drop in."), "#22c55e", "🎄",
          [[12, 18, 12, 26]], "jingle-loader.jar", console_color="0A", fx="gl:ev_christmas",
          headline=_("Jingle Loader has arrived for Christmas!")),
    Event("newyear", "Firework Loader", _("Rockets fly up into the night sky and burst."), "#eab308", "🎆",
          [[12, 31, 1, 3]], "firework-loader.jar", console_color="0E", fx="gl:ev_newyear",
          headline=_("Firework Loader has arrived for the new year!")),
    Event("valentine", "Cocoa Loader", _("A heart chocolate that someone takes a bite of."), "#ec4899", "🍫",
          [[2, 10, 2, 15]], "cocoa-loader.jar", console_color="0D", fx="gl:ev_valentine",
          headline=_("Cocoa Loader has arrived for Valentine's Day!")),
    Event("aprilfools", "Prank Loader", _("Totally a real server. Nothing will explode."), "#ef4444", "🧨",
          [[4, 1, 4, 1]], "prank-loader.jar", console_color="0C", fx="gl:ev_aprilfools",
          headline=_("Prank Loader has arrived for April Fools' Day!")),
    Event("ufo", "UFO Loader", _("A UFO steals the menu... and gives it back. Probably."), "#a3e635", "🛸",
          [[7, 2, 7, 2]], "ufo-loader.jar", console_color="0A", fx="ufo",
          headline=_("UFO Loader has landed for World UFO Day!")),
]


def _localized(v, fallback: str) -> str:
    if isinstance(v, dict):
        return str(v.get(get_language()) or v.get("en") or fallback)
    return str(v) if v else fallback


def _from_json(d: dict, base: Event | None) -> Event | None:
    try:
        key = str(d["key"])
        e = Event(
            key=key,
            name=str(d.get("name") or (base.name if base else key)),
            desc=_localized(d.get("desc"), base.desc if base else ""),
            accent=str(d.get("accent") or (base.accent if base else "#a78bfa")),
            icon=str(d.get("icon") or (base.icon if base else "★")),
            windows=[list(map(int, w)) for w in d.get("windows") or (base.windows if base else [])],
            jar=str(d.get("jar") or (base.jar if base else f"{key}-loader.jar")),
            sha256=str(d.get("sha256") or ""),
            console_color=str(d.get("console_color") or (base.console_color if base else "0F")),
            headline=_localized(d.get("headline"), base.headline if base else ""),
            fx=str(d.get("fx") or (base.fx if base else "")),
            tag=str(d.get("tag") or (base.tag if base else "")),
        )
        if not e.windows or any(len(w) != 4 for w in e.windows):
            return None
        return e
    except (KeyError, TypeError, ValueError):
        return None


def merge(remote: list | None) -> list[Event]:
    """Built-in events, replaced/extended by the remote list (unknown or broken entries are skipped)."""
    out = {e.key: e for e in BUILTIN}
    for d in remote or []:
        if isinstance(d, dict) and not d.get("disabled"):
            e = _from_json(d, out.get(str(d.get("key"))))
            if e:
                out[e.key] = e
        elif isinstance(d, dict) and d.get("disabled") and d.get("key") in out:
            out.pop(d["key"])
    return list(out.values())


def cached() -> list[Event]:
    try:
        return merge(json.loads(CACHE.read_text(encoding="utf-8")).get("events"))
    except (OSError, ValueError, AttributeError):
        return merge(None)


def fetch() -> list[Event]:
    """Download the current events.json (falls back to the cache, then the built-in list)."""
    try:
        data = get_json(EVENTS_URL, timeout=8)
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            try:
                APP_DIR.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
            return merge(data["events"])
    except (NetError, OSError, ValueError):
        pass
    return cached()


def visible(events: list[Event], show_all: bool = False) -> list[Event]:
    return [e for e in events if show_all or e.active()]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_jar(e: Event, dest: Path, log=lambda m: None) -> str:
    """Put the event jar at ``dest``. Uses the bundled copy when it matches, otherwise downloads it."""
    local = BUNDLED / e.jar
    if local.is_file() and (not e.sha256 or _sha256(local) == e.sha256):
        shutil.copyfile(local, dest)
        return "bundled"
    try:
        download(e.jar_url, dest, sha256=e.sha256)
        return "download"
    except Exception as ex:  # offline, GitHub down, checksum mismatch...
        if local.is_file():
            log(_("Download failed ({0}), using the copy included with the app").format(ex))
            shutil.copyfile(local, dest)
            return "bundled"
        raise NetError(_("Could not get {0}: {1}").format(e.name, ex)) from ex


def install(e: Event, folder: Path, java: str = "java", log=lambda m: None) -> Path:
    """Install the event loader into ``folder``: the jar plus start.bat / start.sh. Returns the folder."""
    folder.mkdir(parents=True, exist_ok=True)
    src = get_jar(e, folder / e.jar, log)
    log(_("{0}: {1} ({2})").format(e.jar, _("downloaded") if src == "download" else _("included with the app"),
                                   e.jar_url if src == "download" else e.release_tag))
    title = e.name.replace("&", "").replace("|", "")
    java_win = f'"{java}"' if java and java != "java" else "java"
    bat = ["@echo off", "chcp 65001 >nul", f"title {title}", f"color {e.console_color}", "cd /d \"%~dp0\"",
           f"{java_win} -jar \"{e.jar}\"",
           "if errorlevel 1 (", "  echo.", "  echo Java was not found or the loader failed. Install Java 8+ and try again.",
           "  pause", ")"]
    (folder / "start.bat").write_bytes(("\r\n".join(bat) + "\r\n").encode("utf-8"))
    java_sh = f'"{java}"' if java and java != "java" else "java"
    sh = folder / "start.sh"
    sh.write_text("#!/usr/bin/env sh\ncd \"$(dirname \"$0\")\"\n"
                  f"exec {java_sh} -jar \"{e.jar}\"\n", encoding="utf-8")
    try:
        sh.chmod(0o755)
    except OSError:
        pass
    (folder / "README.txt").write_text(
        f"{e.name}\n\n" + _("This is a limited-time joke loader, not a real server. "
                            "Run start.bat (Windows) or start.sh (Mac/Linux) to see it.") + "\n",
        encoding="utf-8")
    return folder
