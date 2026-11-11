"""Checks that the version list, build list and download URL of every server type really respond.
Run: python scripts/selftest.py   (the result is also saved to selftest_result.txt)"""

import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcsi.i18n import _  # noqa: E402
from mcsi.core.java import find_javas  # noqa: E402
from mcsi.core.net import NetError, open_url  # noqa: E402
from mcsi.core.providers import PROVIDERS  # noqa: E402

lines: list[str] = []


def out(s=""):
    print(s, flush=True)
    lines.append(s)


class _Stop(Exception):
    pass


class ProbeCtx:
    """Resolve only the first download URL without really running install()."""

    def __init__(self):
        self.folder = Path(os.environ.get("TEMP", "/tmp")) / "mcsi_probe"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.java = "java"
        self.url = ""

    def log(self, msg):
        pass

    def download(self, url, dest, sha256="", sha1="", md5=""):
        self.url = url
        try:
            r = open_url(url, timeout=20, retries=2, method="HEAD")
        except NetError:
            r = open_url(url, timeout=20, retries=2)
        size = int(r.headers.get("Content-Length") or 0)
        r.close()
        raise _Stop(f"{size / 1048576:.1f}MB" if size else _("Response OK"))

    def run(self, args, cwd):
        raise _Stop(_("Launch step (OK up to here)"))


out("=" * 72)
out(_("MC Server Installer connection test   Python {0}   {1}").format(sys.version.split()[0], time.strftime('%Y-%m-%d %H:%M')))
out("=" * 72)
fails = 0
for key, p in PROVIDERS.items():
    t0 = time.time()
    try:
        vs = p.list_versions(False)
        if not vs:
            raise NetError(_("Version list is empty"))
        mc = vs[0]
        builds = p.list_builds(mc)
        rec = next((b.id for b in builds if b.recommended), builds[0].id if builds else "")
        ctx = ProbeCtx()
        try:
            p.install(ctx, mc, rec)
            dl = "?"
        except _Stop as s:
            dl = str(s)
        out(_("[ OK ] {0:9s} versions {1:3d} (latest {2:8s})  builds {3:3d}  download {4}  {5:.1f}s").format(p.name, len(vs), mc, len(builds), dl, time.time() - t0))
    except Exception as e:  # noqa: BLE001
        fails += 1
        out(_("[FAIL] {0:9s} {1}: {2}").format(p.name, type(e).__name__, e))
        if "-v" in sys.argv:
            out(traceback.format_exc())
# Modrinth (mod/plugin search)
try:
    from mcsi.core import modrinth as MR
    hits, total = MR.search("", "mod", "fabric", "1.21.1")
    plug, ptotal = MR.search("", "plugin", "paper", "1.21.1")
    dep = MR.resolve(hits[0].project_id, hits[0].title, "mod", "fabric", "1.21.1", "", set())[0] if hits else []
    out(_("[ OK ] Modrinth  {0:,} mods / {1:,} plugins found, '{2}' file + dependencies: {3}").format(total, ptotal, hits[0].title if hits else '-', len(dep)))
except Exception as e:  # noqa: BLE001
    fails += 1
    out(_("[FAIL] Modrinth  {0}: {1}").format(type(e).__name__, e))
out("-" * 72)
javas = find_javas()
out(_("Java installations found: {0}").format(len(javas)))
for j in javas:
    out(f"   Java {j.major:<3d} {j.vendor:18s} {j.path}")
out("-" * 72)
out(_("Everything works.") if not fails else _("{0} failed. Please send this result as is.").format(fails))
(Path(__file__).resolve().parent.parent / "selftest_result.txt").write_text("\n".join(lines), encoding="utf-8")
if os.name == "nt" and "--no-pause" not in sys.argv:
    input(_("\nPress Enter to close..."))
