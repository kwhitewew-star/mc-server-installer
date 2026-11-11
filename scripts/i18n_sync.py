"""Keep translation catalogs in sync with the source code.

    python scripts/i18n_sync.py            # report missing / unused entries for every language
    python scripts/i18n_sync.py --new xx   # create mcsi/i18n/xx.json with every English string to translate

Every user-visible string is written in English and wrapped in _("...").  Catalogs map that exact
English text to the translation; anything missing falls back to English at runtime.
"""

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT_DIR = ROOT / "mcsi" / "i18n"


def source_strings() -> list[str]:
    seen: dict[str, None] = {}
    for f in sorted((ROOT / "mcsi").rglob("*.py")) + [ROOT / "scripts" / "selftest.py"]:
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_" and n.args
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                seen.setdefault(n.args[0].value)
    return list(seen)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", metavar="CODE", help="create an untranslated catalog for a new language")
    a = ap.parse_args()
    keys = source_strings()
    if a.new:
        path = CAT_DIR / f"{a.new}.json"
        if path.exists():
            raise SystemExit(f"{path} already exists")
        path.write_text(json.dumps({k: k for k in sorted(keys)}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Wrote {path} ({len(keys)} strings). Translate the values, then add '{a.new}' to LANGUAGES "
              f"in mcsi/i18n/__init__.py.")
        return
    print(f"{len(keys)} translatable strings in the source")
    for cat in sorted(CAT_DIR.glob("*.json")):
        data = json.loads(cat.read_text(encoding="utf-8"))
        missing = [k for k in keys if k not in data]
        unused = [k for k in data if k not in set(keys)]
        print(f"  {cat.stem:6s} {len(data):4d} entries, {len(missing)} missing, {len(unused)} unused")
        for k in missing[:10]:
            print("      missing:", k[:90])


if __name__ == "__main__":
    main()
