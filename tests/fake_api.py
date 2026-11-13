"""Fake responses that follow each documented API response shape (for offline tests)."""

import json

MANIFEST = {"latest": {"release": "26.3", "snapshot": "26.4-snapshot-2"}, "versions": [
    {"id": "26.4-snapshot-2", "type": "snapshot", "url": "https://x/26.4s2.json"},
    {"id": "26.3", "type": "release", "url": "https://x/26.3.json"},
    {"id": "26.2", "type": "release", "url": "https://x/26.2.json"},
    {"id": "26.1.2", "type": "release", "url": "https://x/26.1.2.json"},
    {"id": "26.1", "type": "release", "url": "https://x/26.1.json"},
    {"id": "1.21.11", "type": "release", "url": "https://x/1.21.11.json"},
    {"id": "1.21.1", "type": "release", "url": "https://x/1.21.1.json"},
    {"id": "1.20.1", "type": "release", "url": "https://x/1.20.1.json"},
    {"id": "1.12.2", "type": "release", "url": "https://x/1.12.2.json"},
    {"id": "b1.7.3", "type": "old_beta", "url": "https://x/b1.7.3.json"},
]}
VJSON = {"downloads": {"server": {"url": "https://piston-data.mojang.com/server.jar", "sha1": ""}},
         "javaVersion": {"majorVersion": 25}}
FILL_PROJECT = {"project": {"id": "paper", "name": "Paper"},
                "versions": {"26.3": ["26.3"], "26.2": ["26.2"], "26.1": ["26.1.2", "26.1.1", "26.1"],
                             "1.21": ["1.21.11", "1.21.10", "1.21.4", "1.21.1"], "1.20": ["1.20.6", "1.20.4"]}}
FILL_BUILDS = [{"id": 31, "channel": "BETA", "downloads": {"server:default": {
    "name": "paper-26.3-31.jar", "url": "https://fill-data.papermc.io/v1/objects/abc/paper-26.3-31.jar",
    "checksums": {"sha256": ""}, "size": 1}}},
    {"id": 30, "channel": "STABLE", "downloads": {"server:default": {
        "name": "paper-26.3-30.jar", "url": "https://fill-data.papermc.io/v1/objects/def/paper-26.3-30.jar",
        "checksums": {"sha256": ""}, "size": 1}}}]
FILL_VERSION = {"version": {"id": "26.3", "java": {"version": {"minimum": 25}, "flags": {"recommended": []}}}}
PURPUR = {"project": "purpur", "versions": ["1.20.4", "1.21.1", "1.21.11", "26.1.2", "26.2", "26.3"]}
PURPUR_V = {"builds": {"latest": "2642", "all": ["2640", "2641", "2642"]}, "project": "purpur", "version": "26.3"}
FABRIC_GAME = [{"version": "26.4-snapshot-2", "stable": False}, {"version": "26.3", "stable": True},
               {"version": "26.2", "stable": True}, {"version": "1.21.11", "stable": True},
               {"version": "1.20.1", "stable": True}]
FABRIC_LOADER = [{"version": "0.19.2", "stable": True}, {"version": "0.19.1", "stable": True}]
FABRIC_INST = [{"version": "1.1.1", "stable": True, "url": "https://x/fabric-installer.jar"}]
QUILT_GAME = [{"version": "1.21.11", "stable": True}, {"version": "1.20.1", "stable": True}]
QUILT_LOADER = [{"version": "0.30.0-beta.3"}, {"version": "0.29.2"}]
QUILT_INST = [{"version": "0.12.1", "url": "https://maven.quiltmc.org/x/quilt-installer-0.12.1.jar"}]
BABRIC_GAME = [{"version": "b1.7.3", "stable": True}]
FORGE_PROMOS = {"homepage": "x", "promos": {"1.20.1-recommended": "47.3.0", "1.20.1-latest": "47.4.10",
                                            "26.1.2-latest": "62.0.12", "1.12.2-recommended": "14.23.5.2859",
                                            "1.7.10-recommended": "10.13.4.1558"}}
