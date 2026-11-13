"""Modpacks: Modrinth (.mrpack), CurseForge modpack zips (manifest.json) and CurseForge server packs.

* ``read_pack(path)`` looks inside the archive and returns a :class:`Pack`: which loader and Minecraft
  version it needs, which files to download, and which folders inside the zip to copy over the server.
* ``Installer`` (core/installer.py) installs the loader with the normal provider, then calls
  ``install_pack``, which downloads the server-side files, verifies their hashes and applies the overrides.

Modrinth
    ``modrinth.index.json`` lists every file with its download URL, hashes and whether the server needs
    it (``env.server``); ``dependencies`` gives the Minecraft and loader versions. ``overrides/`` and then
    ``server-overrides/`` are copied over the server folder.
CurseForge modpack
    ``manifest.json`` only lists project/file IDs. Resolving them needs a CurseForge API key (free at
    console.curseforge.com). Files whose authors disabled third-party downloads have no URL; they are
    listed in MANUAL_DOWNLOADS.txt with links. Client-only files and non-mod content are skipped.
CurseForge server pack
    A ready server folder zipped up. The loader is detected (variables.txt, installer jars, libraries)
    and installed fresh; the pack's mods/config/... are then copied over it (its own launch scripts,
    jars and libraries are left out, the installer writes its own).
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from ..i18n import _
from .net import NetError, USER_AGENT, _context, get_json

MR_API = "https://api.modrinth.com/v2"
CF_API = "https://api.curseforge.com/v1"
CF_KEY_PAGE = "https://console.curseforge.com/"

# Modrinth / CurseForge loader names -> provider key in this app
LOADER_TO_SERVER = {"fabric-loader": "fabric", "quilt-loader": "quilt", "forge": "forge", "neoforge": "neoforge",
                    "fabric": "fabric", "quilt": "quilt"}

# Top-level things a server pack ships that this installer makes itself
SERVERPACK_SKIP_DIRS = {"libraries", ".fabric", ".quilt", "versions", "logs", "crash-reports", "cache"}
SERVERPACK_SKIP_FILES = re.compile(r"(?i)^(.*\.(jar|bat|sh|ps1|command|cmd|exe)|eula\.txt|user_jvm_args\.txt|"
                                   r"variables\.txt|run\..*|start.*|install.*|manifest\.json)$")

CF_CLASS_MODS = 6
CF_CLASS_NAMES = {12: "resourcepacks", 6552: "shaderpacks", 17: "saves"}


class PackError(Exception):
    pass


@dataclass
class PackFile:
    path: str                       # relative path in the server folder ("mods/x.jar")
    urls: list = field(default_factory=list)
    sha1: str = ""
    sha512: str = ""
    size: int = 0


@dataclass
class Pack:
    kind: str                       # "modrinth" | "curseforge" | "serverpack"
    name: str
    version: str = ""
    mc: str = ""
    server: str = ""                # provider key (fabric / quilt / forge / neoforge)
    build: str = ""                 # loader version in the provider's own format
    archive: str = ""               # local path of the zip
    files: list = field(default_factory=list)          # PackFile (Modrinth)
    cf_files: list = field(default_factory=list)       # [(projectID, fileID, required)]
    overrides: list = field(default_factory=list)      # folders inside the zip, applied in order
    root: str = ""                  # server pack: folder inside the zip that holds the server
    summary: str = ""               # one line for the UI
    icon_url: str = ""              # project icon (Modrinth), shown on the cards
    icon_color: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["files"] = [asdict(f) if not isinstance(f, dict) else f for f in self.files]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Pack":
        d = dict(d)
        d["files"] = [PackFile(**f) if isinstance(f, dict) else f for f in d.get("files", [])]
        d["cf_files"] = [tuple(x) for x in d.get("cf_files", [])]
        known = Pack.__dataclass_fields__
        return Pack(**{k: v for k, v in d.items() if k in known})


# ------------------------------------------------------------------ reading archives
def _loader(server: str, version: str, mc: str) -> tuple[str, str]:
    """Normalise a loader version to what the provider expects as its build id."""
    if server == "forge":
        v = version
        if v.startswith(mc + "-"):
            v = v[len(mc) + 1:]
        return "forge", v
    if server == "neoforge":
        # NeoForge for 1.20.1 still used Forge's numbering (47.1.x) and Forge's package names; its mods run
        # on Forge 1.20.1, which this app can install. Every later NeoForge has its own version line.
        if mc == "1.20.1" or version.startswith(mc + "-"):
            return "forge", ""
        return "neoforge", version
    return server, version


def _read_modrinth(z: zipfile.ZipFile, path: str) -> Pack:
    idx = json.loads(z.read("modrinth.index.json"))
    if idx.get("game") not in (None, "minecraft"):
        raise PackError(_("This .mrpack is not a Minecraft modpack."))
    deps = idx.get("dependencies") or {}
    mc = str(deps.get("minecraft", ""))
    server = build = ""
    for k in ("neoforge", "forge", "quilt-loader", "fabric-loader"):
        if k in deps:
            server, build = _loader(LOADER_TO_SERVER[k], str(deps[k]), mc)
            break
    if not mc or not server:
        raise PackError(_("The modpack does not say which Minecraft version or mod loader it needs."))
    files = []
    for f in idx.get("files") or []:
        env = (f.get("env") or {}).get("server", "required")
        if env == "unsupported":
            continue                               # client-only (shaders, minimaps, ...)
        h = f.get("hashes") or {}
        files.append(PackFile(path=f["path"], urls=list(f.get("downloads") or []), sha1=h.get("sha1", ""),
                              sha512=h.get("sha512", ""), size=int(f.get("fileSize") or 0)))
    p = Pack("modrinth", str(idx.get("name") or Path(path).stem), str(idx.get("versionId", "")), mc, server, build,
             path, files=files, overrides=["overrides", "server-overrides"])
    p.summary = _("{0} files for the server").format(len(files))
    return p


def _read_curseforge(z: zipfile.ZipFile, path: str, man: dict) -> Pack:
    mc_info = man.get("minecraft") or {}
    mc = str(mc_info.get("version", ""))
    loaders = mc_info.get("modLoaders") or []
    primary = next((l for l in loaders if l.get("primary")), loaders[0] if loaders else {})
    lid = str(primary.get("id", ""))                       # "forge-47.2.0", "neoforge-21.1.80", "fabric-0.16.9"
    name, _sep, ver = lid.partition("-")
    server = LOADER_TO_SERVER.get(name, "")
    if not mc or not server:
        raise PackError(_("The modpack does not say which Minecraft version or mod loader it needs."))
    server, build = _loader(server, ver, mc)
    cf = [(int(f["projectID"]), int(f["fileID"]), bool(f.get("required", True)))
          for f in man.get("files") or [] if "projectID" in f and "fileID" in f]
    p = Pack("curseforge", str(man.get("name") or Path(path).stem), str(man.get("version", "")), mc, server, build,
             path, cf_files=cf, overrides=[str(man.get("overrides") or "overrides")])
    p.summary = _("{0} mods from CurseForge").format(len(cf))
    return p


def _detect_serverpack(names: list[str]) -> tuple[str, str, str, str]:
    """(root, server, mc, build) for a zipped server folder, or raises PackError."""
    mods = [n for n in names if re.search(r"(^|/)mods/[^/]+\.jar$", n)]
    if not mods:
        raise PackError(_("This zip is not a modpack: no modrinth.index.json, manifest.json or mods folder."))
    root = mods[0][:mods[0].index("mods/")]
    rel = [n[len(root):] for n in names if n.startswith(root)]
    joined = "\n".join(rel)
    # Forge / NeoForge installer or universal jars at the top
    m = re.search(r"(?m)^neoforge-(\d+\.\d+\.\d+[^/\n]*?)-(?:installer|universal|server)\.jar$", joined)
    if m:
        from .providers import neo_to_mc
        return root, "neoforge", neo_to_mc(m.group(1)) or "", m.group(1)
    m = re.search(r"(?m)^forge-(1\.\d+(?:\.\d+)?)-([\d.]+)(?:-[\w.]+)?-(?:installer|universal|server)?\.?jar$", joined)
    if m:
        return root, "forge", m.group(1), m.group(2)
    m = re.search(r"(?m)^libraries/net/neoforged/neoforge/([^/]+)/", joined)
    if m:
        from .providers import neo_to_mc
        return root, "neoforge", neo_to_mc(m.group(1)) or "", m.group(1)
    m = re.search(r"(?m)^libraries/net/minecraftforge/forge/(1\.[\d.]+)-([\d.]+)/", joined)
    if m:
        return root, "forge", m.group(1), m.group(2)
    m = re.search(r"(?m)^libraries/net/fabricmc/fabric-loader/([^/]+)/", joined)
    mc = re.search(r"(?m)^libraries/net/fabricmc/intermediary/([^/]+)/", joined)
    if m and mc:
        return root, "fabric", mc.group(1), m.group(1)
    m = re.search(r"(?m)^libraries/org/quiltmc/quilt-loader/([^/]+)/", joined)
    mc = mc or re.search(r"(?m)^libraries/org/quiltmc/hashed/([^/]+)/", joined)
    if m and mc:
        return root, "quilt", mc.group(1), m.group(1)
    raise PackError(_("Could not tell which loader and Minecraft version this server pack uses."))


def _read_serverpack(z: zipfile.ZipFile, path: str) -> Pack:
    names = z.namelist()
    var = next((n for n in names if n.endswith("variables.txt") and n.count("/") <= 1), None)
    if var:                                                   # ServerPackCreator packs say it plainly
        kv = dict(re.findall(r"(?m)^\s*([A-Z_]+)\s*=\s*\"?([^\"\r\n]*)\"?", z.read(var).decode("utf-8", "replace")))
        loader = kv.get("MODLOADER", "").lower().replace(" ", "")
        server = LOADER_TO_SERVER.get(loader, loader if loader in ("forge", "neoforge", "fabric", "quilt") else "")
        if server and kv.get("MINECRAFT_VERSION"):
            mc = kv["MINECRAFT_VERSION"]
            s2, build = _loader(server, kv.get("MODLOADER_VERSION", ""), mc)
            root = var[:-len("variables.txt")]
            p = Pack("serverpack", Path(path).stem, "", mc, s2, build, path, root=root)
            p.summary = _("server pack · {0} mods").format(sum(1 for n in names if re.search(r"/?mods/[^/]+\.jar$", n)))
            return p
    root, server, mc, build = _detect_serverpack(names)
    if not mc:
        raise PackError(_("Could not tell which loader and Minecraft version this server pack uses."))
    p = Pack("serverpack", Path(path).stem, "", mc, server, build, path, root=root)
    p.summary = _("server pack · {0} mods").format(sum(1 for n in names if re.search(r"(^|/)mods/[^/]+\.jar$", n)))
    return p


def read_pack(path: str | Path) -> Pack:
    """Open a .mrpack / CurseForge zip / server pack zip and describe it. Raises PackError."""
    path = str(path)
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "modrinth.index.json" in names:
                return _read_modrinth(z, path)
            if "manifest.json" in names:
                try:
                    man = json.loads(z.read("manifest.json"))
                except ValueError:
                    man = {}
                if man.get("manifestType") == "minecraftModpack" or "minecraft" in man:
                    return _read_curseforge(z, path, man)
            return _read_serverpack(z, path)
    except zipfile.BadZipFile as e:
        raise PackError(_("Not a valid zip / .mrpack file: {0}").format(e)) from e
    except (KeyError, ValueError, TypeError) as e:
        raise PackError(_("The modpack file is damaged or in an unknown format ({0}).").format(e)) from e


# ------------------------------------------------------------------ Modrinth search
@dataclass
class PackHit:
    project_id: str
    slug: str
    title: str
    description: str
    author: str
    downloads: int
    icon_url: str
    follows: int = 0
    categories: list = field(default_factory=list)   # display categories: loaders + tags
    game_versions: list = field(default_factory=list)
    updated: str = ""                                 # ISO date of the last update
    color: int = 0                                    # Modrinth's accent colour for the project (RGB int)
    server_side: str = ""                             # required / optional / unsupported

    @property
    def latest_mc(self) -> str:
        """Newest release Minecraft version the pack supports (Modrinth lists them oldest first)."""
        rel = [v for v in self.game_versions
               if v.replace(".", "").isdigit() and v.count(".") >= 1]      # skip snapshots / pre-releases
        if not rel:
            return (self.game_versions or [""])[-1]
        return max(rel, key=lambda v: tuple(int(x) for x in v.split(".")))


SORTS = ("relevance", "downloads", "follows", "newest", "updated")


def _hit(h: dict) -> PackHit:
    return PackHit(h["project_id"], h.get("slug", ""), h.get("title", ""), h.get("description", ""),
                   h.get("author", ""), int(h.get("downloads", 0)), h.get("icon_url") or "",
                   int(h.get("follows", 0) or 0),
                   list(h.get("display_categories") or h.get("categories") or []),
                   list(h.get("versions") or []), h.get("date_modified") or "",
                   int(h.get("color") or 0), h.get("server_side") or "")


def search_modrinth(query: str, limit: int = 20, offset: int = 0, sort: str = "") -> list[PackHit]:
    return search_modrinth_page(query, limit, offset, sort)[0]


def search_modrinth_page(query: str, limit: int = 20, offset: int = 0, sort: str = "") -> tuple[list[PackHit], int]:
    """One page of Modrinth modpack search results plus the total number of hits."""
    facets = json.dumps([["project_type:modpack"]])
    if sort not in SORTS:
        sort = "relevance" if query else "downloads"
    q = urllib.parse.urlencode({"query": query, "facets": facets, "limit": limit, "offset": offset, "index": sort})
    data = get_json(f"{MR_API}/search?{q}")
    return [_hit(h) for h in data.get("hits", [])], int(data.get("total_hits", 0) or 0)


@dataclass
class PackVersion:
    id: str
    name: str
    number: str
    game_versions: list
    loaders: list
    url: str                         # the .mrpack file
    filename: str
    sha1: str = ""

    @property
    def label(self) -> str:
        return f"{self.number} · {', '.join(self.game_versions[:2])} · {', '.join(self.loaders)}"


SUPPORTED_LOADERS = {"fabric", "quilt", "forge", "neoforge"}


def modrinth_versions(project_id: str) -> list[PackVersion]:
    out = []
    for v in get_json(f"{MR_API}/project/{urllib.parse.quote(project_id)}/version"):
        f = next((f for f in v.get("files", []) if f.get("primary")), (v.get("files") or [None])[0])
        if not f or not str(f.get("filename", "")).endswith(".mrpack"):
            continue
        loaders = [l for l in v.get("loaders", []) if l in SUPPORTED_LOADERS]
        if not loaders:
            continue
        out.append(PackVersion(v["id"], v.get("name", ""), v.get("version_number", ""), v.get("game_versions", []),
                               loaders, f["url"], f["filename"], (f.get("hashes") or {}).get("sha1", "")))
    return out


# ------------------------------------------------------------------ CurseForge API
def _cf_request(path: str, key: str, body: dict) -> dict:
    req = urllib.request.Request(CF_API + path, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": key, "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_context()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PackError(_("CurseForge refused the API key (HTTP {0}). Check the key in the modpack window.")
                            .format(e.code)) from e
        raise PackError(f"CurseForge HTTP {e.code}") from e
    except OSError as e:
        raise PackError(_("Could not reach CurseForge: {0}").format(e)) from e


@dataclass
class CfResolved:
    files: list            # PackFile
    manual: list           # (name, page url, target folder)
    skipped: list          # names of client-only / non-server files


def cf_resolve(cf_files: list, key: str, log: Callable[[str], None] = lambda m: None) -> CfResolved:
    """Turn manifest (projectID, fileID) pairs into download URLs with the CurseForge API."""
    if not key:
        raise PackError(_("CurseForge modpacks need a CurseForge API key to download the mods. Get a free key at "
                          "console.curseforge.com and paste it in the modpack window, or use the pack's server "
                          "pack instead."))
    ids = [fid for _pid, fid, _req in cf_files]
    files: dict[int, dict] = {}
    for i in range(0, len(ids), 100):
        for f in _cf_request("/mods/files", key, {"fileIds": ids[i:i + 100]}).get("data", []):
            files[int(f["id"])] = f
    pids = sorted({pid for pid, _fid, _r in cf_files})
    mods: dict[int, dict] = {}
    for i in range(0, len(pids), 100):
        for m in _cf_request("/mods", key, {"modIds": pids[i:i + 100]}).get("data", []):
            mods[int(m["id"])] = m
    res = CfResolved([], [], [])
    for pid, fid, required in cf_files:
        f, m = files.get(fid), mods.get(pid, {})
        if not f:
            res.manual.append((f"project {pid} file {fid}", f"https://www.curseforge.com/projects/{pid}", "mods"))
            continue
        name = f.get("fileName") or f"{fid}.jar"
        gv = [str(g).lower() for g in f.get("gameVersions", [])]
        if "client" in gv and "server" not in gv:
            res.skipped.append(name)                     # marked client-only by its author
            continue
        folder = CF_CLASS_NAMES.get(int(m.get("classId") or CF_CLASS_MODS), "mods")
        if folder in ("resourcepacks", "shaderpacks"):
            res.skipped.append(name)                     # the server does not use these
            continue
        sha1 = next((h["value"] for h in f.get("hashes", []) if h.get("algo") == 1), "")
        url = f.get("downloadUrl")
        if not url:                                      # author disabled third-party downloads
            page = ((m.get("links") or {}).get("websiteUrl") or f"https://www.curseforge.com/projects/{pid}")
            res.manual.append((name, f"{page.rstrip('/')}/files/{fid}", folder))
            continue
        res.files.append(PackFile(f"{folder}/{name}", [url], sha1=sha1, size=int(f.get("fileLength") or 0)))
    return res


# ------------------------------------------------------------------ installing
def _safe_target(folder: Path, rel: str) -> Path:
    """Reject absolute paths and '..' so an archive cannot write outside the server folder."""
    p = PurePosixPath(rel.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or not p.parts or re.match(r"^[A-Za-z]:", rel):
        raise PackError(_("Unsafe path in the modpack: {0}").format(rel))
    return folder.joinpath(*p.parts)


def _extract_dir(z: zipfile.ZipFile, prefix: str, folder: Path, skip=None) -> int:
    n = 0
    prefix = prefix.rstrip("/") + "/" if prefix else ""
    for info in z.infolist():
        if not info.filename.startswith(prefix) or info.is_dir():
            continue
        rel = info.filename[len(prefix):]
        if not rel or (skip and skip(rel)):
            continue
        dest = _safe_target(folder, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
        n += 1
    return n


def _serverpack_skip(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] in SERVERPACK_SKIP_DIRS:
        return True
    return len(parts) == 1 and bool(SERVERPACK_SKIP_FILES.match(parts[0]))


def install_pack(pack: Pack, folder: Path, dl: Callable[..., None], log: Callable[[str], None],
                 sub: Callable[[float], None] = lambda f: None, cf_key: str = "") -> list[str]:
    """Download the pack's server files and copy its overrides into ``folder``.

    ``dl(url, dest, sha1=..., sha512=...)`` downloads one file (raises on failure).
    Returns summary lines for the done page."""
    summary: list[str] = []
    manual: list = []
    files = list(pack.files)
    if pack.kind == "curseforge":
        log(_("Asking CurseForge for {0} files...").format(len(pack.cf_files)))
        res = cf_resolve(pack.cf_files, cf_key, log)
        files, manual = res.files, res.manual
        if res.skipped:
            log(_("Skipped {0} client-only files: {1}").format(len(res.skipped), ", ".join(res.skipped[:8])
                                                               + (" …" if len(res.skipped) > 8 else "")))
    n = len(files)
    for i, f in enumerate(files):
        dest = _safe_target(folder, f.path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        log(f"  + {f.path}")
        last: Optional[Exception] = None
        for url in f.urls or []:
            try:
                dl(url, dest, sha1=f.sha1, sha512=f.sha512)
                last = None
                break
            except Exception as e:  # noqa: BLE001  try the next mirror
                last = e
        if last is not None or not f.urls:
            raise NetError(_("Could not download {0}: {1}").format(f.path, last or _("no download link")))
        sub((i + 1) / max(1, n) * 0.9)
    if n:
        summary.append(_("Modpack {0}: {1} files").format(pack.name, n))

    with zipfile.ZipFile(pack.archive) as z:
        copied = 0
        if pack.kind == "serverpack":
            copied = _extract_dir(z, pack.root, folder, _serverpack_skip)
        else:
            for o in pack.overrides:
                copied += _extract_dir(z, o, folder)
    if copied:
        log(_("Copied {0} config / override files from the modpack").format(copied))
        if pack.kind == "serverpack":
            summary.append(_("Server pack {0}: {1} files copied").format(pack.name, copied))
    sub(1.0)

    if manual:
        lines = [_("These mods could not be downloaded automatically (their authors only allow downloads "
                   "on the CurseForge website). Download each one and put it in the folder shown:"), ""]
        lines += [f"[{target}]  {name}\n    {url}" for name, url, target in manual]
        (folder / "MANUAL_DOWNLOADS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(_("⚠ {0} mods must be downloaded by hand: see MANUAL_DOWNLOADS.txt").format(len(manual)))
        summary.append(_("⚠ {0} mods must be downloaded by hand: see MANUAL_DOWNLOADS.txt").format(len(manual)))
    return summary


def download_mrpack(v: PackVersion, dest_dir: Path, dl: Optional[Callable] = None) -> Path:
    """Download a Modrinth modpack version's .mrpack (small) so it can be read and installed."""
    from .net import download
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / re.sub(r'[\\/:*?"<>|]', "_", v.filename)
    if not dest.is_file():
        (dl or download)(v.url, dest, sha1=v.sha1)
    return dest


__all__ = ["Pack", "PackFile", "PackError", "read_pack", "install_pack", "search_modrinth", "modrinth_versions",
           "download_mrpack", "cf_resolve", "CF_KEY_PAGE"]
