"""Client-only mod detection: never take away a mod that a server mod needs."""

import json
import time
import zipfile

import pytest

from mcsi.core import modscan as S


def fabric_jar(path, mid, env="*", depends=(), nested=()):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("fabric.mod.json", json.dumps({"schemaVersion": 1, "id": mid, "name": mid.title(),
                                                  "environment": env, "depends": {d: "*" for d in depends},
                                                  "jars": [{"file": f"META-INF/jars/{n}.jar"} for n in nested]}))
        for n in nested:
            import io
            b = io.BytesIO()
            with zipfile.ZipFile(b, "w") as inner:
                inner.writestr("fabric.mod.json", json.dumps({"schemaVersion": 1, "id": n}))
            z.writestr(f"META-INF/jars/{n}.jar", b.getvalue())


def forge_jar(path, mid, deps=(), neo=True, legacy=False):
    """deps: (modId, side, required)"""
    lines = ['modLoader="javafml"', 'loaderVersion="[1,)"', "", "[[mods]]", f'modId="{mid}"',
             f'displayName="{mid.title()}"',
             'description=\'\'\'multi\nline # not a comment\n\'\'\'', ""]
    for d, side, req in deps:
        lines += [f"[[dependencies.{mid}]]", f'modId="{d}"']
        lines += [f"mandatory={'true' if req else 'false'}"] if legacy else [f'type="{"required" if req else "optional"}"']
        lines += [f'side="{side}"  # comment', ""]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/neoforge.mods.toml" if neo else "META-INF/mods.toml", "\n".join(lines))


@pytest.fixture
def server(tmp_path):
    (tmp_path / "mods").mkdir()
    return tmp_path


def test_reads_metadata(server):
    m = server / "mods"
    fabric_jar(m / "a.jar", "alpha", "client", ["fabricloader", "beta"], nested=["libx"])
    forge_jar(m / "b.jar", "bravo", [("neoforge", "BOTH", True), ("lib", "SERVER", True), ("jei", "BOTH", False),
                                     ("cl", "CLIENT", True)])
    forge_jar(m / "c.jar", "charlie", [("lib", "BOTH", True)], neo=False, legacy=True)
    mods = {x.file: x for x in S.scan(m)}
    a, b, c = mods["a.jar"], mods["b.jar"], mods["c.jar"]
    assert (a.id, a.env, a.loader, a.deps, a.provides) == ("alpha", "client", "fabric", ["fabricloader", "beta"], {"libx"})
    assert (b.id, b.loader, b.deps, b.name) == ("bravo", "neoforge", ["neoforge", "lib"], "Bravo")
    assert (c.loader, c.deps) == ("forge", ["lib"])


def test_simple_toml_reader_matches():
    text = 'a="x # y"\n[[mods]]\nmodId="m" # c\n[[dependencies.m]]\nmodId="d"\nmandatory=true\nside="BOTH"\n'
    d = S._toml_simple(text)
    assert d["a"] == "x # y" and d["mods"][0]["modId"] == "m"
    assert d["dependencies"]["m"][0] == {"modId": "d", "mandatory": True, "side": "BOTH"}


def test_removes_client_only_but_keeps_what_server_mods_need(server):
    m = server / "mods"
    forge_jar(m / "oculus.jar", "oculus")                                    # known client-only, unused → out
    forge_jar(m / "controlling.jar", "controlling")                          # known client-only …
    forge_jar(m / "searchables.jar", "searchables")                          # … and its library
    forge_jar(m / "cfg.jar", "clothy")                                       # pack said client-only, but needed:
    forge_jar(m / "machines.jar", "machines", [("clothy", "BOTH", True), ("oculus", "CLIENT", True)])
    forge_jar(m / "plain.jar", "plain")
    lines = S.cleanup(server, {"cfg.jar": "marked client-only on CurseForge"})
    left = sorted(p.name for p in m.iterdir())
    assert left == ["cfg.jar", "machines.jar", "plain.jar"]
    assert sorted(p.name for p in (server / S.DISABLED).glob("*.jar")) == ["controlling.jar", "oculus.jar",
                                                                          "searchables.jar"]
    assert "Kept 1" in "\n".join(lines) and "Moved 3" in "\n".join(lines)
    assert (server / S.DISABLED / "README.txt").exists()


