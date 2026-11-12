"""Running small helper commands and reading their output safely.

On Windows the output of netsh, PowerShell or java can be in the console code page (cp949 on Korean
Windows, cp932 on Japanese...) or in UTF-8, depending on the program and the user's settings. Reading it
with Python's default text decoding crashes the reader thread on the first byte that does not fit
("'cp949' codec can't decode byte 0x80"), and the result is lost. So: read bytes, then decode.
"""

from __future__ import annotations

import locale
import platform
import subprocess

NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0

# Put at the start of PowerShell scripts so their output is UTF-8 whatever the console code page is
PS_UTF8 = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8\n"


def decode(data: bytes | None) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for enc in (locale.getpreferredencoding(False), "mbcs" if platform.system() == "Windows" else "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def run(cmd: list[str], timeout: float = 30, **kw) -> subprocess.CompletedProcess:
    """subprocess.run that never chokes on the output encoding; stdout/stderr come back as str."""
    kw.setdefault("creationflags", NO_WINDOW)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)
    r.stdout, r.stderr = decode(r.stdout), decode(r.stderr)
    return r
