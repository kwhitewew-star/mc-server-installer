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


def _open(url: str, timeout: float, method: str = "GET", headers: Optional[dict] = None):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout, context=_context())


def open_url(url: str, timeout: float = 30, retries: int = 3, method: str = "GET", headers: Optional[dict] = None):
    last: Exception | None = None
    tried_certifi = False
    for attempt in range(retries):
        try:
            return _open(url, timeout, method, headers)
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


STALL_SEC = 20          # no data for this long -> reconnect and resume
RESUMES = 5


def download(url: str, dest: Path, on_progress: Optional[Callable[[int, int], None]] = None,
             is_cancelled: Callable[[], bool] = lambda: False,
             sha256: str = "", sha1: str = "", md5: str = "", sha512: str = "",
             log: Optional[Callable[[str], None]] = None) -> None:
    """Stream a download and verify the checksum if given. Deletes the .part file on failure.

    Like download managers do: if the server stops sending (STALL_SEC without data) or the connection
    drops, it reconnects and continues where it stopped (HTTP Range), up to RESUMES times. Progress and
    speed go to ``log`` every ~10%."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    hashers = {k: hashlib.new(k) for k, v in (("sha512", sha512), ("sha256", sha256), ("sha1", sha1), ("md5", md5))
               if v}
    done, total, resumes = 0, 0, 0
    t0 = time.time()
    next_log = 0.1
    try:
        with open(part, "wb") as f:
            while True:
                headers = {"Range": f"bytes={done}-"} if done else None
                try:
                    resp = open_url(url, timeout=STALL_SEC, headers=headers)
                except NetError:
                    if not done or resumes >= RESUMES:
                        raise
                    resumes += 1
                    continue
                with resp:
                    if done and getattr(resp, "status", 200) != 206:   # server ignores Range: start over
                        done = 0
                        f.seek(0)
                        f.truncate()
                        hashers = {k: hashlib.new(k) for k in hashers}
                    if not total:
                        length = int(resp.headers.get("Content-Length") or 0)
                        total = length + done if length else 0
                    try:
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
                            if log and total and done / total >= next_log:
                                speed = done / max(0.1, time.time() - t0)
                                left = (total - done) / max(1.0, speed)
                                eta = _("{0} min").format(round(left / 60)) if left >= 90 else _("{0} s").format(round(left))
                                log(_("  {0:.1f} / {1:.1f} MB ({2:.2f} MB/s · about {3} left)").format(
                                    done / 1048576, total / 1048576, speed / 1048576, eta))
                                next_log += 0.1
                    except (TimeoutError, ConnectionError, OSError, urllib.error.URLError) as e:
                        if resumes >= RESUMES:
                            raise NetError(_("Download of {0} stopped: {1}").format(dest.name, describe(e))) from e
                        resumes += 1
                        if log:
                            log(_("  The server stopped sending ({0}). Reconnecting and continuing from {1:.1f} MB "
                                  "({2}/{3})...").format(describe(e), done / 1048576, resumes, RESUMES))
                        continue
                if total and done < total:              # connection closed early
                    if resumes >= RESUMES:
                        raise NetError(_("Download of {0} stopped: {1}").format(
                            dest.name, _("connection closed early")))
                    resumes += 1
                    if log:
                        log(_("  Connection closed early. Continuing from {0:.1f} MB ({1}/{2})...").format(
                            done / 1048576, resumes, RESUMES))
                    continue
                break
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
