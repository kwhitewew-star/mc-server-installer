"""Installer engine (no Qt; reports progress through callbacks)."""

from __future__ import annotations
from ..i18n import _

import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import string
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import schema
from .java import NO_WINDOW, WINDOWS, probe
from .net import Cancelled, NetError, download, get_json
from .providers import PROVIDERS, Launch
from . import upnp, winfw
from .versions import props_moved_to_gamerules, uses_snake_gamerules

AIKAR = ["-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
         "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
         "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4", "-XX:G1MixedGCLiveThresholdPercent=90",
         "-XX:G1RSetUpdatingPauseTimePercent=5", "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem",
         "-XX:MaxTenuringThreshold=1"]
AIKAR_SMALL = ["-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M",
               "-XX:G1ReservePercent=20", "-XX:InitiatingHeapOccupancyPercent=15"]
AIKAR_BIG = ["-XX:G1NewSizePercent=40", "-XX:G1MaxNewSizePercent=50", "-XX:G1HeapRegionSize=16M",
             "-XX:G1ReservePercent=15", "-XX:InitiatingHeapOccupancyPercent=20"]

READY_RE = re.compile(r"Done \(\d|For help, type")
NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


@dataclass
class Plan:
    server: str
    mc: str
    build: str
    folder: str
    ram_gb: int
    java: str
    java_major: int
    values: dict = field(default_factory=dict)
    eula: bool = False
    addons: list = field(default_factory=list)


def split_names(s: str) -> list[str]:
    return [n for n in (x.strip() for x in re.split(r"[,\s]+", s or "")) if n]


def offline_uuid(name: str) -> str:
    """Same value as Java's UUID.nameUUIDFromBytes("OfflinePlayer:"+name)."""
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


def jvm_args(values: dict, ram: int, java_major: int) -> list[str]:
    xms = ram if values.get("jvm:xms_equal", True) else min(2, ram)
    args = [f"-Xms{xms}G", f"-Xmx{ram}G"]
    gc = values.get("jvm:gc", "aikar")
    if gc == "aikar":
        args += AIKAR + (AIKAR_BIG if ram > 12 else AIKAR_SMALL)
    elif gc == "zgc":
        args += ["-XX:+UseZGC"] + (["-XX:+ZGenerational"] if java_major in (21, 22) else [])
    if values.get("jvm:compact_headers") and java_major >= 25:
        args.append("-XX:+UseCompactObjectHeaders")
    if values.get("jvm:utf8", True):
        args += ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]
    extra = str(values.get("jvm:extra", "")).split()
    return args + extra


def prop_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def escape_prop(s: str) -> str:
    out = s.replace("\\", "\\\\").replace("\n", "\\n")
    return "".join(c if ord(c) < 128 else f"\\u{ord(c):04x}" for c in out)


def rule_commands(values: dict, mc: str) -> list[str]:
    """Build commands only for game rules that differ from the default."""
    snake = uses_snake_gamerules(mc)
    moved = props_moved_to_gamerules(mc)
    cmds = []
    for s in schema.RULES + [p for p in schema.PROPS if p.rule_new or p.rule_old]:
        if s in schema.PROPS and not moved:
            continue  # old versions already got it through server.properties
        v = values.get(s.key, s.default)
        if v == s.default:
            continue
        name = s.rule_new if snake else s.rule_old
        if not name:
            continue
        val = v
        if not snake and s.invert_old and isinstance(v, bool):
            val = not v
        cmds.append(f"gamerule {name} {prop_value(val)}")
    return cmds