FORGE_META = ("<metadata><versioning><versions>" + "".join(
    f"<version>{v}</version>" for v in ["1.20.1-47.3.0", "1.20.1-47.4.10", "26.1.2-62.0.11", "26.1.2-62.0.12"])
    + "</versions></versioning></metadata>")
NEO_META = ("<metadata><versioning><versions>" + "".join(
    f"<version>{v}</version>" for v in ["20.4.237", "21.0.167", "21.1.215", "21.1.219",
                                        "26.1.0.0-alpha.2+snapshot-1", "26.1.0.1-beta", "26.1.0.10-beta",
                                        "26.1.2.31", "26.1.2.35", "26.3.0.4-beta"])
    + "</versions></versioning></metadata>")


MOHIST_NEW_VERSIONS = [{"name": "1.20.1"}, {"name": "1.21.1"}, {"name": "1.16.5"}]
MOHIST_NEW_BUILDS = [{"id": 161, "fileMd5": "", "createdAt": 1}, {"id": 160}]
YOUER_OLD = {"versions": ["1.21.1", "26.1.2"]}
YOUER_OLD_BUILDS = {"builds": [{"number": 418, "url": "https://mohistmc.com/api/v2/projects/youer/1.21.1/builds/418/download"},
                               {"number": 419, "url": "https://mohistmc.com/api/v2/projects/youer/1.21.1/builds/419/download"}]}
ARC = [{"tag_name": "FeudalKings/1.0.2", "prerelease": False, "assets": [
    {"name": "arclight-neoforge-1.21.1-1.0.2.jar", "browser_download_url": "https://github.com/a/neo-1.21.1.jar"},
    {"name": "arclight-fabric-1.21.1-1.0.2.jar", "browser_download_url": "https://github.com/a/fab-1.21.1.jar"},
    {"name": "arclight-forge-1.21.1-1.0.2.jar", "browser_download_url": "https://github.com/a/forge-1.21.1.jar"}]},
    {"tag_name": "Trials/1.0.6", "prerelease": False, "assets": [
    {"name": "arclight-forge-1.20.1-1.0.6.jar", "browser_download_url": "https://github.com/a/forge-1.20.1.jar"}]},
    {"tag_name": "x/1.21.11", "prerelease": True, "assets": [
    {"name": "arclight-neoforge-1.21.11-1.0.0-SNAPSHOT.jar", "browser_download_url": "https://github.com/a/neo-1.21.11.jar"}]}]


MR_PROJECTS = {
    "sodium": ("Sodium", "Rendering engine", "jellysquid", 90_000_000, "mod", []),
    "lithium": ("Lithium", "Server optimization mod", "jellysquid", 60_000_000, "mod", ["fabric-api"]),
    "fabric-api": ("Fabric API", "Core API for Fabric mods", "modmuss", 120_000_000, "mod", []),
    "jei": ("Just Enough Items", "Item and recipe viewing mod", "mezz", 300_000_000, "mod", ["architectury"]),
    "architectury": ("Architectury API", "Multiplatform API", "shedaniel", 80_000_000, "mod", []),
    "luckperms": ("LuckPerms", "Permissions plugin", "Luck", 9_000_000, "plugin", []),
    "essentialsx": ("EssentialsX", "Essential commands plugin", "md678685", 5_000_000, "plugin", ["vault"]),
    "vault": ("Vault", "Economy API", "MilkBowl", 4_000_000, "plugin", []),
    "terralith": ("Terralith", "Overworld datapack", "Stardust", 20_000_000, "datapack", []),
    "fabulously-optimized": ("Fabulously Optimized", "Improved performance and graphics", "robotkoer", 30_000_000,
                             "modpack", []),
    "cobblemon-official": ("Cobblemon Official Modpack", "The official Cobblemon pack", "Cobblemon", 9_000_000,
                           "modpack", []),
    "better-mc": ("Better MC [FORGE]", "Vanilla+ with 200+ mods", "LunaPixel", 12_000_000, "modpack", []),
}


