"""Windows Defender Firewall: inbound rules for the server ports.

Like game and server installers do, the rules are added with ``netsh advfirewall`` as administrator.
If the app is not elevated, one UAC prompt runs all of them at once (a small temporary .cmd started with
``Start-Process -Verb RunAs``); rules that already exist are skipped, so re-installs don't ask again.
Rules are checked with ``Get-NetFirewallRule`` (exact display name), which does not need admin rights.
The rule names match open_firewall.bat.
"""

from __future__ import annotations

import base64
import ctypes
import os
import platform
import subprocess
import tempfile
from typing import Callable

from ..i18n import _
from . import proc
from .proc import PS_UTF8

NO_WINDOW = 0x08000000


def rule_name(port: int, proto: str) -> str:
    return f"Minecraft Server {port} {proto}"


def add_command(port: int, proto: str) -> str:
    return (f'netsh advfirewall firewall add rule name="{rule_name(port, proto)}" '
            f"dir=in action=allow protocol={proto} localport={port}")


def available() -> bool:
    return platform.system() == "Windows"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())     # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False


def _ps(script: str, timeout: float = 60) -> str:
    """Run a PowerShell script (passed encoded, so no quoting problems) and return its output."""
    enc = base64.b64encode((PS_UTF8 + script).encode("utf-16-le")).decode()
    r = proc.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], timeout=timeout)
    return r.stdout + r.stderr


def existing(rules: list[tuple[int, str]]) -> set[tuple[int, str]]:
    """Which of the rules already exist (enabled inbound allow rules with our exact name)."""
    if not available() or not rules:
        return set()
    lines = [f"if (Get-NetFirewallRule -DisplayName '{rule_name(p, pr)}' -ErrorAction SilentlyContinue) "
             f"{{ 'HAVE {p}/{pr}' }}" for p, pr in rules]
    try:
        out = _ps("\n".join(lines), 40)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {(p, pr) for p, pr in rules if f"HAVE {p}/{pr}" in out}


def ensure_rules(rules: list[tuple[int, str]], log: Callable[[str], None] = lambda m: None) -> bool:
    """Make sure every (port, protocol) has an inbound allow rule. Returns True when all exist."""
    if not available():
        return False
    missing = [r for r in rules if r not in existing(rules)]
    if not missing:
        log(_("Windows Firewall: rules already exist"))
        return True
    cmd = tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False, encoding="utf-8")
    try:
        cmd.write("@echo off\r\n" + "\r\n".join(add_command(p, pr) for p, pr in missing) + "\r\n")
        cmd.close()
        if is_admin():
            proc.run(["cmd", "/c", cmd.name], timeout=60)
        else:
            log(_("Windows Firewall: asking for administrator permission (UAC)..."))
            path = cmd.name.replace("'", "''")
            out = _ps(f"try {{ $p = Start-Process -FilePath '{path}' -Verb RunAs -WindowStyle Hidden -Wait -PassThru; "
                      f"'EXIT ' + $p.ExitCode }} catch {{ 'CANCELLED ' + $_.Exception.Message }}", 300)
            if "CANCELLED" in out:
                log(_("Windows Firewall: the administrator prompt was declined or closed."))
    except (OSError, subprocess.SubprocessError) as e:
        log(_("Windows Firewall: {0}").format(e))
    finally:
        try:
            os.unlink(cmd.name)
        except OSError:
            pass
    have = existing(rules)
    for p, pr in missing:
        if (p, pr) in have:
            log(_("Windows Firewall: allowed {0}/{1}").format(p, pr))
    still = [r for r in missing if r not in have]
    if still:
        log(_("Windows Firewall: not added (permission declined?). Run open_firewall.bat as administrator."))
    return not still