class Installer:
    def __init__(self, plan: Plan, log: Callable[[str], None], progress: Callable[[int], None],
                 stage: Callable[[int, str], None], is_cancelled: Callable[[], bool]):
        self.plan = plan
        self.folder = Path(plan.folder).expanduser()
        self.java = plan.java
        self.log = log
        self._progress = progress
        self._stage = stage
        self.is_cancelled = is_cancelled
        self._span = (0, 100)
        self._proc: Optional[subprocess.Popen] = None
        self.summary: list[str] = []
        self.forward: Optional[upnp.ForwardResult] = None
        self.rules = upnp.port_rules(plan.values, [str(a.get("title", "")) for a in plan.addons])

    # ---- Progress ----
    def stage(self, idx: int, text: str, start: int, end: int) -> None:
        self._span = (start, end)
        self._stage(idx, text)
        self._progress(start)

    def sub(self, frac: float) -> None:
        a, b = self._span
        self._progress(int(a + (b - a) * max(0.0, min(1.0, frac))))

    def check(self) -> None:
        if self.is_cancelled():
            raise Cancelled()

    # ---- Ctx implementation (used by providers) ----
    def download(self, url, dest, sha256="", sha1="", md5=""):
        self.log(f"↓ {url}")
        download(url, Path(dest), lambda d, t: self.sub(d / t if t else 0.5), self.is_cancelled,
                 sha256=sha256, sha1=sha1, md5=md5, log=self.log)
        if sha256 or sha1 or md5:
            self.log(_("  ✓ Checksum verified"))

    def run(self, args, cwd):
        self.log("$ " + " ".join(str(a) for a in args))
        self.sub(0.5)
        self._proc = subprocess.Popen(
            [str(a) for a in args], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=NO_WINDOW)
        assert self._proc.stdout
        for line in self._proc.stdout:
            self.log("  " + line.rstrip())
            if self.is_cancelled():
                self._proc.kill()
                raise Cancelled()
        code = self._proc.wait()
        self._proc = None
        if code != 0:
            raise NetError(_("Command failed (exit code {0}). Check the log above.").format(code))

    def kill(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except OSError:
                pass

    # ---- Main flow ----
    def execute(self) -> Launch:
        p, v = self.plan, self.plan.values
        prov = PROVIDERS[p.server]
        self.folder.mkdir(parents=True, exist_ok=True)

        self.stage(0, _("Checking Java"), 0, 4)
        info = probe(self.java) if self.java else None
        if not info:
            raise NetError(_("Cannot run the selected Java. Go back and choose another Java."))
        self.log(f"Java: {info.label}  ({info.path})")
        self.java = info.path

        self.stage(1, _("Downloading {0} {1}").format(prov.name, p.mc), 4, 52 if p.addons else 60)
        launch = prov.install(self, p.mc, p.build)
        self.check()

        if p.addons:
            self.stage(2, _("Downloading {0} mods/plugins").format(len(p.addons)), 52, 60)
            self.install_addons()
            self.check()

        self.stage(3, _("Writing config files"), 60, 66)
        self.write_properties()
        (self.folder / "eula.txt").write_text(
            f"#Accepted in MC Server Installer {datetime.now():%Y-%m-%d %H:%M}\neula=true\n", encoding="utf-8")
        args = jvm_args(v, p.ram_gb, info.major)
        self.write_scripts(launch, args)
        self.check()

        self.stage(4, _("Preparing extras"), 66, 72)
        self.write_extras()
        first = bool(v.get("manage:first_run", True))
        if not first:
            self.write_player_lists()
        self.check()

        if first:
            self.stage(5, _("First run (world generation)"), 72, 95)
            self.first_run(launch, args)
        fw_auto = WINDOWS and v.get("manage:firewall_auto", True)
        if v.get("manage:upnp", True) or fw_auto:
            self.stage(6, _("Port forwarding · firewall"), 95, 99)
            fw_ok = winfw.ensure_rules([(p_, pr) for p_, pr, _why in self.rules], self.log) if fw_auto else None
            if v.get("manage:upnp", True):
                self.forward_ports()
            if self.forward is not None:
                self.forward.firewall = fw_ok
        self.stage(7, _("Finishing"), 99, 100)
        (self.folder / "mcsi_install.json").write_text(json.dumps({
            "server": p.server, "mc": p.mc, "build": p.build, "java": self.java, "ram_gb": p.ram_gb,
            "launch": launch.__dict__, "installed": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self._progress(100)
        return launch

    # ---- Mods / plugins / datapacks ----
    def install_addons(self) -> None:
        level = str(self.plan.values.get("level-name", "world")) or "world"
        dirs = {"mod": self.folder / "mods", "plugin": self.folder / "plugins",
                "datapack": self.folder / level / "datapacks"}
        n = len(self.plan.addons)
        for i, d in enumerate(self.plan.addons):
            self.check()
            kind = d.get("kind", "mod")
            target = dirs.get(kind, self.folder / "mods")
            target.mkdir(parents=True, exist_ok=True)
            name = d.get("filename") or "addon.jar"
            name = re.sub(r'[\\/:*?"<>|]', "_", name)
            if d.get("local_path"):
                src = Path(d["local_path"])
                if not src.is_file():
                    self.log(_("  ✕ File missing, skipped: {0}").format(src))
                    continue
                shutil.copyfile(src, target / name)
                self.log(_("  + {0}/{1} (local file)").format(target.name, name))
            else:
                self.log(f"  + {target.name}/{name}  ({d.get('title')} {d.get('version_number', '')})")
                a, b = self._span
                self._span = (a + (b - a) * i / n, a + (b - a) * (i + 1) / n)
                download(d["url"], target / name, lambda x, t: self.sub(x / t if t else 0.5), self.is_cancelled,
                         sha512=d.get("sha512", ""), sha1="" if d.get("sha512") else d.get("sha1", ""))
                self._span = (a, b)
        self.summary.append(_("Installed {0} mods/plugins/datapacks").format(n))

    # ---- server.properties ----
    def write_properties(self) -> None:
        v = self.plan.values
        path = self.folder / "server.properties"
        merged: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    k, _x, val = s.partition("=")
                    merged[k.strip()] = val
        for s in schema.PROPS:
            val = v.get(s.key, s.default)
            if s.key == "management-server-secret":
                if not v.get("management-server-enabled"):
                    continue  # let the server generate it
                if not re.fullmatch(r"[A-Za-z0-9]{40}", str(val)):
                    val = "".join(secrets.choice(string.ascii_letters + string.digits) for _x in range(40))
                    self.summary.append(_("Management API secret: {0}").format(val))
            merged[s.key] = escape_prop(prop_value(val))
        body = "\n".join(f"{k}={val}" for k, val in merged.items())
        path.write_text(f"#Minecraft server properties\n#Written by MC Server Installer "
                        f"{datetime.now():%Y-%m-%d %H:%M}\n{body}\n", encoding="utf-8")
        self.log(_("Wrote server.properties ({0} keys)").format(len(merged)))

    # ---- Launch scripts ----
    def java_line(self, launch: Launch, args: list[str], windows: bool) -> str:
        java = f'"{self.java}"' if windows else f'"{self.java}"'
        nogui = " nogui" if self.plan.values.get("launch:nogui", True) else ""
        if launch.kind == "args":
            return f"{java} @user_jvm_args.txt {launch.java_args(windows)[0]}{nogui}"
        return f"{java} {' '.join(args)} -jar {launch.jar}{nogui}"

    def write_scripts(self, launch: Launch, args: list[str]) -> None:
        v = self.plan.values
        if launch.kind == "args":
            (self.folder / "user_jvm_args.txt").write_text(
                "# MC Server Installer\n" + "\n".join(args) + "\n", encoding="utf-8")
        title = re.sub(r"[&|<>^\"]", "", str(v.get("launch:title", "Minecraft Server"))) or "Minecraft Server"
        delay = int(v.get("launch:restart_delay", 10))
        restart = bool(v.get("launch:auto_restart"))
        bat = ["@echo off", "chcp 65001 >nul", f"title {title}", 'cd /d "%~dp0"']
        if restart:
            bat += [":loop", self.java_line(launch, args, True),
                    f"echo Server stopped. Restarting in {delay}s (press Ctrl+C to cancel)...",
                    f"timeout /t {delay} >nul", "goto loop"]
        else:
            bat += [self.java_line(launch, args, True), "pause"]
        (self.folder / "start.bat").write_bytes(("\r\n".join(bat) + "\r\n").encode("utf-8"))
        sh = ["#!/usr/bin/env bash", 'cd "$(dirname "$0")" || exit 1']
        if restart:
            sh += ["while true; do", "  " + self.java_line(launch, args, False),
                   f'  echo "Server stopped. Restarting in {delay}s (Ctrl+C to cancel)..."',
                   f"  sleep {delay}", "done"]
        else:
            sh += [self.java_line(launch, args, False)]
        p = self.folder / "start.sh"
        p.write_bytes(("\n".join(sh) + "\n").encode("utf-8"))
        if not WINDOWS:
            os.chmod(p, 0o755)
        self.log(_("Wrote start.bat / start.sh"))

    # ---- Extras ----
    def write_extras(self) -> None:
        v = self.plan.values
        icon = str(v.get("manage:icon", "")).strip()
        if icon and Path(icon).is_file():
            shutil.copyfile(icon, self.folder / "server-icon.png")
            self.log(_("Copied server-icon.png"))
        if v.get("manage:backup", True):
            level = str(v.get("level-name", "world")).replace("'", "")
            keep = int(v.get("manage:backup_keep", 10))
            ps = [
                "$ErrorActionPreference = 'Stop'", "Set-Location $PSScriptRoot", f"$level = '{level}'",
                "$t = @($level, \"${level}_nether\", \"${level}_the_end\") | Where-Object { Test-Path $_ }",
                "if (-not $t) { Write-Host 'No world folder yet.'; exit 1 }",
                "New-Item -ItemType Directory -Force backups | Out-Null",
                "$name = 'backups/' + $level + '_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.zip'",
                "Write-Host 'Tip: stop the server (or run save-off) before backing up.'",
                "Compress-Archive -Path $t -DestinationPath $name -CompressionLevel Optimal",
                "Write-Host \"Saved $name\"",
                f"Get-ChildItem backups -Filter *.zip | Sort-Object LastWriteTime -Descending | "
                f"Select-Object -Skip {keep} | Remove-Item",
            ]
            (self.folder / "backup.ps1").write_text("\r\n".join(ps) + "\r\n", encoding="utf-8-sig")
            (self.folder / "backup.bat").write_bytes(
                b'@echo off\r\ncd /d "%~dp0"\r\npowershell -NoProfile -ExecutionPolicy Bypass -File '
                b'"%~dp0backup.ps1"\r\npause\r\n')
            sh = ("#!/usr/bin/env bash\ncd \"$(dirname \"$0\")\" || exit 1\nmkdir -p backups\n"
                  f"L='{level}'\nT=$(ls -d \"$L\" \"${{L}}_nether\" \"${{L}}_the_end\" 2>/dev/null)\n"
                  "[ -z \"$T\" ] && { echo 'No world folder yet.'; exit 1; }\n"
                  "tar -czf \"backups/${L}_$(date +%Y%m%d_%H%M%S).tar.gz\" $T && echo saved\n"
                  f"ls -1t backups/*.tar.gz | tail -n +{keep + 1} | xargs -r rm --\n")
            bp = self.folder / "backup.sh"
            bp.write_text(sh, encoding="utf-8")
            if not WINDOWS:
                os.chmod(bp, 0o755)
            self.log(_("Wrote backup.bat / backup.sh"))
        if v.get("manage:firewall", True):
            fw = ["@echo off", "net session >nul 2>&1 || (powershell -NoProfile -Command \"Start-Process "
                  "'%~f0' -Verb RunAs\" & exit /b)"]
            for rport, proto, _why in self.rules:
                fw.append(winfw.add_command(rport, proto))
            fw.append("pause")
            (self.folder / "open_firewall.bat").write_bytes(("\r\n".join(fw) + "\r\n").encode("utf-8"))
            self.log(_("Wrote open_firewall.bat (run as administrator)"))
        if v.get("manage:shortcut") and WINDOWS:
            name = re.sub(r'[\\/:*?"<>|]', "", str(v.get("launch:title", "Minecraft Server"))) or "MC Server"
            target = str(self.folder / "start.bat").replace("'", "''")
            wd = str(self.folder).replace("'", "''")
            cmd = ("$d=[Environment]::GetFolderPath('Desktop');"
                   f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\\{name}.lnk\");"
                   f"$s.TargetPath='{target}';$s.WorkingDirectory='{wd}';$s.Save()")
            try:
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], timeout=30,
                               creationflags=NO_WINDOW, capture_output=True)
                self.log(_("Created desktop shortcut"))
            except Exception as e:
                self.log(_("Could not create shortcut: {0}").format(e))

    def write_player_lists(self) -> None:
        v = self.plan.values
        online = bool(v.get("online-mode", True))

        def resolve(name: str) -> Optional[dict]:
            if not NAME_RE.match(name):
                self.log(_("  Invalid player name, skipped: {0}").format(name))
                return None
            if not online:
                return {"uuid": offline_uuid(name), "name": name}
            try:
                d = get_json(f"https://api.mojang.com/users/profiles/minecraft/{name}")
                u = d["id"]
                return {"uuid": f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}", "name": d["name"]}
            except Exception:
                self.log(_("  {0}: no premium account found, skipped").format(name))
                return None

        ops = [r for r in map(resolve, split_names(v.get("manage:ops", ""))) if r]
        wl = [r for r in map(resolve, split_names(v.get("manage:whitelist", ""))) if r]
        level = int(v.get("op-permission-level", 4))
        if ops:
            (self.folder / "ops.json").write_text(json.dumps(
                [dict(o, level=level, bypassesPlayerLimit=False) for o in ops], indent=2), encoding="utf-8")
            self.log(f"ops.json: {', '.join(o['name'] for o in ops)}")
        names = {w["name"] for w in wl}
        wl += [o for o in ops if o["name"] not in names]
        if wl:
            (self.folder / "whitelist.json").write_text(json.dumps(wl, indent=2), encoding="utf-8")
            self.log(_("whitelist.json: {0} players").format(len(wl)))

    # ---- Port forwarding ----
    def forward_ports(self) -> None:
        """Ask the router to open the needed ports via UPnP. Never fails the install."""
        rules = [(p, proto) for p, proto, _why in self.rules]
        title = str(self.plan.values.get("launch:title", "Minecraft Server")) or "Minecraft Server"
        self.forward = upnp.forward_ports(rules, title[:40], self.log)
        if self.forward.ok:
            self.log(_("✓ Port forwarding done ({0}). External address: {1}").format(
                upnp.methods_text(self.forward.methods), self.forward.external_ip))
        else:
            for e in self.forward.errors:
                self.log("  " + e)
            self.log(_("Automatic port forwarding did not fully work. See the port forwarding guide on the last page."))

    # ---- First run ----
    def first_run(self, launch: Launch, args: list[str], timeout: float = 900) -> None:
        v = self.plan.values
        if launch.kind == "args":
            cmd = [self.java, "@user_jvm_args.txt", launch.java_args(WINDOWS)[0], "nogui"]
        else:
            cmd = [self.java] + args + ["-jar", launch.jar, "nogui"]
        self.log("$ " + " ".join(cmd))
        self._proc = proc = subprocess.Popen(
            cmd, cwd=str(self.folder), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=NO_WINDOW)
        lines: "queue.Queue[Optional[str]]" = queue.Queue()

        def reader():
            assert proc.stdout
            for ln in proc.stdout:
                lines.put(ln.rstrip())
            lines.put(None)

        threading.Thread(target=reader, daemon=True).start()
        tail: list[str] = []
        start = time.time()
        ready = False

        def pump(until: Callable[[], bool], limit: float) -> bool:
            nonlocal ready
            end = time.time() + limit
            while time.time() < end:
                if self.is_cancelled():
                    proc.kill()
                    raise Cancelled()
                try:
                    ln = lines.get(timeout=0.2)
                except queue.Empty:
                    if not ready:
                        self.sub(min(0.85, (time.time() - start) / 120))
                    continue
                if ln is None:
                    return False
                self.log("  │ " + ln)
                tail.append(ln)
                del tail[:-25]
                if not ready and READY_RE.search(ln):
                    ready = True
                if until():
                    return True
            return False

        pump(lambda: ready, timeout)
        if not ready:
            proc.kill()
            hint = "\n".join(tail[-8:])
            if "UnsupportedClassVersionError" in hint or "requires running the server with Java" in hint:
                raise NetError(_("The server did not start because Java is too old. Choose a newer Java.\n") + hint)
            raise NetError(_("The server did not start correctly. Last log lines:\n") + hint)
        self.log(_("✓ The server started correctly. Applying settings."))
        self.sub(0.88)
        cmds = rule_commands(v, self.plan.mc)
        ops = [n for n in split_names(v.get("manage:ops", "")) if NAME_RE.match(n)]
        wl = [n for n in split_names(v.get("manage:whitelist", "")) if NAME_RE.match(n)]
        cmds += [f"op {n}" for n in ops]
        cmds += [f"whitelist add {n}" for n in dict.fromkeys(wl + ops)]
        applied = 0
        for c in cmds:
            self.log(f"  > {c}")
            assert proc.stdin
            proc.stdin.write(c + "\n")
            proc.stdin.flush()
            n0 = len(tail)
            pump(lambda: len(tail) > n0, 3)
            if tail and re.search(r"now set to|Made .* a server operator|Added .* to the whitelist|"
                                  r"already|is already", tail[-1]):
                applied += 1
        if cmds:
            self.summary.append(_("First run applied {0}/{1} commands").format(applied, len(cmds)))
        assert proc.stdin
        proc.stdin.write("save-all\nstop\n")
        proc.stdin.flush()
        self.sub(0.95)
        pump(lambda: proc.poll() is not None, 120)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        self._proc = None
        self.log(_("✓ First run finished, server stopped cleanly."))