def _mr_search(url):
    import urllib.parse, json as _j
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    facets = _j.loads(q["facets"][0])
    ptype = facets[0][0].split(":")[1]
    query = q.get("query", [""])[0].lower()
    hits = []
    for pid, (t, d, a, dl, k, deps) in MR_PROJECTS.items():
        if k == ptype and (not query or query in t.lower()):
            extra = MR_PACK_META.get(pid, {}) if k == "modpack" else {}
            hits.append({"project_id": pid, "slug": pid, "title": t, "description": d, "author": a,
                         "downloads": dl, "icon_url": extra.get("icon_url", ""), "project_type": k,
                         "follows": extra.get("follows", 0), "display_categories": extra.get("cats", []),
                         "versions": extra.get("versions", []), "date_modified": extra.get("updated", ""),
                         "color": extra.get("color", 0), "server_side": extra.get("server_side", "")})
    sort = q.get("index", ["downloads"])[0]
    key = {"follows": "follows", "updated": "date_modified", "newest": "date_modified"}.get(sort, "downloads")
    hits.sort(key=lambda h: h[key], reverse=True)
    off, lim = int(q.get("offset", ["0"])[0]), int(q.get("limit", ["20"])[0])
    return {"hits": hits[off:off + lim], "total_hits": len(hits), "offset": off, "limit": lim}


MR_PACK_META = {
    "fabulously-optimized": {"icon_url": "https://cdn.modrinth.com/data/fo/icon.png", "follows": 4_200,
                             "cats": ["fabric", "optimization", "lightweight"], "color": 0x7DB4E6,
                             "versions": ["1.20.1", "1.21", "1.21.1"], "updated": "2026-11-09T10:00:00Z",
                             "server_side": "optional"},
    "cobblemon-official": {"icon_url": "https://cdn.modrinth.com/data/cobble/icon.png", "follows": 2_800,
                           "cats": ["fabric", "adventure", "multiplayer"], "color": 0xE8604C,
                           "versions": ["1.21.1"], "updated": "2026-10-28T10:00:00Z", "server_side": "required"},
    "better-mc": {"icon_url": "https://cdn.modrinth.com/data/bmc/icon.png", "follows": 1_900,
                  "cats": ["forge", "adventure", "magic", "technology"], "color": 0x5FB85A,
                  "versions": ["1.19.2", "1.20.1"], "updated": "2026-08-02T10:00:00Z", "server_side": "required"},
}


def fake_icon(url: str) -> bytes:
    """A small original PNG icon (coloured tile with a block shape) for fake Modrinth projects."""
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    from PyQt6.QtGui import QColor, QImage, QPainter
    import zlib
    c = QColor.fromHsv(zlib.crc32(url.encode()) % 360, 150, 210)
    img = QImage(96, 96, QImage.Format.Format_ARGB32)
    img.fill(c.darker(160))
    p = QPainter(img)
    p.fillRect(20, 20, 56, 56, c)
    p.fillRect(20, 20, 56, 14, c.lighter(140))
    p.fillRect(38, 46, 20, 20, c.darker(130))
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def _mr_versions(pid):
    t, d, a, dl, k, deps = MR_PROJECTS[pid]
    if k == "modpack":
        loader = "forge" if "forge" in t.lower() else "fabric"
        return [{"id": f"{pid}-{i}", "name": f"{t} {n}", "version_number": n, "game_versions": [mc],
                 "loaders": [loader], "files": [{"url": f"https://cdn.modrinth.com/data/{pid}/{pid}-{n}.mrpack",
                                                 "filename": f"{pid}-{n}.mrpack", "primary": True,
                                                 "hashes": {"sha1": ""}}]}
                for i, (n, mc) in enumerate((("6.2.0", "1.21.1"), ("5.9.1", "1.20.1")))]
    if pid == "sodium":
        return []   # scenario: no version compatible with the server
    return [{"id": f"{pid}-v2", "project_id": pid, "version_number": "2.0.0", "version_type": "release",
             "files": [{"url": f"https://cdn.modrinth.com/data/{pid}/{pid}-2.0.0.jar",
                        "filename": f"{pid}-2.0.0.{'zip' if k == 'datapack' else 'jar'}", "primary": True,
                        "hashes": {"sha1": "", "sha512": ""}}],
             "dependencies": [{"project_id": x, "dependency_type": "required"} for x in deps] +
                             [{"project_id": "optional-thing", "dependency_type": "optional"}]}]


