"""Modpacks: reading .mrpack / CurseForge zips / server packs and installing them (offline)."""

import json
import os
import zipfile

import pytest

from mcsi.core import installer as I
from mcsi.core import modpack as M
from mcsi.core import schema


def mrpack(path, deps=None, files=None):
    idx = {"formatVersion": 1, "game": "minecraft", "versionId": "1.2.0", "name": "Cozy Pack",
           "dependencies": deps or {"minecraft": "1.21.1", "fabric-loader": "0.16.9"},
           "files": files if files is not None else [
               {"path": "mods/lithium.jar", "hashes": {"sha1": "a" * 40, "sha512": "b" * 128},
                "env": {"client": "required", "server": "required"},
                "downloads": ["https://cdn.modrinth.com/data/x/lithium.jar"], "fileSize": 10},
               {"path": "mods/voicechat-fabric-2.5.jar", "hashes": {"sha1": "c" * 40},
                "downloads": ["https://bad.example/vc.jar", "https://cdn.modrinth.com/data/y/vc.jar"]},
               {"path": "mods/iris.jar", "hashes": {"sha1": "d" * 40},
                "env": {"client": "required", "server": "unsupported"},
                "downloads": ["https://cdn.modrinth.com/data/z/iris.jar"]}]}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("modrinth.index.json", json.dumps(idx))
        z.writestr("overrides/config/lithium.properties", "a=1\n")
        z.writestr("overrides/server.properties", "motd=from pack\n")
        z.writestr("server-overrides/config/lithium.properties", "a=2\n")
        z.writestr("client-overrides/options.txt", "x\n")
    return path


def test_read_mrpack(tmp_path):
    p = M.read_pack(mrpack(tmp_path / "cozy.mrpack"))
    assert (p.kind, p.name, p.mc, p.server, p.build) == ("modrinth", "Cozy Pack", "1.21.1", "fabric", "0.16.9")
    assert [f.path for f in p.files if not f.client] == ["mods/lithium.jar", "mods/voicechat-fabric-2.5.jar"]
    assert [f.path for f in p.files if f.client] == ["mods/iris.jar"]     # downloaded, decided after install
    assert M.Pack.from_dict(json.loads(json.dumps(p.to_dict()))) == p


@pytest.mark.parametrize("deps, server, build", [
    ({"minecraft": "1.20.1", "forge": "47.2.0"}, "forge", "47.2.0"),
    ({"minecraft": "1.21.1", "neoforge": "21.1.80"}, "neoforge", "21.1.80"),
    ({"minecraft": "1.20.1", "neoforge": "47.1.106"}, "forge", ""),       # NeoForge 1.20.1 -> Forge
    ({"minecraft": "1.21.1", "quilt-loader": "0.27.1"}, "quilt", "0.27.1"),
])
def test_loaders(tmp_path, deps, server, build):
    p = M.read_pack(mrpack(tmp_path / "x.mrpack", deps=deps, files=[]))
    assert (p.server, p.build) == (server, build)


def cf_zip(path, loader="forge-47.2.0"):
    man = {"minecraft": {"version": "1.20.1", "modLoaders": [{"id": loader, "primary": True}]},
           "manifestType": "minecraftModpack", "manifestVersion": 1, "name": "All the Tests", "version": "3.1",
           "files": [{"projectID": 1, "fileID": 11, "required": True}, {"projectID": 2, "fileID": 22},
                     {"projectID": 3, "fileID": 33}, {"projectID": 4, "fileID": 44}],
           "overrides": "overrides"}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(man))
        z.writestr("overrides/config/jei.toml", "x=1\n")
    return path


def test_read_curseforge(tmp_path):
    p = M.read_pack(cf_zip(tmp_path / "att.zip"))
    assert (p.kind, p.mc, p.server, p.build, len(p.cf_files)) == ("curseforge", "1.20.1", "forge", "47.2.0", 4)
    p2 = M.read_pack(cf_zip(tmp_path / "f.zip", "fabric-0.15.11"))
    assert (p2.server, p2.build) == ("fabric", "0.15.11")


