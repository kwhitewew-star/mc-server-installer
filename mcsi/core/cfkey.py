"""Where the CurseForge API key comes from.

Like Prism Launcher / GDLauncher, the official builds carry the app's own CurseForge API key (applied for at
console.curseforge.com as a third-party app). It is never in the source repository: the release workflow
writes it into ``_cf_embedded.py`` from the ``CF_API_KEY`` secret just before PyInstaller runs, and the
build script deletes that file again afterwards.

Order: the user's own key (modpack window) → ``MCSI_CF_KEY`` environment variable → the built-in key.
People running from source without a key can still install CurseForge **server packs** and paste a key.
"""

from __future__ import annotations

import base64
import os

ENV = "MCSI_CF_KEY"
_MASK = b"mc-server-installer"
_user = ""


def _unmask(s: str) -> str:
    try:
        raw = base64.b64decode(s.encode())
    except ValueError:
        return ""
    return bytes(b ^ _MASK[i % len(_MASK)] for i, b in enumerate(raw)).decode("utf-8", "replace")


def mask(key: str) -> str:
    """Light obfuscation for the built-in key (keeps it out of plain-text greps of the .exe; not secrecy)."""
    raw = key.encode()
    return base64.b64encode(bytes(b ^ _MASK[i % len(_MASK)] for i, b in enumerate(raw))).decode()


def builtin() -> str:
    try:
        from ._cf_embedded import KEY  # type: ignore  # written by scripts/build_exe.py
    except ImportError:
        return ""
    return _unmask(KEY).strip()


def set_user(key: str) -> None:
    global _user
    _user = (key or "").strip()


def get(user: str = "") -> str:
    return (user or "").strip() or _user or os.environ.get(ENV, "").strip() or builtin()


def source(user: str = "") -> str:
    """'user' | 'env' | 'builtin' | '' — where get() would take the key from."""
    if (user or "").strip() or _user:
        return "user"
    if os.environ.get(ENV, "").strip():
        return "env"
    return "builtin" if builtin() else ""


def headers_for(url: str) -> dict:
    """CurseForge asks downloaders to send their key to its CDN too (x-api-key on edge.forgecdn.net)."""
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if host == "forgecdn.net" or host.endswith(".forgecdn.net"):
        k = get()
        if k:
            return {"x-api-key": k}
    return {}
