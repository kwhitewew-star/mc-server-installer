"""Checks GitHub for a newer release of the installer."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import __version__
from .events import REPO
from .net import get_json

LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"


@dataclass
class Release:
    version: str        # "1.0.3"
    url: str            # release page
    notes: str          # release notes (markdown)


def parse_version(v: str) -> tuple:
    nums = re.findall(r"\d+", v.split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def latest() -> Release | None:
    """The newest published (non-pre) release, or None if it is not newer than this build."""
    d = get_json(LATEST_API, timeout=8)
    tag = str(d.get("tag_name", "")).lstrip("vV")
    if not tag or d.get("draft") or d.get("prerelease") or not is_newer(tag):
        return None
    return Release(tag, str(d.get("html_url") or RELEASES_PAGE), str(d.get("body") or ""))