def test_curseforge_needs_key(tmp_path):
    with pytest.raises(M.PackError, match="API key"):
        M.cf_resolve([(1, 11, True)], "")


def test_curseforge_resolve(monkeypatch):
    def fake(path, key, body):
        assert key == "k"
        if path == "/mods/files":
            return {"data": [
                {"id": 11, "fileName": "jei.jar", "downloadUrl": "https://edge.forgecdn.net/files/0/11/jei.jar",
                 "hashes": [{"value": "e" * 40, "algo": 1}], "gameVersions": ["1.20.1", "Forge", "Server", "Client"]},
                {"id": 22, "fileName": "optifine-ish.jar", "downloadUrl": "https://x/o.jar",
                 "gameVersions": ["1.20.1", "Client"]},
                {"id": 33, "fileName": "secret.jar", "downloadUrl": None, "gameVersions": ["1.20.1"]},
                {"id": 44, "fileName": "pretty.zip", "downloadUrl": "https://x/p.zip", "gameVersions": ["1.20.1"]}]}
        return {"data": [{"id": 1, "classId": 6}, {"id": 2, "classId": 6},
                         {"id": 3, "classId": 6, "links": {"websiteUrl": "https://www.curseforge.com/minecraft/mc-mods/secret"}},
                         {"id": 4, "classId": 12}]}
    monkeypatch.setattr(M, "_cf_request", fake)
    r = M.cf_resolve([(1, 11, True), (2, 22, True), (3, 33, True), (4, 44, True)], "k")
    assert [f.path for f in r.files if not f.client] == ["mods/jei.jar"] and r.files[0].sha1 == "e" * 40
    assert [f.path for f in r.files if f.client] == ["mods/optifine-ish.jar"]
    assert r.manual == [("secret.jar", "https://www.curseforge.com/minecraft/mc-mods/secret/files/33", "mods")]
    assert sorted(r.skipped) == ["pretty.zip"]


def serverpack(path, kind="forge"):
    with zipfile.ZipFile(path, "w") as z:
        top = "ATT Server Files/"
        if kind == "forge":
            z.writestr(top + "forge-1.20.1-47.2.0-installer.jar", "x")
        elif kind == "vars":
            z.writestr(top + "variables.txt", 'MINECRAFT_VERSION=1.21.1\nMODLOADER=NeoForge\nMODLOADER_VERSION=21.1.80\n')
        elif kind == "fabric":
            z.writestr(top + "libraries/net/fabricmc/fabric-loader/0.16.9/fabric-loader-0.16.9.jar", "x")
            z.writestr(top + "libraries/net/fabricmc/intermediary/1.21.1/intermediary-1.21.1.jar", "x")
        z.writestr(top + "mods/create.jar", "mod")
        z.writestr(top + "config/create.toml", "c=1\n")
        z.writestr(top + "startserver.bat", "old script")
        z.writestr(top + "libraries/x/y.jar", "lib")
        z.writestr(top + "server.properties", "motd=pack\n")
    return path


@pytest.mark.parametrize("kind, server, mc, build", [
    ("forge", "forge", "1.20.1", "47.2.0"), ("vars", "neoforge", "1.21.1", "21.1.80"),
    ("fabric", "fabric", "1.21.1", "0.16.9")])
def test_read_serverpack(tmp_path, kind, server, mc, build):
    p = M.read_pack(serverpack(tmp_path / "sp.zip", kind))
    assert (p.kind, p.server, p.mc, p.build, p.root) == ("serverpack", server, mc, build, "ATT Server Files/")


