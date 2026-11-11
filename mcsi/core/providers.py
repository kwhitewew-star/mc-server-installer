"""Per server type: version lists, build lists and install logic."""

from __future__ import annotations
from ..i18n import _

import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from .net import NetError, get_bytes, get_json
from .versions import at_least, is_release, required_java, sort_versions

MOJANG_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
FILL = "https://fill.papermc.io/v3/projects"
PURPUR = "https://api.purpurmc.org/v2/purpur"
FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
BABRIC_META = "https://meta.babric.glass-launcher.net/v2"
LEGACY_FABRIC_META = "https://meta.legacyfabric.net/v2"
FORGE_PROMOS = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
FORGE_MAVEN = "https://maven.minecraftforge.net/net/minecraftforge/forge"
NEO_MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
MOHIST_NEW = "https://api.mohistmc.com/project"
MOHIST_OLD = "https://mohistmc.com/api/v2/projects"
ARCLIGHT_RELEASES = "https://api.github.com/repos/IzzelAliz/Arclight/releases?per_page=60"
BUILDTOOLS = ("https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/"
              "artifact/target/BuildTools.jar")


@dataclass
class Build:
    id: str
    label: str
    recommended: bool = False


@dataclass
class Launch:
    """How to launch the server. kind='jar' is a jar file, 'args' is a Forge/NeoForge args file."""
    kind: str
    jar: str = ""
    win_args: str = ""
    unix_args: str = ""

    def java_args(self, windows: bool) -> list[str]:
        if self.kind == "jar":
            return ["-jar", self.jar]
        return [f"@{self.win_args if windows else self.unix_args}"]


class Ctx(Protocol):
    folder: Path
    java: str

    def log(self, msg: str) -> None: ...
    def download(self, url: str, dest: Path, sha256: str = "", sha1: str = "", md5: str = "") -> None: ...
    def run(self, args: list[str], cwd: Path) -> None: ...


@dataclass
class Provider:
    key: str
    name: str
    desc: str
    kind: str                 # vanilla | plugin | mod
    accent: str               # card color
    badge: str = ""
    experimental: bool = False
    needs_git: bool = False
    tags: list = field(default_factory=list)

    def list_versions(self, snapshots: bool) -> list[str]:
        raise NotImplementedError

    def list_builds(self, mc: str) -> list[Build]:
        return []

    def java_for(self, mc: str) -> int:
        return required_java(mc)

    def install(self, ctx: Ctx, mc: str, build: str) -> Launch:
        raise NotImplementedError


def _filter(vs: list[str], snapshots: bool) -> list[str]:
    return sort_versions([v for v in vs if snapshots or is_release(v)])


# ---------------- Vanilla ----------------

def mojang_versions() -> list[dict]:
    return get_json(MOJANG_MANIFEST)["versions"]


def mojang_version_json(mc: str) -> dict:
    for e in mojang_versions():
        if e["id"] == mc:
            return get_json(e["url"])
    raise NetError(_("Version {0} is not in the Mojang list.").format(mc))


class Vanilla(Provider):
    def list_versions(self, snapshots):
        return [v["id"] for v in mojang_versions()
                if v["type"] == "release" or (snapshots and v["type"] == "snapshot")]

    def java_for(self, mc):
        try:
            return int(mojang_version_json(mc)["javaVersion"]["majorVersion"])
        except Exception:
            return required_java(mc)

    def install(self, ctx, mc, build):
        data = mojang_version_json(mc)
        srv = data.get("downloads", {}).get("server")
        if not srv:
            raise NetError(_("Mojang does not provide a server file for version {0}.").format(mc))
        ctx.download(srv["url"], ctx.folder / "server.jar", sha1=srv.get("sha1", ""))
        return Launch("jar", jar="server.jar")


# ---------------- Paper / Folia (Fill v3) ----------------