def route(url: str):
    if "api.modrinth.com/v2/search" in url:
        return _mr_search(url)
    if "api.modrinth.com/v2/project/" in url:
        pid = url.split("/project/")[1].split("/")[0].split("?")[0]
        if "/version" in url:
            return _mr_versions(pid)
        t, d, a, dl, k, deps = MR_PROJECTS[pid]
        return {"id": pid, "title": t, "project_type": k}
    if "api.mohistmc.com/project/mohist" in url:
        return MOHIST_NEW_BUILDS if url.endswith("/builds") else MOHIST_NEW_VERSIONS
    if "api.mohistmc.com/project/banner" in url:
        return [{"id": 77}] if url.endswith("/builds") else ["1.20.1", "1.21.1"]
    if "api.mohistmc.com/project/youer" in url:
        raise RuntimeError("502 bad gateway")          # new API down -> must fall back to the old v2 API
    if "mohistmc.com/api/v2/projects/youer" in url:
        return YOUER_OLD_BUILDS if url.endswith("/builds") else YOUER_OLD
    if "api.github.com/repos/IzzelAliz/Arclight" in url:
        return ARC
    if "version_manifest" in url:
        return MANIFEST
    if url.startswith("https://x/") and url.endswith(".json"):
        return VJSON
    if "fill.papermc.io" in url:
        if url.endswith("/builds"):
            return FILL_BUILDS
        if "/versions/" in url:
            return FILL_VERSION
        return FILL_PROJECT
    if "purpurmc" in url:
        return PURPUR_V if url.rstrip("/").split("/")[-1][0].isdigit() else PURPUR
    if "fabricmc" in url or "babric" in url or "legacyfabric" in url:
        if url.endswith("/game"):
            if "legacyfabric" in url:
                return [{"version": "1.13.2", "stable": True}, {"version": "1.12.2", "stable": True},
                        {"version": "1.8.9", "stable": True}, {"version": "1.7.10", "stable": True}]
            return BABRIC_GAME if "babric" in url else FABRIC_GAME
        if url.endswith("/loader"):
            return FABRIC_LOADER
        if url.endswith("/installer"):
            return FABRIC_INST
    if "quiltmc" in url:
        if url.endswith("/game"):
            return QUILT_GAME
        if url.endswith("/loader"):
            return QUILT_LOADER
        if url.endswith("/installer"):
            return QUILT_INST
    if "promotions_slim" in url:
        return FORGE_PROMOS
    raise RuntimeError("no fake for " + url)


def get_json(url, timeout=30):
    return json.loads(json.dumps(route(url)))


def get_bytes(url, timeout=30, cache_sec=0, retries=3):
    if url.endswith("icon.png"):
        return fake_icon(url)
    if "neoforged" in url:
        return NEO_META.encode()
    if "minecraftforge" in url:
        return FORGE_META.encode()
    return json.dumps(route(url)).encode()