def test_not_a_pack(tmp_path):
    with zipfile.ZipFile(tmp_path / "x.zip", "w") as z:
        z.writestr("readme.txt", "hi")
    with pytest.raises(M.PackError):
        M.read_pack(tmp_path / "x.zip")
    (tmp_path / "y.zip").write_text("not a zip")
    with pytest.raises(M.PackError):
        M.read_pack(tmp_path / "y.zip")


def test_unsafe_paths_are_rejected(tmp_path):
    for bad in ("../evil.jar", "/etc/passwd", "C:/Windows/x.dll", "mods/../../x"):
        with pytest.raises(M.PackError):
            M._safe_target(tmp_path, bad)


# ---------------------------------------------------------------- full installs with fake downloads / java
pytestmark_posix = pytest.mark.skipif(os.name == "nt", reason="fake java needs a POSIX shell")


def plan_for(pack, folder, java):
    vals = schema.defaults()
    vals.update({"manage:first_run": False})
    return I.Plan(server=pack.server, mc=pack.mc, build=pack.build, folder=str(folder), ram_gb=4, java=java,
                  java_major=25, values=vals, eula=True, modpack=pack.to_dict())


@pytestmark_posix
def test_install_mrpack(tmp_path, fake_java, no_downloads, no_upnp):
    pack = M.read_pack(mrpack(tmp_path / "cozy.mrpack"))
    srv = tmp_path / "server"
    real = no_downloads

    stages = []
    inst = I.Installer(plan_for(pack, srv, fake_java), lambda s: None, lambda v: None,
                       lambda i, t: stages.append(i), lambda: False)
    inst.execute()
    assert (srv / "mods" / "lithium.jar").exists() and (srv / "mods" / "voicechat-fabric-2.5.jar").exists()
    assert not (srv / "mods" / "iris.jar").exists() and (srv / "mods_disabled" / "iris.jar").exists()
    assert (srv / "config" / "lithium.properties").read_text() == "a=2\n"       # server-overrides win
    assert not (srv / "options.txt").exists()
    assert "https://cdn.modrinth.com/data/x/lithium.jar" in real
    assert 2 in stages
    assert (24454, "UDP") in [(p, pr) for p, pr in no_upnp[0]]                  # voice chat port found


@pytestmark_posix
def test_install_serverpack_keeps_pack_files_but_not_its_scripts(tmp_path, fake_java, no_downloads, no_upnp):
    pack = M.read_pack(serverpack(tmp_path / "sp.zip", "fabric"))
    srv = tmp_path / "server"
    I.Installer(plan_for(pack, srv, fake_java), lambda s: None, lambda v: None, lambda i, t: None,
                lambda: False).execute()
    assert (srv / "mods" / "create.jar").read_text() == "mod" and (srv / "config" / "create.toml").exists()
    assert not (srv / "startserver.bat").exists() and not (srv / "libraries" / "x").exists()
    assert "fabric-server-launch.jar" in (srv / "start.bat").read_text()      # our own launch script


@pytestmark_posix
def test_install_curseforge_writes_manual_list(tmp_path, fake_java, no_downloads, no_upnp, monkeypatch):
    pack = M.read_pack(cf_zip(tmp_path / "att.zip", "fabric-0.15.11"))
    monkeypatch.setattr(M, "cf_resolve", lambda files, key, log=None: M.CfResolved(
        [M.PackFile("mods/jei.jar", ["https://edge.forgecdn.net/jei.jar"], sha1="e" * 40)],
        [("secret.jar", "https://www.curseforge.com/x/files/33", "mods")], ["client.jar"]))
    srv = tmp_path / "server"
    plan = plan_for(pack, srv, fake_java)
    plan.cf_key = "k"
    inst = I.Installer(plan, lambda s: None, lambda v: None, lambda i, t: None, lambda: False)
    inst.execute()
    assert (srv / "mods" / "jei.jar").exists() and (srv / "config" / "jei.toml").exists()
    assert "secret.jar" in (srv / "MANUAL_DOWNLOADS.txt").read_text()
    assert any("MANUAL_DOWNLOADS" in s for s in inst.summary)