class PaperLike(Provider):
    project: str = "paper"

    def list_versions(self, snapshots):
        data = get_json(f"{FILL}/{self.project}")
        groups = data.get("versions", {})
        flat = [v for lst in groups.values() for v in lst] if isinstance(groups, dict) else list(groups)
        return _filter(flat, snapshots)

    def _builds(self, mc) -> list[dict]:
        data = get_json(f"{FILL}/{self.project}/versions/{mc}/builds")
        builds = data if isinstance(data, list) else data.get("builds", [])
        return sorted(builds, key=lambda b: int(b["id"]), reverse=True)

    def list_builds(self, mc):
        out, rec = [], False
        for b in self._builds(mc):
            ch = str(b.get("channel", "")).upper()
            is_rec = ch == "STABLE" and not rec
            rec = rec or is_rec
            out.append(Build(str(b["id"]), f"#{b['id']} · {ch.lower() or 'build'}", is_rec))
        if out and not rec:
            out[0].recommended = True
        return out

    def java_for(self, mc):
        try:
            info = get_json(f"{FILL}/{self.project}/versions/{mc}")
            return int(info["version"]["java"]["version"]["minimum"])
        except Exception:
            return required_java(mc)

    def install(self, ctx, mc, build):
        builds = self._builds(mc)
        if not builds:
            raise NetError(_("No builds for {0} {1}.").format(self.name, mc))
        pick = next((b for b in builds if str(b["id"]) == build), None) if build else None
        if pick is None:
            pick = next((b for b in builds if str(b.get("channel", "")).upper() == "STABLE"), builds[0])
        downloads = pick.get("downloads", {})
        d = downloads.get("server:default") or next(iter(downloads.values()), None)
        if not d:
            raise NetError(_("{0} build #{1} has no download information.").format(self.name, pick['id']))
        ctx.log(_("{0} {1} build #{2} ({3})").format(self.name, mc, pick['id'], pick.get('channel', '')))
        ctx.download(d["url"], ctx.folder / "server.jar",
                     sha256=d.get("checksums", {}).get("sha256", ""))
        return Launch("jar", jar="server.jar")


class Paper(PaperLike):
    project = "paper"


class Folia(PaperLike):
    project = "folia"


# ---------------- Purpur ----------------

class Purpur(Provider):
    def list_versions(self, snapshots):
        return _filter(get_json(PURPUR)["versions"], snapshots)

    def list_builds(self, mc):
        data = get_json(f"{PURPUR}/{mc}")["builds"]
        latest = str(data.get("latest", ""))
        allb = sorted((str(b) for b in data.get("all", [])), key=lambda s: int(s) if s.isdigit() else 0,
                      reverse=True)
        return [Build(b, f"#{b}", b == latest) for b in allb]

    def install(self, ctx, mc, build):
        b = build or str(get_json(f"{PURPUR}/{mc}")["builds"]["latest"])
        md5 = ""
        try:
            md5 = get_json(f"{PURPUR}/{mc}/{b}").get("md5", "") or ""
        except Exception:
            pass
        ctx.log(_("Purpur {0} build #{1}").format(mc, b))
        ctx.download(f"{PURPUR}/{mc}/{b}/download", ctx.folder / "server.jar", md5=md5)
        return Launch("jar", jar="server.jar")


# ---------------- Spigot / Bukkit (BuildTools) ----------------

class BuildToolsProvider(Provider):
    target: str = "spigot"

    def list_versions(self, snapshots):
        return [v["id"] for v in mojang_versions()
                if v["type"] == "release" and at_least(v["id"], 1, 8)]

    def install(self, ctx, mc, build):
        if not shutil.which("git"):
            raise NetError(_("Spigot/Bukkit builds need Git. Install it from git-scm.com and try again."))
        work = ctx.folder / ".buildtools"
        work.mkdir(parents=True, exist_ok=True)
        ctx.download(BUILDTOOLS, work / "BuildTools.jar")
        args = [ctx.java, "-jar", "BuildTools.jar", "--rev", mc, "--output-dir", str(ctx.folder)]
        if self.target == "craftbukkit":
            args += ["--compile", "craftbukkit"]
        ctx.log(_("Building with BuildTools. The first build can take 10-30 minutes."))
        ctx.run(args, work)
        cands = sorted(ctx.folder.glob(f"{self.target}-*.jar"), key=lambda p: p.stat().st_mtime)
        if not cands:
            raise NetError(_("Build output ({0}-{1}.jar) not found. Check the log.").format(self.target, mc))
        cands[-1].replace(ctx.folder / "server.jar")
        return Launch("jar", jar="server.jar")


