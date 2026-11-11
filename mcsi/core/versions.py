"""Minecraft version string parsing (1.x scheme + the year-based 26.x scheme from 2026)."""

from __future__ import annotations

import re

_SNAP_WEEK = re.compile(r"^(\d{2})w(\d{2})[a-z]$")


def version_key(v: str) -> tuple:
    """Sort key. 1.21.11 < 26.1-snapshot-1 < 26.1-pre-1 < 26.1-rc-1 < 26.1 < 26.1.1."""
    v = v.strip()
    m = _SNAP_WEEK.match(v)
    if m:  # weekly snapshots like 25w44a: place within their year
        year, week = int(m.group(1)), int(m.group(2))
        approx = {25: (1, 21, 11), 24: (1, 21, 1), 23: (1, 20, 4), 22: (1, 19, 3),
                  21: (1, 18, 0), 20: (1, 16, 4), 19: (1, 15, 0), 18: (1, 14, 0)}
        base = approx.get(year, (1, 13, 0)) if year <= 25 else (year, 0, 0)
        return base + (0, week, ord(v[-1]))
    m2 = re.match(r"^[a-z]?([\d.]+)(.*)$", v)
    main, tag = (m2.group(1), m2.group(2)) if m2 else (v, "")
    nums = [int(n) for n in re.findall(r"\d+", main)][:3]
    while len(nums) < 3:
        nums.append(0)
    tag = tag.lower()
    if not tag:
        stage = 9
    elif "snapshot" in tag:
        stage = 1
    elif "pre" in tag:
        stage = 2
    elif "rc" in tag:
        stage = 3
    else:
        stage = 0
    tnum = [int(n) for n in re.findall(r"\d+", tag)] or [0]
    return tuple(nums) + (stage, tnum[0], 0)


def sort_versions(vs: list[str]) -> list[str]:
    return sorted(dict.fromkeys(vs), key=version_key, reverse=True)


def at_least(v: str, *target: int) -> bool:
    return version_key(v)[:3] >= tuple(target) + (0,) * (3 - len(target))


def required_java(mc: str) -> int:
    """Minimum Java major version needed to run the server (rules based on Mojang metadata)."""
    k = version_key(mc)
    if k[0] >= 26:
        return 25
    if k[:3] >= (1, 20, 5):
        return 21
    if k[:3] >= (1, 18, 0):
        return 17
    if k[:3] >= (1, 17, 0):
        return 16
    return 8


def is_release(v: str) -> bool:
    return re.fullmatch(r"\d+\.\d+(\.\d+)?", v) is not None


def uses_snake_gamerules(mc: str) -> bool:
    """Game rule names became snake_case in 1.21.11."""
    return at_least(mc, 1, 21, 11)


def props_moved_to_gamerules(mc: str) -> bool:
    """Since 1.21.9 some properties (pvp etc.) moved from server.properties to game rules."""
    return at_least(mc, 1, 21, 9)