def test_needed_transitively_and_via_nested_jar(server):
    m = server / "mods"
    fabric_jar(m / "ui.jar", "uilib", "client")                              # client lib …
    fabric_jar(m / "bridge.jar", "bridge", "client", ["uilib"])             # … needed by a client mod …
    fabric_jar(m / "core.jar", "core", "*", ["bridge"])                     # … that a server mod needs
    fabric_jar(m / "hud.jar", "hud", "client", ["shaded"])
    fabric_jar(m / "pack.jar", "packmod", "*", nested=["shaded"])            # provides "shaded" itself
    dec = S.decide(S.scan(m))
    assert sorted(x.file for x, _w in dec.remove) == ["hud.jar"]
    assert sorted(x[0].file for x in dec.keep) == ["bridge.jar", "ui.jar"]


def test_unreadable_jar_uses_pack_hint(server):
    (server / "mods" / "iris.jar").write_text("not a zip")
    assert S.cleanup(server, {"iris.jar": "marked client-only in the modpack"})
    assert (server / S.DISABLED / "iris.jar").exists()


NEO_CRASH = """[18:12:01] [main/ERROR] [ne.ne.fm.lo.ModLoader/LOADING]: Failed to create mod instance. ModID: oculus
java.lang.RuntimeException: Attempted to load class net/minecraft/client/renderer/ShaderInstance for invalid dist DEDICATED_SERVER
\tat TRANSFORMER/oculus@1.7.0/net.irisshaders.iris.Iris.<init>(Iris.java:10)
\tat MC-BOOTSTRAP/cpw.mods.modlauncher@11.0.5/cpw.mods.modlauncher.Launcher.run(Launcher.java:103)
Caused by: java.lang.RuntimeException: Attempted to load class net/minecraft/client/Minecraft for invalid dist DEDICATED_SERVER
\tat MC-BOOTSTRAP/cpw.mods.bootstraplauncher@2.0.2/cpw.mods.bootstraplauncher.BootstrapLauncher.main(BootstrapLauncher.java:69)""".splitlines()


def test_blame_and_explain(server):
    forge_jar(server / "mods" / "oculus.jar", "oculus")
    forge_jar(server / "mods" / "create.jar", "create")
    mods = S.scan(server / "mods")
    assert S.blame(NEO_CRASH, mods) == ["oculus"]
    assert S.blame(["java.lang.NullPointerException", "\tat TRANSFORMER/create@6/x"], mods) == []   # not client code
    why = S.explain(NEO_CRASH)
    assert "invalid dist DEDICATED_SERVER" in why and "at TRANSFORMER" not in why and "[main/ERROR]" not in why
    miss = S.missing_deps(["Mod 'Create' (create) 6.0 requires any version of mod flywheel, which is missing!"])
    assert miss and "flywheel" in miss[0]


def test_installer_retries_without_blamed_mod(server, monkeypatch):
    import mcsi.core.installer as I
    forge_jar(server / "mods" / "oculus.jar", "oculus")
    forge_jar(server / "mods" / "create.jar", "create")
    inst = I.Installer.__new__(I.Installer)
    inst.folder, inst.summary, inst.log = server, [], lambda m: None
    runs = []

    def first_run(launch, args):
        runs.append(1)
        if (server / "mods" / "oculus.jar").exists():
            raise I.StartFailed(NEO_CRASH, time.time())

    inst.first_run = first_run
    inst.first_run_fixing(None, [])
    assert len(runs) == 2 and (server / S.DISABLED / "oculus.jar").exists()
    assert any("oculus" in s.lower() for s in inst.summary)


def test_installer_explains_missing_mod(server):
    import mcsi.core.installer as I
    from mcsi.core.net import NetError
    (server / "MANUAL_DOWNLOADS.txt").write_text("x")
    inst = I.Installer.__new__(I.Installer)
    inst.folder, inst.summary, inst.log = server, [], lambda m: None

    def first_run(launch, args):
        raise I.StartFailed(["Mod 'Create' (create) 6.0 requires any version of mod flywheel, which is missing!",
                             "\tat foo.bar(Baz.java:1)"], time.time())

    inst.first_run = first_run
    with pytest.raises(NetError, match="MANUAL_DOWNLOADS"):
        inst.first_run_fixing(None, [])


