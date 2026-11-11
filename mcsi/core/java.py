"""Finding installed Java and installing the Adoptium (Temurin) JDK automatically."""

from __future__ import annotations
from ..i18n import _

import glob
import os
import platform
import re
import shutil
import subprocess
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .net import download

APP_DIR = Path.home() / ".mc_server_installer"
JAVA_DIR = APP_DIR / "java"
WINDOWS = os.name == "nt"
NO_WINDOW = 0x08000000 if WINDOWS else 0


@dataclass
class JavaInfo:
    path: str
    major: int
    version: str
    vendor: str

    @property
    def label(self) -> str:
        return f"Java {self.major}  ·  {self.vendor}  ·  {self.version}"


INCLUDE_LAUNCHER = {"on": True}


def _candidates() -> list[str]:
    exe = "java.exe" if WINDOWS else "java"
    found: list[str] = []
    w = shutil.which("java")
    if w:
        found.append(w)
    jh = os.environ.get("JAVA_HOME")
    if jh:
        found.append(os.path.join(jh, "bin", exe))
    found += glob.glob(str(JAVA_DIR / "*" / "**" / "bin" / exe), recursive=True)
    if WINDOWS:
        bases = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            bases.append(os.path.join(local, "Programs"))
        vendors = ["Java", "Eclipse Adoptium", "Eclipse Foundation", "Microsoft", "Zulu", "BellSoft",
                   "Amazon Corretto", "Semeru", "AdoptOpenJDK", "GraalVM", "ojdkbuild", "OpenJDK"]
        for b in filter(None, bases):
            for v in vendors:
                found += glob.glob(os.path.join(b, v, "*", "bin", exe))
        appdata = os.environ.get("APPDATA", "")
        rt_roots = []
        if appdata:
            rt_roots.append(os.path.join(appdata, ".minecraft", "runtime"))
        if local:
            rt_roots.append(os.path.join(local, "Packages", "Microsoft.4297127D64EC6_8wekyb3d8bbwe",
                                         "LocalCache", "Local", "runtime"))
        for r in (rt_roots if INCLUDE_LAUNCHER["on"] else []):  # Java bundled with the Minecraft Launcher
            found += glob.glob(os.path.join(r, "*", "windows-x64", "*", "bin", exe))
    else:
        found += glob.glob(f"/usr/lib/jvm/*/bin/{exe}")
        found += glob.glob(f"/Library/Java/JavaVirtualMachines/*/Contents/Home/bin/{exe}")
        found += glob.glob(os.path.expanduser(f"~/.sdkman/candidates/java/*/bin/{exe}"))
    seen, out = set(), []
    for p in found:
        try:
            rp = os.path.realpath(p)
        except OSError:
            continue
        if os.path.isfile(rp) and rp.lower() not in seen:
            seen.add(rp.lower())
            out.append(rp)
    return out


def probe(path: str) -> Optional[JavaInfo]:
    try:
        r = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=15,
                           creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
    except Exception:
        return None
    text = r.stderr + r.stdout
    m = re.search(r'version "([^"]+)"', text)
    if not m:
        return None
    ver = m.group(1)
    parts = re.findall(r"\d+", ver)
    if not parts:
        return None
    major = int(parts[0])
    if major == 1 and len(parts) > 1:
        major = int(parts[1])
    lines = [l for l in text.splitlines() if l.strip()]
    vendor = "OpenJDK"
    if len(lines) > 1:
        v = lines[1]
        for name in ("Temurin", "Microsoft", "Zulu", "Corretto", "GraalVM", "Liberica", "Semeru", "Oracle"):
            if name.lower() in v.lower():
                vendor = name
                break
        else:
            if "Java(TM)" in v:
                vendor = "Oracle"
    if ".minecraft" in path or "4297127D64EC6" in path:
        vendor += _(" (MC Launcher)")
    return JavaInfo(path, major, ver, vendor)


def find_javas() -> list[JavaInfo]:
    cands = _candidates()
    with ThreadPoolExecutor(max_workers=8) as ex:
        infos = [i for i in ex.map(probe, cands) if i]
    infos.sort(key=lambda j: (-j.major, j.path))
    return infos


def best_for(javas: list[JavaInfo], need: int) -> Optional[JavaInfo]:
    ok = [j for j in javas if j.major >= need]
    if not ok:
        return None
    # pick the closest to the required version (very new Java can break old mods)
    return min(ok, key=lambda j: j.major)


def adoptium_url(major: int) -> tuple[str, str]:
    sysname = platform.system().lower()
    os_name = {"windows": "windows", "darwin": "mac"}.get(sysname, "linux")
    arch = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}.get(arch, "x64")
    url = (f"https://api.adoptium.net/v3/binary/latest/{major}/ga/{os_name}/{arch}/jdk/hotspot/normal/eclipse"
           f"?project=jdk")
    return url, ("zip" if os_name == "windows" else "tar.gz")


def install_jdk(major: int, on_progress: Optional[Callable[[int, int], None]] = None,
                is_cancelled: Callable[[], bool] = lambda: False) -> JavaInfo:
    url, ext = adoptium_url(major)
    target = JAVA_DIR / f"temurin-{major}"
    archive = JAVA_DIR / f"temurin-{major}.{ext}"
    download(url, archive, on_progress, is_cancelled)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    if ext == "zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
    else:
        with tarfile.open(archive) as t:
            t.extractall(target, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(target)
    archive.unlink(missing_ok=True)
    exe = "java.exe" if WINDOWS else "java"
    hits = glob.glob(str(target / "**" / "bin" / exe), recursive=True)
    if not hits:
        raise RuntimeError(_("Extracted the archive but could not find the java executable."))
    if not WINDOWS:
        os.chmod(hits[0], 0o755)
    info = probe(hits[0])
    if not info:
        raise RuntimeError(_("Could not run the installed Java."))
    return info
