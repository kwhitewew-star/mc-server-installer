"""Network helpers: retries, certificate fallback, streaming downloads, checksum verification."""

from __future__ import annotations
from ..i18n import _

import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

# PaperMC requires a User-Agent that includes contact info.
USER_AGENT = "MCServerInstaller/3.0 (https://github.com/mc-server-installer)"

_ssl_ctx: Optional[ssl.SSLContext] = None


class Cancelled(Exception):
    """Raised when the user cancels."""


class NetError(Exception):
    """Human-readable network error."""


def _context() -> ssl.SSLContext:
    """Use the system certificate store, switching to certifi after a failure."""
    global _ssl_ctx
    if _ssl_ctx is None:
        _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


def _switch_to_certifi() -> bool:
    global _ssl_ctx
    try:
        import certifi  # type: ignore
    except ImportError:
        return False
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    return True


def _open(url: str, timeout: float, method: str = "GET"):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=timeout, context=_context())


def open_url(url: str, timeout: float = 30, retries: int = 3, method: str = "GET"):
    last: Exception | None = None
    tried_certifi = False
    for attempt in range(retries):
        try:
            return _open(url, timeout, method)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise NetError(f"HTTP {e.code}: {url}") from e
            last = e
        except urllib.error.URLError as e:
            last = e
            if isinstance(e.reason, ssl.SSLError) and not tried_certifi:
                tried_certifi = True
                if _switch_to_certifi():
                    continue
        except (TimeoutError, ConnectionError, OSError) as e:
            last = e
        time.sleep(0.6 * (attempt + 1))
    raise NetError(_("Could not connect to {0}: {1}").format(url, describe(last)))


def describe(e: Exception | None) -> str:
    if e is None:
        return _("Unknown error")
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code} {e.reason}"
    if isinstance(e, urllib.error.URLError):
        r = e.reason
        if isinstance(r, ssl.SSLError):
            return _("SSL certificate error ({0}). Run 'pip install certifi' and try again.").format(r)
        return _("Connection error ({0})").format(r)
    return f"{type(e).__name__}: {e}"


_cache: dict[str, tuple[float, bytes]] = {}


def get_bytes(url: str, timeout: float = 30, cache_sec: float = 300, retries: int = 3) -> bytes:
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < cache_sec:
        return hit[1]
    with open_url(url, timeout, retries=retries) as resp:
        data = resp.read()
    _cache[url] = (now, data)
    return data


def get_json(url: str, timeout: float = 30):
    data = get_bytes(url, timeout)
    try:
        return json.loads(data.decode("utf-8"))
    except ValueError as e:
        raise NetError(_("{0} did not return JSON").format(url)) from e


def clear_cache() -> None:
    _cache.clear()


def download(url: str, dest: Path, on_progress: Optional[Callable[[int, int], None]] = None,
             is_cancelled: Callable[[], bool] = lambda: False,
             sha256: str = "", sha1: str = "", md5: str = "", sha512: str = "") -> None:
    """Stream a download and verify the checksum if given. Deletes the .part file on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    hashers = {k: hashlib.new(k) for k, v in (("sha512", sha512), ("sha256", sha256), ("sha1", sha1), ("md5", md5))
               if v}
    try:
        with open_url(url, timeout=60) as resp, open(part, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if is_cancelled():
                    raise Cancelled()
                chunk = resp.read(128 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                for h in hashers.values():
                    h.update(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)
        expected = {"sha512": sha512, "sha256": sha256, "sha1": sha1, "md5": md5}
        for k, h in hashers.items():
            if h.hexdigest().lower() != expected[k].lower():
                raise NetError(_("{0} checksum ({1}) mismatch: the file is corrupted. Please try again.").format(dest.name, k))
        os.replace(part, dest)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise
