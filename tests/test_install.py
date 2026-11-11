"""Install every server type end-to-end with fake downloads and a fake Java."""

import os

import pytest

from mcsi.core import installer as I
from mcsi.core import schema

# The fake Java is a Python script with a shebang, which Windows cannot execute directly.
pytestmark = pytest.mark.skipif(os.name == "nt", reason="fake java needs a POSIX shell")

CASES = {"vanilla": "26.3", "paper": "26.3", "purpur": "26.3", "folia": "26.3", "spigot": "26.3",
         "bukkit": "1.21.11", "fabric": "26.3", "quilt": "1.21.11", "babric": "b1.7.3", "legacyfabric": "1.12.2",
         "forge": "1.20.1", "neoforge": "26.1.2", "mohist": "1.21.1", "youer": "1.21.1", "arclight": "1.21.1",
         "banner": "1.21.1"}


def make_plan(server, mc, folder, java, **values):
    vals = schema.defaults()
    vals.update(values)
    return I.Plan(server=server, mc=mc, build="", folder=str(folder), ram_gb=6, java=java, java_major=25,
                  values=vals, eula=True)


@pytest.mark.parametrize("server,mc", CASES.items())
def test_install(server, mc, tmp_path, fake_java, no_downloads, no_upnp):
    plan = make_plan(server, mc, tmp_path, fake_java, **{
        "rule:keep_inventory": True, "rule:doFireTick": False, "pvp": False,
        "motd": "Test server §aé", "manage:ops": "Steve, bad name!", "launch:auto_restart": True})
    logs, stages = [], []
    inst = I.Installer(plan, logs.append, lambda v: None, lambda i, t: stages.append(i), lambda: False)
    launch = inst.execute()
    props = (tmp_path / "server.properties").read_text()
    assert "motd=Test server" in props and "pvp=false" in props
    assert "eula=true" in (tmp_path / "eula.txt").read_text()
    assert (tmp_path / "backup.bat").exists() and (tmp_path / "open_firewall.bat").exists()
    assert ":loop" in (tmp_path / "start.bat").read_text()
    assert stages == [0, 1, 3, 4, 5, 6, 7], logs[-15:]
    assert launch.kind in ("jar", "args")
    assert no_upnp == [[(25565, "TCP")]]
    assert inst.forward and inst.forward.ok


def test_upnp_and_first_run_can_be_skipped(tmp_path, fake_java, no_downloads, no_upnp):
    plan = make_plan("paper", "26.3", tmp_path, fake_java, **{"manage:upnp": False, "manage:first_run": False})
    stages = []
    I.Installer(plan, lambda s: None, lambda v: None, lambda i, t: stages.append(i), lambda: False).execute()
    assert stages == [0, 1, 3, 4, 7]
    assert no_upnp == []


def test_firewall_script_covers_extra_ports(tmp_path, fake_java, no_downloads, no_upnp):
    plan = make_plan("paper", "26.3", tmp_path, fake_java, **{"server-port": 25570})
    plan.addons = [{"kind": "plugin", "title": "Geyser", "filename": "geyser.jar", "url": "https://x/g.jar"}]
    I.Installer(plan, lambda s: None, lambda v: None, lambda i, t: None, lambda: False).execute()
    fw = (tmp_path / "open_firewall.bat").read_text()
    assert "localport=25570" in fw and "protocol=UDP localport=19132" in fw
    assert no_upnp == [[(25570, "TCP"), (19132, "UDP")]]


def test_addons_go_to_the_right_folders(tmp_path, fake_java, no_downloads, no_upnp):
    from mcsi.core import modrinth as M
    local = tmp_path / "my_local_mod.jar"
    local.write_text("local")
    adds = [a.to_dict() for a in M.resolve("jei", "JEI", "mod", "neoforge", "1.21.1", "", set())[0]]
    adds += [a.to_dict() for a in M.resolve("essentialsx", "EssentialsX", "plugin", "youer", "1.21.1", "", set())[0]]
    adds += [a.to_dict() for a in M.resolve("terralith", "Terralith", "datapack", "youer", "1.21.1", "", set())[0]]
    adds.append(M.Addon(kind="mod", title="my_local_mod", local_path=str(local), filename=local.name).to_dict())
    folder = tmp_path / "srv"
    plan = make_plan("youer", "1.21.1", folder, fake_java, **{"level-name": "myworld"})
    plan.addons = adds
    stages = []
    I.Installer(plan, lambda s: None, lambda v: None, lambda i, t: stages.append(i), lambda: False).execute()
    assert 2 in stages
    files = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    assert "mods/my_local_mod.jar" in files
    assert any(f.startswith("plugins/") for f in files)
    assert any(f.startswith("myworld/datapacks/") for f in files)
