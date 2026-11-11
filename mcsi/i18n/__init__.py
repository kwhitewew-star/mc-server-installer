"""Tiny gettext-style translation layer.

English is the source language: every UI string in the code is written in English and wrapped
in ``_()``.  Other languages live in ``<code>.json`` files next to this module, mapping the
English text to the translated text.  Missing entries fall back to English.

The language is read from the user's config file when this module is first imported, so it is
already set before any module that translates strings at import time (e.g. ``core.schema``).
"""

from __future__ import annotations

import json
from pathlib import Path

LANGUAGES = {
    "en": "English",
    "ko": "한국어",
    "ja": "日本語",
    "zh_CN": "简体中文",
    "es": "Español",
}
DEFAULT = "en"

_dir = Path(__file__).resolve().parent
_catalog: dict[str, str] = {}
_lang = DEFAULT


def set_language(code: str) -> None:
    global _catalog, _lang
    _lang = code if code in LANGUAGES else DEFAULT
    _catalog = {}
    if _lang != DEFAULT:
        try:
            _catalog = json.loads((_dir / f"{_lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _catalog = {}


def get_language() -> str:
    return _lang


def _(text: str) -> str:
    """Translate ``text`` (English) into the current language."""
    return _catalog.get(text, text)


def config_language() -> str:
    try:
        cfg = json.loads((Path.home() / ".mc_server_installer" / "config.json").read_text(encoding="utf-8"))
        return str(cfg.get("app", {}).get("language", DEFAULT))
    except (OSError, ValueError, AttributeError):
        return DEFAULT


set_language(config_language())