CF_PACKS = [
    {"id": 715572, "slug": "all-the-mods-9", "name": "All the Mods 9 - ATM9", "summary": "Kitchen sink pack with 400+ mods",
     "downloadCount": 21_500_000, "thumbsUpCount": 900, "dateModified": "2026-11-02T08:00:00Z",
     "logo": {"thumbnailUrl": "https://media.forgecdn.net/avatars/thumbnails/atm9/icon.png"},
     "authors": [{"name": "ATMTeam"}], "categories": [{"name": "Tech"}, {"name": "Magic"}, {"name": "Exploration"}],
     "links": {"websiteUrl": "https://www.curseforge.com/minecraft/modpacks/all-the-mods-9"},
     "latestFilesIndexes": [{"gameVersion": "1.20.1", "modLoader": 1}]},
    {"id": 452013, "slug": "rlcraft", "name": "RLCraft", "summary": "Hardcore realism",
     "downloadCount": 20_100_000, "thumbsUpCount": 700, "dateModified": "2026-06-10T08:00:00Z",
     "logo": {"thumbnailUrl": "https://media.forgecdn.net/avatars/thumbnails/rl/icon.png"},
     "authors": [{"name": "Shivaxi"}], "categories": [{"name": "Adventure and RPG"}],
     "links": {"websiteUrl": "https://www.curseforge.com/minecraft/modpacks/rlcraft"},
     "latestFilesIndexes": [{"gameVersion": "1.12.2", "modLoader": 1}]},
    {"id": 925200, "slug": "cozy-fabric", "name": "Cozy Fabric", "summary": "Relaxed Fabric survival",
     "downloadCount": 450_000, "thumbsUpCount": 40, "dateModified": "2026-11-11T08:00:00Z",
     "logo": {"thumbnailUrl": "https://media.forgecdn.net/avatars/thumbnails/cozy/icon.png"},
     "authors": [{"name": "Cozy"}], "categories": [{"name": "Multiplayer"}],
     "links": {"websiteUrl": "https://www.curseforge.com/minecraft/modpacks/cozy-fabric"},
     "latestFilesIndexes": [{"gameVersion": "1.21.1", "modLoader": 4}]},
]
CF_FILES = {
    715572: [{"id": 5001, "displayName": "All the Mods 9-0.3.0", "fileName": "ATM9-0.3.0.zip",
              "gameVersions": ["1.20.1", "Forge"], "fileDate": "2026-11-02T08:00:00Z", "isServerPack": False,
              "serverPackFileId": 5002, "downloadUrl": "https://edge.forgecdn.net/files/5/1/ATM9-0.3.0.zip",
              "hashes": []},
             {"id": 5002, "displayName": "Server", "fileName": "ServerFiles-0.3.0.zip", "isServerPack": True,
              "gameVersions": ["1.20.1"], "fileDate": "2026-11-02T08:00:00Z",
              "downloadUrl": "https://edge.forgecdn.net/files/5/2/ServerFiles-0.3.0.zip", "hashes": []}],
    925200: [{"id": 6001, "displayName": "Cozy 1.2", "fileName": "Cozy-1.2.zip", "gameVersions": ["1.21.1", "Fabric"],
              "fileDate": "2026-11-11T08:00:00Z", "isServerPack": False, "serverPackFileId": 0,
              "downloadUrl": None, "hashes": []}],
}


def cf_get(path, key, params=None):
    """Fake CurseForge REST API (GET)."""
    from mcsi.core.modpack import PackError
    if not key:
        raise PackError("no key")
    if path == "/mods/search":
        q = (params or {}).get("searchFilter", "").lower()
        hits = [m for m in CF_PACKS if q in m["name"].lower()]
        off, lim = int(params.get("index", 0)), int(params.get("pageSize", 20))
        return {"data": hits[off:off + lim], "pagination": {"index": off, "pageSize": lim,
                                                            "resultCount": len(hits[off:off + lim]),
                                                            "totalCount": len(hits)}}
    parts = path.strip("/").split("/")
    mod = int(parts[1])
    if len(parts) == 3:
        return {"data": CF_FILES.get(mod, []), "pagination": {"totalCount": len(CF_FILES.get(mod, []))}}
    fid = int(parts[3])
    return {"data": next(f for f in CF_FILES.get(mod, []) if f["id"] == fid)}


def install():
    """Route every provider / Modrinth request to the fakes above."""
    import mcsi.core.modpack as MP
    import mcsi.core.modrinth as M
    import mcsi.core.providers as P
    P.get_json = get_json
    P.get_bytes = get_bytes
    M.get_json = get_json
    MP.get_json = get_json
    MP._cf_get = cf_get
