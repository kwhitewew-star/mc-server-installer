"""App state, settings persistence and async helpers."""

from __future__ import annotations
from ..i18n import _

import ctypes
import json
import os
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from ..core import schema
from ..core.java import APP_DIR, JavaInfo

CONFIG = APP_DIR / "config.json"

MODE_STEPS = {
    "quick": ["welcome", "server", "version", "addons", "resource", "summary", "install", "done"],
    "standard": ["welcome", "server", "version", "addons", "resource", "props", "rules", "manage", "summary",
                 "install", "done"],
    "detailed": ["welcome", "server", "version", "addons", "resource", "props", "rules", "manage", "summary",
                 "install", "done"],
}
STEP_NAMES = {"welcome": _("Start"), "server": _("Server type"), "version": _("Version"), "addons": _("Mods · plugins"), "resource": _("Location · performance"),
              "props": _("Server settings"), "rules": _("Game rules"), "manage": _("Manage & launch"), "summary": _("Review"),
              "install": _("Install"), "done": _("Done")}


@dataclass
class State:
    mode: str = "standard"
    server: str = "paper"
    event: str = ""                                   # limited-time event loader picked instead (not saved)
    mc: str = ""
    build: str = ""
    snapshots: bool = False
    folder: str = ""
    folder_custom: bool = False
    ram: int = 4
    java: str = ""
    eula: bool = False
    fx: str = "high"
    addons: list = field(default_factory=list)
    addons_ctx: list = field(default_factory=list)
    app: dict = field(default_factory=dict)
    values: dict = field(default_factory=schema.defaults)
    javas: list = field(default_factory=list)       # not saved
    java_need: int = 0                                # not saved

    def save(self) -> None:
        d = asdict(self)
        d.pop("javas", None)
        d.pop("java_need", None)
        d.pop("event", None)
        d["values"] = {k: v for k, v in self.values.items() if k in schema.BY_KEY}
        if not self.app.get("remember", True):
            d = {"app": self.app, "fx": self.fx, "mode": self.mode}
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    @classmethod
    def load(cls) -> "State":
        s = cls()
        try:
            d = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return s
        s.app = dict(d.get("app", {})) if isinstance(d.get("app"), dict) else {}
        if "fx" in d:
            s.fx = d["fx"]
        if not s.app.get("remember", True):  # remember off: keep only app settings and effects
            s.mode = d.get("mode", s.mode)
            s.values["manage:first_run"] = bool(s.app.get("first_run_default", True))
            return s
        for k in ("mode", "server", "mc", "build", "snapshots", "folder", "folder_custom", "ram", "java",
                  "addons", "addons_ctx"):
            if k in d:
                setattr(s, k, d[k])
        for k, v in d.get("values", {}).items():
            spec = schema.BY_KEY.get(k)
            if spec and isinstance(v, type(spec.default)):
                if spec.type == "int" and not isinstance(v, bool):
                    v = max(spec.min, min(spec.max, v))     # e.g. a port saved before limits existed
                s.values[k] = v
        if s.mode not in MODE_STEPS:
            s.mode = "standard"
        return s

    def changed_count(self) -> int:
        return sum(1 for s in schema.ALL if self.values.get(s.key, s.default) != s.default)


BASE_FOLDER = {"path": ""}


def event_folder(e) -> str:
    """Default folder for an event loader: next to the normal server folders."""
    from ..core.events import default_folder_name
    return str(Path(default_folder("x", "")).parent / default_folder_name(e))


def default_folder(server: str, mc: str) -> str:
    name = f"{server}-{mc}" if mc else server
    if BASE_FOLDER["path"]:
        return str(Path(BASE_FOLDER["path"]).expanduser() / name)
    base = Path.home() / "Desktop"
    if not base.is_dir():
        base = Path.home()
    return str(base / "MinecraftServers" / name)


def total_ram_gb() -> int:
    try:
        if platform.system() == "Windows":
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            b = m.ullTotalPhys
        elif platform.system() == "Darwin":
            b = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
        else:
            with open("/proc/meminfo") as f:
                b = int(f.readline().split()[1]) * 1024
        return max(1, round(b / 1024 ** 3))
    except Exception:
        return 8


def recommended_ram(total: int) -> int:
    return max(1, min(round(total / 2), 32))


def local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def open_path(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ------------------------------------------------------------ Async
class _Sig(QObject):
    ok = pyqtSignal(object)
    err = pyqtSignal(str)
    prog = pyqtSignal(int, int)


class _Task(QRunnable):
    def __init__(self, fn: Callable, sig: _Sig):
        super().__init__()
        self.fn, self.sig = fn, sig

    def run(self):
        try:
            self.sig.ok.emit(self.fn(self.sig))
        except Exception as e:  # noqa: BLE001
            self.sig.err.emit(str(e) or type(e).__name__)


_alive: set = set()


_icon_pool: "QThreadPool | None" = None


def icon_pool() -> QThreadPool:
    """Separate thread pool for low-priority work like icons (so search/add jobs never queue behind it)."""
    global _icon_pool
    if _icon_pool is None:
        _icon_pool = QThreadPool()
        _icon_pool.setMaxThreadCount(3)
    return _icon_pool


def run_async(fn: Callable, ok: Callable, err: Callable, prog: Callable | None = None,
              pool: "QThreadPool | None" = None) -> None:
    """Run fn(sig) on the thread pool and deliver the result to a main-thread callback."""
    sig = _Sig()
    _alive.add(sig)

    def done_ok(v):
        _alive.discard(sig)
        ok(v)

    def done_err(m):
        _alive.discard(sig)
        err(m)

    sig.ok.connect(done_ok)
    sig.err.connect(done_err)
    if prog:
        sig.prog.connect(prog)
    (pool or QThreadPool.globalInstance()).start(_Task(fn, sig))


def java_label(j: JavaInfo) -> str:
    return j.label
