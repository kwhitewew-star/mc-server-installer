"""Build the event loader jars, events.json and the files for their GitHub releases.

    python scripts/build_events.py

Needs a JDK (javac + jar, version 9+; 17+ for reproducible jars). Writes:
  mcsi/assets/events/<name>-loader.jar   copies bundled with the app (used when offline)
  dist/events/events.json                the event list (with sha256 checksums) -> "events" release
  dist/events/<tag>/<jar> + notes.md     one release per loader ("event-halloween", ...)
  dist/events/publish.ps1                creates/updates all of those releases with gh

Publish (from the repository folder; every release is a pre-release so none becomes "latest"):
    powershell -ExecutionPolicy Bypass -File dist\\events\\publish.ps1
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcsi.core.events import BUILTIN  # noqa: E402

SRC = ROOT / "events" / "src" / "EventLoader.java"
ASSETS = ROOT / "mcsi" / "assets" / "events"
OUT = ROOT / "dist" / "events"
DATE = "2026-01-01T00:00:00Z"   # fixed timestamp -> the same source always gives the same jar (same sha256)
OCCASION = {"halloween": ("Halloween", "할로윈"), "christmas": ("Christmas", "크리스마스"),
            "newyear": ("New Year", "새해"), "valentine": ("Valentine's Day", "발렌타인데이"),
            "aprilfools": ("April Fools' Day", "만우절"), "ufo": ("World UFO Day", "세계 UFO의 날")}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def notes(e, digest: str, ko: dict) -> str:
    occ_en, occ_ko = OCCASION.get(e.key, (e.key, e.key))
    return f"""## {e.icon} {e.name}

A limited-time joke loader for **{occ_en}** ({e.window_text()}), part of
[MC Server Installer](https://github.com/kwhitewew-star/mc-server-installer).

{e.desc}

It is not a real Minecraft server: run `start.bat` (Windows) or `start.sh` (Mac/Linux) next to the jar,
or `java -jar {e.jar}`, to see a short 3D animation in a window (drawn in plain Java, no extra libraries).
Without a screen it plays a console animation instead (`--ascii` forces that). Java 8 or newer.
The installer shows it under *Server type* during the event and installs it in one click.

---

**{occ_ko}** 기간({e.window_text()})에만 나오는 장난용 로더예요. {ko.get(e.desc, '')}
진짜 서버가 아니라, 실행하면 창이 떠서 짧은 3D 애니메이션이 나오고 꺼져요.

`sha256: {digest}`
"""


def publish_script(entries: list) -> str:
    lines = [
        "# Creates or updates the event loader releases. Run from the repository folder:",
        "#   powershell -ExecutionPolicy Bypass -File dist\\events\\publish.ps1",
        "$ErrorActionPreference = 'Continue'",
        "$base = Split-Path -Parent $MyInvocation.MyCommand.Path",
        "function Publish($tag, $title, $files) {",
        "  $notes = Join-Path $base \"$tag\\notes.md\"",
        "  gh release view $tag *> $null",
        "  if ($LASTEXITCODE -eq 0) {",
        "    gh release edit $tag --prerelease --title $title --notes-file $notes",
        "    gh release upload $tag $files --clobber",
        "  } else {",
        "    gh release create $tag $files --prerelease --title $title --notes-file $notes",
        "  }",
        "  if ($LASTEXITCODE -eq 0) { Write-Host \"OK   $tag\" -ForegroundColor Green }",
        "  else { Write-Host \"FAIL $tag (run this script again)\" -ForegroundColor Red }",
        "}",
    ]
    for e in entries:
        lines.append(f"Publish '{e['tag']}' '{e['icon']} {e['name']}' (Join-Path $base '{e['tag']}\\{e['jar']}')")
    lines.append("Publish 'events' 'Event loaders (list)' (Join-Path $base 'events.json')")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    ko = json.loads((ROOT / "mcsi" / "i18n" / "ko.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        classes = tmp / "classes"
        classes.mkdir()
        subprocess.run(["javac", "--release", "8", "-Xlint:-options", "-d", str(classes)] + [str(p) for p in sorted(SRC.parent.glob("*.java"))], check=True)
        (tmp / "manifest.txt").write_text("Main-Class: EventLoader\n", encoding="ascii")
        entries = []
        for e in BUILTIN:
            work = tmp / e.key
            shutil.copytree(classes, work)
            (work / "event.txt").write_text(e.key, encoding="ascii")
            jar = ASSETS / e.jar
            jar.unlink(missing_ok=True)
            cmd = ["jar", "--create", "--file", str(jar), "--manifest", str(tmp / "manifest.txt"), "-C", str(work), "."]
            try:
                subprocess.run(cmd[:1] + [f"--date={DATE}"] + cmd[1:], check=True, capture_output=True)
            except subprocess.CalledProcessError:       # JDK < 17: no --date (jar is then not reproducible)
                subprocess.run(cmd, check=True)
            digest = sha256(jar)
            rel = OUT / e.release_tag
            rel.mkdir()
            shutil.copyfile(jar, rel / e.jar)
            (rel / "notes.md").write_text(notes(e, digest, ko), encoding="utf-8")
            entries.append({"key": e.key, "name": e.name, "accent": e.accent, "icon": e.icon,
                            "windows": e.windows, "jar": e.jar, "tag": e.release_tag, "sha256": digest,
                            "console_color": e.console_color, "fx": e.fx})
            print(f"{e.release_tag:18s} {e.jar:22s} {jar.stat().st_size:6d} bytes  {digest[:16]}")
    (OUT / "events").mkdir()
    (OUT / "events" / "notes.md").write_text(
        "The list of limited-time event loaders that MC Server Installer reads at startup (`events.json`).\n"
        "Each loader has its own release:\n\n"
        + "".join(f"- {d['icon']} [{d['name']}](https://github.com/kwhitewew-star/mc-server-installer/releases/tag/{d['tag']})\n"
                  for d in entries)
        + "\n앱이 시작할 때 읽는 이벤트 로더 목록이에요. 로더마다 릴리즈가 따로 있어요.\n", encoding="utf-8")
    (OUT / "events.json").write_text(json.dumps({"version": 1, "events": entries}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    # UTF-8 with BOM so Windows PowerShell 5 reads the emoji in the titles correctly
    (OUT / "publish.ps1").write_bytes(b"\xef\xbb\xbf" + publish_script(entries).encode("utf-8"))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