class Spigot(BuildToolsProvider):
    target = "spigot"


class Bukkit(BuildToolsProvider):
    target = "craftbukkit"


# ---------------- Fabric / Babric ----------------

def _first_stable(items: list[dict]) -> dict:
    return next((i for i in items if i.get("stable", True)), items[0])


class FabricLike(Provider):
    meta: str = FABRIC_META
    launcher_name = "fabric-server-launch.jar"   # avoid server.jar, that's the vanilla file name

    def list_versions(self, snapshots):
        games = get_json(f"{self.meta}/versions/game")
        vs = [g["version"] for g in games if snapshots or g.get("stable", True)]
        return vs if self.key == "babric" else sort_versions(vs)

    def list_builds(self, mc):
        loaders = get_json(f"{self.meta}/versions/loader")
        rec = _first_stable(loaders)["version"]
        return [Build(l["version"], l["version"] + ("" if l.get("stable", True) else " · beta"),
                      l["version"] == rec) for l in loaders[:40]]

    def install(self, ctx, mc, build):
        loader = build or _first_stable(get_json(f"{self.meta}/versions/loader"))["version"]
        inst = _first_stable(get_json(f"{self.meta}/versions/installer"))["version"]
        ctx.log(_("{0} loader {1} / installer {2}").format(self.name, loader, inst))
        ctx.download(f"{self.meta}/versions/loader/{mc}/{loader}/{inst}/server/jar",
                     ctx.folder / self.launcher_name)
        return Launch("jar", jar=self.launcher_name)


class Fabric(FabricLike):
    meta = FABRIC_META


class Babric(FabricLike):
    """Fabric port for Beta 1.7.3 only."""
    meta = BABRIC_META

    def java_for(self, mc):
        return 17  # recommended by the Babric toolchain


class LegacyFabric(FabricLike):
    """Fabric port for old versions (1.3 - 1.13.2) that Fabric doesn't support."""
    meta = LEGACY_FABRIC_META


# ---------------- Quilt (runs the installer) ----------------

class Quilt(Provider):
    def list_versions(self, snapshots):
        games = get_json(f"{QUILT_META}/versions/game")
        return sort_versions([g["version"] for g in games if snapshots or g.get("stable", True)])

    def list_builds(self, mc):
        loaders = get_json(f"{QUILT_META}/versions/loader")
        vs = [l["version"] for l in loaders]
        stable = next((v for v in vs if "beta" not in v and "pre" not in v), vs[0] if vs else "")
        return [Build(v, v, v == stable) for v in vs[:40]]

    def install(self, ctx, mc, build):
        inst = get_json(f"{QUILT_META}/versions/installer")[0]
        ver = inst["version"]
        url = inst.get("url") or (f"https://maven.quiltmc.org/repository/release/org/quiltmc/"
                                  f"quilt-installer/{ver}/quilt-installer-{ver}.jar")
        jar = ctx.folder / "quilt-installer.jar"
        ctx.download(url, jar)
        args = [ctx.java, "-jar", jar.name, "install", "server", mc]
        if build:
            args.append(build)
        args += ["--download-server", f"--install-dir={ctx.folder}"]
        ctx.run(args, ctx.folder)
        jar.unlink(missing_ok=True)
        launch = next(iter(ctx.folder.glob("quilt-server-launch*.jar")), None)
        if not launch:
            raise NetError(_("quilt-server-launch.jar not found. Check the log."))
        return Launch("jar", jar=launch.name)


# ---------------- Forge / NeoForge ----------------

ARGS_RE = re.compile(r"@(libraries[/\\][^\s\"']+?_args\.txt)")