def test_search_page_has_card_details():
    hits, total = M.search_modrinth_page("", 2, 0, "downloads")
    assert total == 3 and len(hits) == 2
    fo = hits[0]
    assert fo.title == "Fabulously Optimized" and fo.icon_url.endswith("icon.png")
    assert fo.follows == 4200 and "optimization" in fo.categories and fo.latest_mc == "1.21.1"
    more, _t = M.search_modrinth_page("", 2, 2, "downloads")
    assert [h.title for h in more] == ["Cobblemon Official Modpack"]
    assert M.search_modrinth_page("", 5, 0, "follows")[0][0].follows == 4200


def test_pack_icon_survives_round_trip():
    p = M.Pack("modrinth", "X", icon_url="https://cdn/x.png", icon_color=123)
    d = p.to_dict()
    d["unknown_future_key"] = 1
    q = M.Pack.from_dict(d)
    assert q.icon_url == "https://cdn/x.png" and q.icon_color == 123


def test_relative_time():
    from datetime import datetime, timezone
    from mcsi.ui.modpack_picker import ago, tag_name
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    assert ago("2026-11-09T00:00:00Z", now) == "3 days ago"
    assert ago("2026-11-11T21:00:00Z", now) == "3 h ago"
    assert ago("2025-10-01T00:00:00Z", now) == "1 years ago"
    assert ago("", now) == "" and ago("garbage", now) == ""
    assert tag_name("neoforge") == "NeoForge" and tag_name("some-new-tag") == "Some new tag"


# ---------------------------------------------------------------- CurseForge search / key / server packs
def test_cfkey_order_and_mask(monkeypatch):
    from mcsi.core import cfkey
    monkeypatch.setattr(cfkey, "_user", "")
    monkeypatch.delenv(cfkey.ENV, raising=False)
    monkeypatch.setattr(cfkey, "builtin", lambda: "BUILTIN")
    assert cfkey.get() == "BUILTIN" and cfkey.source() == "builtin"
    monkeypatch.setenv(cfkey.ENV, "ENVKEY")
    assert cfkey.get() == "ENVKEY" and cfkey.source() == "env"
    assert cfkey.get("mine") == "mine" and cfkey.source("mine") == "user"
    k = "$2a$10$abcdefghijklmnopqrstuv"
    assert cfkey._unmask(cfkey.mask(k)) == k and k not in cfkey.mask(k)
    assert cfkey.headers_for("https://edge.forgecdn.net/files/1/2/a.jar") == {"x-api-key": "ENVKEY"}
    assert cfkey.headers_for("https://mediafilez.forgecdn.net/files/1/2/a.jar") == {"x-api-key": "ENVKEY"}
    assert cfkey.headers_for("https://cdn.modrinth.com/data/x.jar") == {}
    assert cfkey.headers_for("https://evilforgecdn.net/x") == {}


def test_download_sends_key_only_to_curseforge_cdn(monkeypatch, tmp_path):
    import io
    from mcsi.core import cfkey, net
    monkeypatch.setenv(cfkey.ENV, "K")
    seen = []

    class Resp(io.BytesIO):
        status = 200
        headers = {"Content-Length": "3"}

    def fake_open(url, timeout=30, retries=3, method="GET", headers=None):
        seen.append(headers)
        return Resp(b"abc")

    monkeypatch.setattr(net, "open_url", fake_open)
    net.download("https://edge.forgecdn.net/files/1/2/a.jar", tmp_path / "a.jar")
    net.download("https://cdn.modrinth.com/data/a.jar", tmp_path / "b.jar")
    assert seen[0] == {"x-api-key": "K"} and not seen[1]


