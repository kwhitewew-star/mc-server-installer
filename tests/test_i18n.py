"""Every translatable string must exist in every catalog with the same placeholders."""

import ast
import json
import re
import string
from pathlib import Path

import pytest

from mcsi import i18n

ROOT = Path(__file__).resolve().parents[1]
PH = re.compile(r"\{\d+[^}]*\}")


def source_strings():
    out = set()
    files = list((ROOT / "mcsi").rglob("*.py")) + [ROOT / "scripts" / "selftest.py"]
    for f in files:
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_":
                assert n.args and isinstance(n.args[0], ast.Constant), f"non-literal _() in {f}:{n.lineno}"
                out.add(n.args[0].value)
    return out


KEYS = source_strings()
LANGS = [c for c in i18n.LANGUAGES if c != i18n.DEFAULT]


def test_languages_have_catalog_files():
    for code in LANGS:
        assert (ROOT / "mcsi" / "i18n" / f"{code}.json").is_file()


@pytest.mark.parametrize("code", LANGS)
def test_catalog_is_complete_and_consistent(code):
    cat = json.loads((ROOT / "mcsi" / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
    missing = sorted(KEYS - set(cat))
    assert not missing, f"{code}: {len(missing)} missing, e.g. {missing[:3]}"
    for en, tr in cat.items():
        assert sorted(PH.findall(en)) == sorted(PH.findall(tr)), (code, en, tr)
        fields = [f for _t, f, _s, _c in string.Formatter().parse(tr) if f is not None]
        assert all(f.isdigit() for f in fields), (code, tr)


def test_switching_language():
    try:
        i18n.set_language("ko")
        assert i18n._("Cancel") == "취소"
        i18n.set_language("nope")
        assert i18n.get_language() == "en" and i18n._("Cancel") == "Cancel"
    finally:
        i18n.set_language("en")