def detect_installer_launch(d: Path) -> Launch:
    win = unix = ""
    for name in ("run.bat", "run.sh"):
        p = d / name
        if p.exists():
            for m in ARGS_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
                path = m.group(1).replace("\\", "/")
                if path.endswith("win_args.txt"):
                    win = path
                elif path.endswith("unix_args.txt"):
                    unix = path
    if win or unix:
        return Launch("args", win_args=win or unix.replace("unix_args", "win_args"),
                      unix_args=unix or win.replace("win_args", "unix_args"))
    jars = [p for p in d.glob("*.jar") if "installer" not in p.name and
            ("forge" in p.name.lower() or "neoforge" in p.name.lower())]
    if jars:
        return Launch("jar", jar=sorted(jars, key=lambda p: len(p.name))[0].name)
    raise NetError(_("Could not find the launch file (run.bat or forge jar) after installing."))


class Forge(Provider):
    def _promos(self) -> dict:
        return get_json(FORGE_PROMOS)["promos"]

    def list_versions(self, snapshots):
        vs = {k.rsplit("-", 1)[0] for k in self._promos()}
        return sort_versions([v for v in vs if at_least(v, 1, 12)])

    def list_builds(self, mc):
        root = ET.fromstring(get_bytes(f"{FORGE_MAVEN}/maven-metadata.xml"))
        promos = self._promos()
        rec = promos.get(f"{mc}-recommended") or promos.get(f"{mc}-latest") or ""
        out = []
        for e in root.iter("version"):
            v = (e.text or "").strip()
            if v.startswith(mc + "-"):
                b = v[len(mc) + 1:]
                tag = _(" · recommended") if b == promos.get(f"{mc}-recommended") else (
                    _(" · latest") if b == promos.get(f"{mc}-latest") else "")
                out.append(Build(b, b + tag, b == rec))
        out.reverse()
        return out[:60]

    def install(self, ctx, mc, build):
        promos = self._promos()
        b = build or promos.get(f"{mc}-recommended") or promos.get(f"{mc}-latest")
        if not b:
            raise NetError(_("No Forge build found for {0}.").format(mc))
        full = f"{mc}-{b}"
        jar = ctx.folder / f"forge-{full}-installer.jar"
        ctx.download(f"{FORGE_MAVEN}/{full}/forge-{full}-installer.jar", jar)
        ctx.run([ctx.java, "-jar", jar.name, "--installServer"], ctx.folder)
        jar.unlink(missing_ok=True)
        return detect_installer_launch(ctx.folder)


def neo_to_mc(nv: str) -> Optional[str]:
    """NeoForge version -> Minecraft version.
    20.4.237 → 1.20.4, 21.0.x → 1.21, 26.1.0.10-beta → 26.1, 26.1.2.5 → 26.1.2,
    26.1.0.0-alpha.2+snapshot-1 → 26.1-snapshot-1"""
    base, _x, plus = nv.partition("+")
    core = base.split("-")[0]
    parts = core.split(".")
    if not all(p.isdigit() for p in parts) or len(parts) < 3:
        return None
    a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
    if a >= 26:
        mc = f"{a}.{b}" if c == 0 else f"{a}.{b}.{c}"
    elif a >= 20:
        mc = f"1.{a}" if b == 0 else f"1.{a}.{b}"
    else:
        return None
    if plus:
        mc += "-" + plus
    return mc


def neo_versions() -> list[str]:
    root = ET.fromstring(get_bytes(f"{NEO_MAVEN}/maven-metadata.xml"))
    return [(e.text or "").strip() for e in root.iter("version") if e.text]