def test_curseforge_search_and_versions():
    hits, total = M.search_curseforge_page("", "k", 2, 0, "popularity")
    assert total == 3 and len(hits) == 2
    atm = hits[0]
    assert (atm.source, atm.title, atm.author, atm.latest_mc) == ("curseforge", "All the Mods 9 - ATM9", "ATMTeam", "1.20.1")
    assert atm.categories[0] == "forge" and "Magic" in atm.categories and atm.icon_url.endswith("icon.png")
    vs = M.curseforge_versions(atm.project_id, "k", atm.page_url)
    assert len(vs) == 1 and vs[0].server_pack_id == 5002 and vs[0].loaders == ["forge"]   # server pack hidden
    assert "✓" in vs[0].label
    with pytest.raises(M.PackError):
        M.search_curseforge_page("", "", 2, 0)
    assert M.search_curseforge_page("", "k", 50, 9990) == ([], 10_000)


def test_curseforge_prefers_server_pack(tmp_path):
    got = []

    def dl(url, dest, sha1=""):
        got.append(url)
        with zipfile.ZipFile(dest, "w") as z:
            if "ServerFiles" in url:
                z.writestr("ServerFiles-0.3.0/forge-1.20.1-47.2.0-installer.jar", b"x")
                z.writestr("ServerFiles-0.3.0/mods/a.jar", b"x")
            else:
                z.writestr("manifest.json", json.dumps({"minecraft": {"version": "1.20.1", "modLoaders": [
                    {"id": "forge-47.2.0", "primary": True}]}, "name": "ATM9", "version": "0.3.0", "files": []}))

    v = M.curseforge_versions(715572, "k")[0]
    pack = M.load_curseforge(v, tmp_path, "k", dl=dl)
    assert pack.kind == "serverpack" and pack.server == "forge" and got[0].endswith("ServerFiles-0.3.0.zip")
    v.server_pack_id = 0                                    # no server pack: the normal modpack zip
    pack = M.load_curseforge(v, tmp_path / "b", "k", dl=dl)
    assert pack.kind == "curseforge" and got[-1].endswith("ATM9-0.3.0.zip")


def test_curseforge_blocked_pack_points_to_website(tmp_path):
    v = M.curseforge_versions(925200, "k", "https://www.curseforge.com/minecraft/modpacks/cozy-fabric")[0]
    with pytest.raises(M.PackError, match="cozy-fabric/files/6001"):
        M.load_curseforge(v, tmp_path, "k", dl=lambda *a, **k: None)


def test_parallel_download_and_cache(tmp_path):
    import hashlib
    import threading
    data = {f"mods/m{i}.jar": f"mod {i}".encode() for i in range(30)}
    files = [M.PackFile(p, [f"https://x/{p}"], sha1=hashlib.sha1(b).hexdigest()) for p, b in data.items()]
    active, peak, calls = [0], [0], []
    lock = threading.Lock()

    def dl(url, dest, sha1="", sha512=""):
        import time
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            calls.append(url)
        time.sleep(0.02)
        dest.write_bytes(data[url.split("/", 3)[3]])
        with lock:
            active[0] -= 1

    a = tmp_path / "a"
    st = M._download_all(files, a, dl, lambda m: None, lambda f: None)
    assert st == {"done": 30, "reused": 0} and peak[0] > 1 and len(calls) == 30
    assert (a / "mods" / "m7.jar").read_bytes() == b"mod 7"
    # a second server (or a reinstall) takes everything from the cache: no downloads at all
    st = M._download_all(files, tmp_path / "b", dl, lambda m: None, lambda f: None)
    assert st["reused"] == 30 and len(calls) == 30
    # a wrong file in the folder is not "reused"
    (tmp_path / "b" / "mods" / "m3.jar").write_bytes(b"broken")
    calls.clear()
    import shutil
    shutil.rmtree(tmp_path / "_filecache")
    M._download_all(files, tmp_path / "b", dl, lambda m: None, lambda f: None)
    assert calls == ["https://x/mods/m3.jar"]