HARMLESS = """[19:47:30.916] [main/ERROR] [common.asm.RuntimeDistCleaner/DISTXFORM]: Attempted to load class net/minecraft/client/multiplayer/ClientLevel for invalid dist DEDICATED_SERVER
[19:47:30.918] [main/WARN] [mixin/]: Error loading class: net/minecraft/client/multiplayer/ClientLevel (java.lang.RuntimeException: Attempted to load class net/minecraft/client/multiplayer/ClientLevel for invalid dist DEDICATED_SERVER)
[19:47:39] [main/INFO] [or.gr.gm.in.ModExtensionLoader/]: Skipping extension class org.groovymc.cgl.api.extension.client.MinecraftExtensions: it requires dist CLIENT, but we're running on DEDICATED_SERVER
java.lang.IllegalStateException: Expected BEGIN_OBJECT but was NUMBER
\tat TRANSFORMER/create@6.0.10/com.simibubi.create.Foo.bar(Foo.java:1)""".splitlines()


def test_harmless_client_class_warnings_blame_nobody(server):
    """Big packs (Create+ 1.21.1) print these while starting fine: they must not get a mod removed."""
    forge_jar(server / "mods" / "create.jar", "create")
    assert S.blame(HARMLESS, S.scan(server / "mods")) == []


def test_e4mc_is_kept_but_explained(server):
    forge_jar(server / "mods" / "e4mc-neoforge-6.1.2.jar", "e4mc_minecraft")
    lines = S.cleanup(server)
    assert (server / "mods" / "e4mc-neoforge-6.1.2.jar").exists() and "e4mc.link" in "\n".join(lines)


def test_forge_1201_loading_errors_from_a_real_log(server):
    """Forge 1.20.1 + Connector pack: four client-only mods listed in LoadingFailedException (with § colours)
    and one crashing during construction (Caused by ... invalid dist)."""
    from pathlib import Path
    lines = (Path(__file__).parent / "data_forge_client_crash.txt").read_text(encoding="utf-8").splitlines()
    for mid in ("hide_key_binding", "citresewn", "jecharacters", "imblocker", "kubejs", "quark"):
        forge_jar(server / "mods" / f"{mid}.jar", mid)
    assert sorted(S.blame(lines, S.scan(server / "mods"))) == ["citresewn", "hide_key_binding", "imblocker",
                                                              "jecharacters"]
    why = S.explain(lines)
    assert "Hide Key Binding (hide_key_binding) has failed to load correctly" in why
    assert "§" not in why


def test_installer_stops_waiting_after_fatal_line():
    import mcsi.core.installer as I
    assert I.FATAL_RE.search("[19:54:53] [main/ERROR] [minecraft/Main]: Failed to start the minecraft server")
    assert I.NOISY_RE.match("    Slim  ebp$a.class") and not I.NOISY_RE.match("Downloading forge")


def test_replace_waits_for_a_locked_target(tmp_path, monkeypatch):
    """Windows: os.replace fails while antivirus / an old server has the target open."""
    import os
    from mcsi.core import net
    from mcsi.core.net import NetError
    part, dest = tmp_path / "a.jar.part", tmp_path / "a.jar"
    part.write_bytes(b"new")
    real, calls = os.replace, []

    def flaky(a, b):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError(5, "Access is denied")
        real(a, b)

    monkeypatch.setattr(net.os, "replace", flaky)
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    net._replace(part, dest)
    assert dest.read_bytes() == b"new" and len(calls) == 3

    part.write_bytes(b"other")
    monkeypatch.setattr(net.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(5, "denied")))
    with pytest.raises(NetError, match="another program"):
        net._replace(part, dest)
    part.write_bytes(b"new")                                  # same size as the locked file: keep it
    net._replace(part, dest)
    assert not part.exists()


def test_leftover_server_pid_is_only_killed_if_java(tmp_path, monkeypatch):
    import mcsi.core.installer as I
    monkeypatch.setattr(I, "_pid_file", lambda: tmp_path / "pids.json")
    I._remember_pid(tmp_path / "srv", 999999)
    killed = []
    monkeypatch.setattr(I, "_pid_is_java", lambda pid: False)
    monkeypatch.setattr(I.os, "kill", lambda pid, sig: killed.append(pid))
    I.stop_leftover_servers(tmp_path / "srv")
    assert not killed and I._load_pids() == {}