class NeoForge(Provider):
    def list_versions(self, snapshots):
        mcs = set()
        for nv in neo_versions():
            mc = neo_to_mc(nv)
            if mc and (snapshots or ("+" not in nv and "alpha" not in nv)):
                mcs.add(mc)
        return sort_versions(list(mcs))

    def list_builds(self, mc):
        cands = [nv for nv in neo_versions() if neo_to_mc(nv) == mc]
        cands.sort(key=lambda s: [int(x) for x in re.findall(r"\d+", s.split("-")[0].split("+")[0])],
                   reverse=True)
        stable = next((c for c in cands if "-" not in c), cands[0] if cands else "")
        return [Build(c, c + (_(" · stable") if "-" not in c else ""), c == stable) for c in cands[:60]]

    def install(self, ctx, mc, build):
        nv = build
        if not nv:
            builds = self.list_builds(mc)
            if not builds:
                raise NetError(_("No NeoForge build found for {0}.").format(mc))
            nv = next((b.id for b in builds if b.recommended), builds[0].id)
        ctx.log(f"NeoForge {nv}")
        jar = ctx.folder / f"neoforge-{nv}-installer.jar"
        ctx.download(f"{NEO_MAVEN}/{nv}/neoforge-{nv}-installer.jar", jar)
        ctx.run([ctx.java, "-jar", jar.name, "--installServer"], ctx.folder)
        jar.unlink(missing_ok=True)
        return detect_installer_launch(ctx.folder)


# ---------------- Hybrids (plugins + mods) ----------------

def _as_versions(data) -> list[str]:
    """The MohistMC API response shape has changed over time, so accept all known forms."""
    if isinstance(data, dict):
        for k in ("versions", "data", "list"):
            if k in data:
                return _as_versions(data[k])
        return []
    out = []
    for v in data or []:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            name = v.get("name") or v.get("version") or v.get("id") or v.get("mcVersion")
            if name:
                out.append(str(name))
    return out


def _as_builds(data) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("builds") or data.get("data") or []
    out = []
    for b in data or []:
        if isinstance(b, dict):
            bid = b.get("id") or b.get("number") or b.get("build")
            if bid is not None:
                out.append(dict(b, _id=str(bid)))
        elif isinstance(b, (int, str)):
            out.append({"_id": str(b)})
    return sorted(out, key=lambda b: int(b["_id"]) if b["_id"].isdigit() else 0, reverse=True)


class MohistLike(Provider):
    """MohistMC projects: mohist (Forge), youer (NeoForge), banner (Fabric)."""
    project: str = "mohist"

    def _get(self, path_new: str, path_old: str):
        last = None
        for url in (f"{MOHIST_NEW}/{self.project}{path_new}", f"{MOHIST_OLD}/{self.project}{path_old}"):
            try:
                return url, get_json(url)
            except Exception as e:  # noqa: BLE001
                last = e
        raise NetError(_("Could not fetch the {0} server list: {1}").format(self.name, last))

    def list_versions(self, snapshots):
        _x, data = self._get("", "")
        return _filter(_as_versions(data), snapshots)

    def _builds(self, mc):
        url, data = self._get(f"/{mc}/builds", f"/{mc}/builds")
        return url, _as_builds(data)

    def list_builds(self, mc):
        _x, builds = self._builds(mc)
        return [Build(b["_id"], f"#{b['_id']}", i == 0) for i, b in enumerate(builds[:60])]

    def install(self, ctx, mc, build):
        url, builds = self._builds(mc)
        if not builds:
            raise NetError(_("No builds for {0} {1}.").format(self.name, mc))
        pick = next((b for b in builds if b["_id"] == build), builds[0]) if build else builds[0]
        dl = pick.get("url") or pick.get("downloadUrl") or f"{url.rsplit('/builds', 1)[0]}/builds/{pick['_id']}/download"
        md5 = pick.get("fileMd5") or pick.get("md5") or ""
        sha256 = pick.get("fileSha256") or pick.get("sha256") or ""
        ctx.log(_("{0} {1} build #{2}").format(self.name, mc, pick['_id']))
        ctx.download(dl, ctx.folder / "server.jar", md5=md5 if len(str(md5)) == 32 else "",
                     sha256=sha256 if len(str(sha256)) == 64 else "")
        return Launch("jar", jar="server.jar")


class Mohist(MohistLike):
    project = "mohist"


class Youer(MohistLike):
    project = "youer"


class Banner(MohistLike):
    project = "banner"


ARC_RE = re.compile(r"arclight-(forge|neoforge|fabric)-(\d+(?:\.\d+){1,2})-(.+)\.jar$", re.I)
LOADER_NAME = {"forge": "Forge", "neoforge": "NeoForge", "fabric": "Fabric"}


