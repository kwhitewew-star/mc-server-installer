"""Modrinth API v2: search mods/plugins/datapacks, pick compatible versions, resolve required dependencies."""

from __future__ import annotations
from ..i18n import _

import json
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Optional

from .net import NetError, get_json

API = "https://api.modrinth.com/v2"

# content kinds and Modrinth loader names per server type
PLUGIN_LOADERS = {
    "paper": ["paper", "spigot", "bukkit"],
    "purpur": ["purpur", "paper", "spigot", "bukkit"],
    "folia": ["folia"],
    "spigot": ["spigot", "bukkit"],
    "bukkit": ["bukkit"],
    "mohist": ["bukkit", "spigot", "paper"],
    "youer": ["bukkit", "spigot", "paper"],
    "arclight": ["bukkit", "spigot", "paper"],
    "banner": ["bukkit", "spigot", "paper"],
}
MOD_LOADERS = {
    "fabric": ["fabric"],
    "quilt": ["quilt", "fabric"],
    "babric": ["babric"],
    "legacyfabric": ["legacy-fabric"],
    "forge": ["forge"],
    "neoforge": ["neoforge"],
    "mohist": ["forge"],
    "youer": ["neoforge"],
    "banner": ["fabric"],
}
KIND_LABEL = {"mod": _("Mod"), "plugin": _("Plugin"), "datapack": _("Datapack")}
KIND_DIR = {"mod": "mods", "plugin": "plugins", "datapack": "datapacks"}


def loaders_for(server: str, kind: str, build: str = "") -> list[str]:
    if kind == "datapack":
        return ["datapack"]
    if kind == "plugin":
        return PLUGIN_LOADERS.get(server, [])
    if server == "arclight":  # Arclight's loader depends on the chosen build file
        b = (build or "").lower()
        return ["neoforge"] if "neoforge" in b else ["fabric"] if "fabric" in b else ["forge"]
    return MOD_LOADERS.get(server, [])


def kinds_for(server: str) -> list[str]:
    out = []
    if server in MOD_LOADERS or server == "arclight":
        out.append("mod")
    if server in PLUGIN_LOADERS:
        out.append("plugin")
    out.append("datapack")
    return out


@dataclass
class Hit:
    project_id: str
    slug: str
    title: str
    description: str
    author: str
    downloads: int
    icon_url: str
    kind: str


@dataclass
class Addon:
    """An item in the install list (Modrinth or a local file)."""
    kind: str
    title: str
    project_id: str = ""
    version_id: str = ""
    version_number: str = ""
    url: str = ""
    filename: str = ""
    sha1: str = ""
    sha512: str = ""
    local_path: str = ""
    dependency_of: str = ""        # parent name if added automatically as a dependency
    deps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Addon":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _q(obj) -> str:
    return urllib.parse.quote(json.dumps(obj, separators=(",", ":")))


def search(query: str, kind: str, server: str, mc: str, build: str = "", offset: int = 0,
           limit: int = 20, hide_client_only: bool = True) -> tuple[list[Hit], int]:
    loaders = loaders_for(server, kind, build)
    if not loaders:
        return [], 0
    facets = [[f"project_type:{kind}"], [f"categories:{l}" for l in loaders], [f"versions:{mc}"]]
    if hide_client_only and kind == "mod":
        facets.append(["server_side:required", "server_side:optional"])
    index = "relevance" if query.strip() else "downloads"
    url = (f"{API}/search?query={urllib.parse.quote(query.strip())}&facets={_q(facets)}"
           f"&index={index}&offset={offset}&limit={limit}")
    data = get_json(url)
    hits = [Hit(h["project_id"], h.get("slug", ""), h.get("title", "?"), h.get("description", ""),
                h.get("author", ""), int(h.get("downloads", 0)), h.get("icon_url") or "", kind)
            for h in data.get("hits", [])]
    return hits, int(data.get("total_hits", len(hits)))


def best_version(project_id: str, kind: str, server: str, mc: str, build: str = "") -> Optional[dict]:
    loaders = loaders_for(server, kind, build)
    url = f"{API}/project/{project_id}/version?loaders={_q(loaders)}&game_versions={_q([mc])}"
    versions = get_json(url)
    if not versions:
        return None
    for vt in ("release", "beta", "alpha"):  # newest release, then beta, then alpha
        for v in versions:
            if v.get("version_type") == vt and v.get("files"):
                return v
    return None


def _addon_from_version(v: dict, kind: str, title: str, parent: str = "") -> Addon:
    files = v["files"]
    f = next((x for x in files if x.get("primary")), files[0])
    hashes = f.get("hashes", {})
    deps = [d.get("project_id") or "" for d in v.get("dependencies", [])
            if d.get("dependency_type") == "required" and d.get("project_id")]
    return Addon(kind=kind, title=title, project_id=v["project_id"], version_id=v["id"],
                 version_number=v.get("version_number", ""), url=f["url"], filename=f["filename"],
                 sha1=hashes.get("sha1", ""), sha512=hashes.get("sha512", ""), dependency_of=parent, deps=deps)


def resolve(project_id: str, title: str, kind: str, server: str, mc: str, build: str,
            existing: set[str], max_depth: int = 4) -> tuple[list[Addon], list[str]]:
    """Resolve one project and its required dependencies; returns (addons, warnings).
    Raises NetError if the project itself has no compatible version; a missing dependency only adds a warning."""
    out: list[Addon] = []
    warns: list[str] = []
    seen = set(existing)

    def go(pid: str, name: str, parent: str, depth: int):
        if pid in seen or depth > max_depth:
            return
        kk = kind
        v = best_version(pid, kind, server, mc, build)
        if v is None and parent:
            # a dependency can be a different kind (e.g. a library, not a plugin) -> check the project info
            try:
                info = get_json(f"{API}/project/{pid}")
                k2 = info.get("project_type", kind)
                name = info.get("title", name)
                if k2 != kind and k2 in KIND_DIR:
                    kk = k2
                    v = best_version(pid, k2, server, mc, build)
            except NetError:
                v = None
        if v is None:
            if parent:
                warns.append(_("'{1}', required by '{0}', has no file for {2} and was left out. Add it manually if the server fails to start.").format(parent, name, mc))
                seen.add(pid)
                return
            raise NetError(_("'{0}' has no file compatible with this server type and version {1}.").format(name, mc))
        seen.add(pid)
        a = _addon_from_version(v, kk, name, parent)
        out.append(a)
        for dep in a.deps:
            if dep not in seen:
                dep_name = dep
                try:
                    dep_name = get_json(f"{API}/project/{dep}").get("title", dep)
                except NetError:
                    pass
                go(dep, dep_name, name, depth + 1)

    go(project_id, title, "", 0)
    return out, warns


def fmt_downloads(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)