class Arclight(Provider):
    """Uses arclight-<loader>-<version>-<build>.jar files from GitHub releases."""

    def _assets(self) -> list[tuple[str, str, str, str, bool]]:
        out = []
        for rel in get_json(ARCLIGHT_RELEASES):
            pre = bool(rel.get("prerelease"))
            for a in rel.get("assets", []):
                m = ARC_RE.match(a.get("name", ""))
                if m:
                    out.append((m.group(2), m.group(1).lower(), m.group(3), a["browser_download_url"], pre))
        return out

    def list_versions(self, snapshots):
        # without snapshots, only versions that have a release file
        return sort_versions(list({mc for mc, _l, _v, _u, pre in self._assets() if snapshots or not pre}))

    def list_builds(self, mc):
        items = [a for a in self._assets() if a[0] == mc]
        order = {"neoforge": 0, "fabric": 1, "forge": 2}
        items.sort(key=lambda a: (a[4], order.get(a[1], 9)))
        return [Build(url, f"{LOADER_NAME[loader]} · {ver}" + (_(" · pre-release") if pre else ""), i == 0)
                for i, (_x, loader, ver, url, pre) in enumerate(items)]

    def install(self, ctx, mc, build):
        url = build
        if not url:
            builds = self.list_builds(mc)
            if not builds:
                raise NetError(_("No Arclight file for {0}.").format(mc))
            url = builds[0].id
        ctx.log(f"Arclight: {url.rsplit('/', 1)[-1]}")
        ctx.download(url, ctx.folder / "arclight.jar")
        return Launch("jar", jar="arclight.jar")


PROVIDERS: dict[str, Provider] = {p.key: p for p in [
    Vanilla("vanilla", "Vanilla", _("Official Mojang server. As vanilla as it gets"), "vanilla", "#34d399", _("Official")),
    Paper("paper", "Paper", _("The standard plugin server. Fast and stable"), "plugin", "#60a5fa", _("Recommended")),
    Purpur("purpur", "Purpur", _("Based on Paper, with more fun features and options"), "plugin", "#c084fc"),
    Folia("folia", "Folia", _("Multithreaded Paper for huge servers (check plugin support)"), "plugin", "#38bdf8", _("Advanced")),
    Spigot("spigot", "Spigot", _("Classic plugin server, built locally with BuildTools"), "plugin", "#fb923c",
           _("Needs Git"), needs_git=True),
    Bukkit("bukkit", "Bukkit", _("CraftBukkit, built locally with BuildTools"), "plugin", "#f97316",
           _("Needs Git"), needs_git=True),
    Fabric("fabric", "Fabric", _("Lightweight mod loader with fast updates"), "mod", "#fbbf24", _("Popular")),
    Quilt("quilt", "Quilt", _("Mod loader compatible with Fabric mods"), "mod", "#f472b6"),
    LegacyFabric("legacyfabric", "Legacy Fabric", _("Use Fabric mods on 1.3 – 1.13.2, before official Fabric support"),
                 "mod", "#e0c48a", _("Legacy")),
    Babric("babric", "Babric", _("Fabric port for Beta 1.7.3 only (b1.7.3)"), "mod", "#c9b48a", "Beta 1.7.3",
           experimental=True),
    Forge("forge", "Forge", _("The classic big mod loader"), "mod", "#f87171"),
    NeoForge("neoforge", "NeoForge", _("Successor to Forge. Standard for modern modpacks"), "mod", "#fb7185", _("Recommended")),
    Mohist("mohist", "Mohist", _("Forge mods + Bukkit/Spigot plugins together"), "hybrid", "#22d3ee", _("Popular")),
    Youer("youer", "Youer", _("NeoForge mods + plugins (successor to Mohist)"), "hybrid", "#a78bfa", _("Recommended")),
    Arclight("arclight", "Arclight", _("Pick Forge, NeoForge or Fabric + plugins"), "hybrid", "#f59e0b",
             _("Choose loader")),
    Banner("banner", "Banner", _("Fabric mods + plugins"), "hybrid", "#4ade80", _("Experimental"), experimental=True),
]}
