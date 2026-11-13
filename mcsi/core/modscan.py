"""Find client-only mods in a server's ``mods`` folder, without breaking mods that need them.

A mod is a *candidate* for removal when
  * its own metadata says so (Fabric/Quilt ``"environment": "client"``),
  * the modpack marked it client-only (Modrinth ``env.server = unsupported``, CurseForge "Client" tag),
  * its id is on a short list of well-known client-only Forge/NeoForge mods (shaders, renderers, HUDs), or
  * the server's own crash log blames it (``invalid dist DEDICATED_SERVER``, "Suspected Mod", ...).

A candidate is **kept** when any mod that stays on the server lists it as a required dependency on the
server side (Fabric ``depends``; Forge/NeoForge ``[[dependencies]]`` that are mandatory / ``type="required"``
and not ``side="CLIENT"``), so a "client-only" library/API that a server mod needs is never taken away.
Ids provided by jars nested inside other jars (Fabric ``jars``, Forge Jar-in-Jar) count as present.

Removed mods are moved to ``mods_disabled/`` (never deleted), so they can be put back by hand.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from ..i18n import _

DISABLED = "mods_disabled"

# Forge / NeoForge mods that only change how the game looks or feels on the client. Fabric mods don't need a
# list: they say so themselves. Only clear cases go here; anything else is caught from the crash log.
KNOWN_CLIENT = {
    "oculus", "iris", "embeddium", "rubidium", "sodium", "sodium_extra", "sodiumextra", "magnesium_extras",
    "reeses_sodium_options", "sodiumoptionsapi", "sodiumdynamiclights", "embeddium_extra", "embeddiumplus",
    "entityculling", "entity_texture_features", "entity_model_features", "notenoughanimations", "betterf3",
    "fpsreducer", "dynamiclights", "lambdynlights", "ryoamiclights", "skinlayers3d", "legendarytooltips",
    "itemborders", "equipmentcompare", "mousetweaks", "controlling", "searchables", "ambientsounds",
    "soundphysics", "sound_physics_remastered", "presencefootsteps", "fancymenu", "drippyloadingscreen",
    "konkrete", "blur", "catalogue", "enhancedvisuals", "firstperson", "firstpersonmod", "cullleaves",
    "cull_leaves", "chat_heads", "chatheads", "torohealth", "neat", "immediatelyfast", "betterfpsdist",
    "cherishedworlds", "eatinganimation", "visuality", "particlerain", "fallingleaves", "loadingscreens",
    "smoothboot", "rrls", "watermedia_client", "xaerobetterpvp", "inventoryhud", "betterthirdperson",
    "shouldersurfing", "camerapture_client", "zume", "itemphysiclite", "screenshot_viewer", "blockui",
    "hide_key_binding", "citresewn", "jecharacters", "imblocker", "chunksfadein", "smoothscroll",
    "fastscrolling", "movesubtitles", "armorchroma", "badoptimizations",
}
# Not client-only, but worth telling the owner about: they change who can reach the server.
NOTES = {
    "e4mc_minecraft": "e4mc", "e4mc": "e4mc",
}
IGNORED_DEPS = {"minecraft", "java", "fabricloader", "fabric-loader", "quilt_loader", "forge", "neoforge",
                "fml", "javafml", "mixinextras_neoforge"}


@dataclass
class ModInfo:
    file: str                                  # file name in mods/
    ids: list = field(default_factory=list)    # mod ids in this jar (first = main)
    provides: set = field(default_factory=set)  # ids of nested jars / "provides"
    name: str = ""
    env: str = ""                              # "client" | "server" | "" (both / unknown)
    deps: list = field(default_factory=list)   # required server-side dependency ids
    loader: str = ""

    @property
    def id(self) -> str:
        return self.ids[0] if self.ids else Path(self.file).stem

    @property
    def label(self) -> str:
        return f"{self.name or self.id} ({self.file})"


# ------------------------------------------------------------------ reading metadata
def _toml(text: str) -> dict:
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(text)
    except ImportError:
        pass
    except Exception:  # noqa: BLE001  broken TOML in a mod is common enough; use the simple reader
        pass
    return _toml_simple(text)


def _strip_comment(s: str) -> str:
    q = ""
    for i, c in enumerate(s):
        if q:
            if c == q:
                q = ""
        elif c in "\"'":
            q = c
        elif c == "#":
            return s[:i]
    return s


def _toml_simple(text: str) -> dict:
    """Just enough TOML for mods.toml: [[mods]] / [[dependencies.x]] tables and key = "value" pairs."""
    text = re.sub(r'("""|\'\'\').*?\1', '""', text, flags=re.S)      # drop multi-line descriptions
    out: dict = {}
    cur: dict = out
    for raw in text.splitlines():
        ln = _strip_comment(raw).strip()
        if not ln:
            continue
        m = re.fullmatch(r"\[\[\s*([\w.\-\"]+)\s*\]\]", ln)
        if m:
            parts = [p.strip('"') for p in m.group(1).split(".")]
            node = out
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            cur = {}
            node.setdefault(parts[-1], []).append(cur)
            continue
        m = re.fullmatch(r"\[\s*([\w.\-\"]+)\s*\]", ln)
        if m:
            node = out
            for p in [p.strip('"') for p in m.group(1).split(".")]:
                node = node.setdefault(p, {})
            cur = node
            continue
        m = re.fullmatch(r"([\w\-]+)\s*=\s*(.+)", ln)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v[:1] in "\"'":
            q = v[0]
            v = v[1:v.find(q, 1)] if v.find(q, 1) > 0 else v[1:]
        elif v in ("true", "false"):
            v = v == "true"
        cur[k] = v
    return out


def _fabric(meta: dict) -> tuple[list, str, list, set, str]:
    ids = [meta["id"]] if meta.get("id") else []
    env = str(meta.get("environment") or "*").lower()
    env = "client" if env == "client" else "server" if env == "server" else ""
    deps = [d for d in (meta.get("depends") or {}) if isinstance(d, str)]
    prov = set(meta.get("provides") or [])
    return ids, env, deps, prov, meta.get("name", "")


def _quilt(meta: dict) -> tuple[list, str, list, set, str]:
    ql = meta.get("quilt_loader") or {}
    ids = [ql["id"]] if ql.get("id") else []
    env = str((meta.get("minecraft") or {}).get("environment") or "*").lower()
    env = "client" if env in ("client", "client_only") else "server" if env == "dedicated_server" else ""
    deps = []
    for d in ql.get("depends") or []:
        if isinstance(d, str):
            deps.append(d.split(":")[-1])
        elif isinstance(d, dict) and not d.get("optional") and d.get("id"):
            deps.append(str(d["id"]).split(":")[-1])
    prov = {(p if isinstance(p, str) else p.get("id", "")).split(":")[-1] for p in ql.get("provides") or []}
    return ids, env, deps, prov, (ql.get("metadata") or {}).get("name", "")


def _forge(meta: dict) -> tuple[list, str, list, set, str]:
    mods = meta.get("mods") or []
    ids = [m.get("modId") for m in mods if m.get("modId")]
    deps = []
    for owner, lst in (meta.get("dependencies") or {}).items():
        if not isinstance(lst, list):
            continue
        for d in lst:
            if not isinstance(d, dict) or not d.get("modId"):
                continue
            side = str(d.get("side") or "BOTH").upper()
            if "type" in d:
                required = str(d["type"]).lower() == "required"
            else:
                required = d.get("mandatory", True) not in (False, "false")
            if required and side != "CLIENT":
                deps.append(d["modId"])
    name = mods[0].get("displayName", "") if mods else ""
    return ids, "", deps, set(), name


def _read_zip(z: zipfile.ZipFile, depth: int = 0) -> Optional[tuple]:
    names = set(z.namelist())
    res = None
    try:
        if "fabric.mod.json" in names:
            res = _fabric(json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)) + ("fabric",)
        elif "quilt.mod.json" in names:
            res = _quilt(json.loads(z.read("quilt.mod.json").decode("utf-8", "replace"), strict=False)) + ("quilt",)
        else:
            for t, lo in (("META-INF/neoforge.mods.toml", "neoforge"), ("META-INF/mods.toml", "forge")):
                if t in names:
                    res = _forge(_toml(z.read(t).decode("utf-8", "replace"))) + (lo,)
                    break
    except (ValueError, KeyError, AttributeError, TypeError):
        res = None
    if res is None:
        return None
    ids, env, deps, prov, name, loader = res
    prov = set(prov)
    if depth < 2:                               # Jar-in-Jar: libraries shipped inside this mod
        for n in names:
            if n.endswith(".jar") and (n.startswith("META-INF/jars/") or n.startswith("META-INF/jarjar/")):
                try:
                    with zipfile.ZipFile(io.BytesIO(z.read(n))) as inner:
                        r = _read_zip(inner, depth + 1)
                except (zipfile.BadZipFile, OSError, KeyError):
                    r = None
                if r:
                    prov |= set(r[0]) | set(r[3])
    return ids, env, deps, prov, name, loader


def read_mod(path: Path) -> Optional[ModInfo]:
    try:
        with zipfile.ZipFile(path) as z:
            r = _read_zip(z)
    except (zipfile.BadZipFile, OSError):
        return ModInfo(path.name)              # unreadable: only the modpack's hint can say anything
    if not r:
        return ModInfo(path.name)
    ids, env, deps, prov, name, loader = r
    return ModInfo(path.name, ids, prov, name, env, deps, loader)


def scan(mods_dir: Path) -> list[ModInfo]:
    if not mods_dir.is_dir():
        return []
    out = []
    for p in sorted(mods_dir.glob("*.jar")):
        m = read_mod(p)
        if m:
            out.append(m)
    return out


# ------------------------------------------------------------------ deciding
@dataclass
class Decision:
    remove: list = field(default_factory=list)   # (ModInfo, reason)
    keep: list = field(default_factory=list)     # (ModInfo, reason, needed_by label)


def decide(mods: list[ModInfo], hints: Optional[dict] = None, blame: Iterable[str] = ()) -> Decision:
    """hints: file name -> reason (from the modpack); blame: mod ids or file names the crash log points at."""
    hints = hints or {}
    blame = {b.lower() for b in blame}
    cand: dict[str, tuple[ModInfo, str]] = {}
    for m in mods:
        reason = ""
        if m.env == "client":
            reason = _("marked client-only by the mod itself")
        elif m.file in hints:
            reason = hints[m.file]
        elif m.loader in ("forge", "neoforge") and any(i.lower() in KNOWN_CLIENT for i in m.ids):
            reason = _("known client-only mod")
        if blame & ({i.lower() for i in m.ids} | {m.file.lower()}):
            reason = _("the server crashed in this mod (client-only code)")
        if reason:
            cand[m.file] = (m, reason)

    by_id: dict[str, ModInfo] = {}
    for m in mods:
        for i in list(m.ids) + list(m.provides):
            by_id.setdefault(i.lower(), m)

    keep: dict[str, tuple[ModInfo, str, str]] = {}
    changed = True
    while changed:                          # keep anything a staying mod needs, transitively
        changed = False
        for m in mods:
            if m.file in cand and m.file not in keep:
                continue                    # being removed: its needs don't count
            for d in m.deps:
                dl = d.lower()
                if dl in IGNORED_DEPS:
                    continue
                prov = by_id.get(dl)
                if prov is None or prov is m or prov.file not in cand or prov.file in keep:
                    continue
                keep[prov.file] = (prov, cand[prov.file][1], m.name or m.id)
                changed = True
    dec = Decision()
    for f, (m, why) in cand.items():
        if f in keep:
            dec.keep.append(keep[f])
        else:
            dec.remove.append((m, why))
    return dec


def apply(folder: Path, dec: Decision, log: Callable[[str], None] = lambda m: None) -> list[str]:
    """Move the removed mods to mods_disabled/ and return summary lines."""
    lines: list[str] = []
    if not dec.remove and not dec.keep:
        return lines
    dis = folder / DISABLED
    moved = []
    for m, why in dec.remove:
        src = folder / "mods" / m.file
        if not src.is_file():
            continue
        dis.mkdir(exist_ok=True)
        dst = dis / m.file
        if dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))
        moved.append(m)
        log(_("  − {0}: {1} → mods_disabled").format(m.label, why))
    for m, why, needed_by in dec.keep:
        log(_("  = kept {0}: {1}, but {2} needs it").format(m.label, why, needed_by))
    if moved:
        (dis / "README.txt").write_text(_(
            "These mods only work in the game client, so the installer moved them out of the server's mods "
            "folder. Nothing was deleted: move a file back into mods/ if the server needs it after all.")
            + "\n\n" + "\n".join(f"{m.file}  ({why})" for m, why in dec.remove) + "\n", encoding="utf-8")
        lines.append(_("Moved {0} client-only mods to mods_disabled: {1}").format(
            len(moved), ", ".join(m.name or m.id for m in moved[:6]) + (" …" if len(moved) > 6 else "")))
    if dec.keep:
        lines.append(_("Kept {0} client-side mods that server mods need: {1}").format(
            len(dec.keep), ", ".join(m.name or m.id for m, _w, _n in dec.keep[:6])))
    return lines


def cleanup(folder: Path, hints: Optional[dict] = None, log: Callable[[str], None] = lambda m: None) -> list[str]:
    mods = scan(folder / "mods")
    if not mods:
        return []
    log(_("Checking {0} mods for client-only ones...").format(len(mods)))
    lines = apply(folder, decide(mods, hints), log)
    if any(i.lower() in NOTES for m in mods for i in m.ids):
        note = _("ℹ The e4mc mod is in this pack: it gives the server a public *.e4mc.link address, so anyone "
                 "with that address can join without port forwarding. Remove it from mods/ if you don't want that.")
        log(note)
        lines.append(note)
    return lines


# ------------------------------------------------------------------ reading a failed start
CAUSE_RE = re.compile(
    r"Caused by:|Exception|Error:|requires .*(missing|or above|version)|Missing or unsupported|"
    r"invalid dist|Mixin .*(fail|error)|Suspected Mods?:|Mod loading issue|Failed to create mod instance|"
    r"Incompatible mod set|which is missing|environment type SERVER|could not find|Crash report saved|"
    r"has failed to load correctly",
    re.I)
NOISE_RE = re.compile(r"^\s*at |^\s*\.\.\. \d+ more|^\s*\|", re.I)


CLIENT_EXC_RE = re.compile(
    r"^\s*(Caused by: )?[\w.$]*(Exception|Error)[\w.$]*: .*(invalid dist DEDICATED_SERVER|environment type SERVER|"
    r"net[/.]minecraft[/.]client[/.])")
COLOR_RE = re.compile(r"§[0-9a-fk-or]", re.I)
WARN_ONLY_RE = re.compile(r"\[mixin/?\]: Error loading class|RuntimeDistCleaner|Skipping extension class")


def blame(lines: list[str], mods: list[ModInfo]) -> list[str]:
    """Mod ids the log says crashed the server by loading client-only code.

    Many big packs print harmless "Attempted to load class net/minecraft/client/... for invalid dist" lines
    from mixin/RuntimeDistCleaner while starting fine, so only a real exception (a line that *is* the
    exception, or its "Caused by:") counts, and the culprit is taken from that exception's own stack trace
    or the crash report's "Suspected Mods" / "Mod loading issue" lines."""
    lines = [COLOR_RE.sub("", ln) for ln in lines]
    known = {i.lower() for m in mods for i in m.ids} | {m.file.lower() for m in mods}
    found: list[str] = []

    def add(tok: str) -> None:
        t = tok.strip().lower()
        if t in known and t not in IGNORED_DEPS and t not in found:
            found.append(t)

    hits = [i for i, ln in enumerate(lines) if CLIENT_EXC_RE.search(ln) and not WARN_ONLY_RE.search(ln)]
    if not hits:
        return []
    for i in hits:
        # Forge's list: "Hide Key Binding (hide_key_binding) has failed to load correctly" + the exception
        for back in lines[max(0, i - 2):i]:
            m = re.search(r"\(([a-z0-9_\-]+)\) has failed to load correctly", back)
            if m:
                add(m.group(1))
        # the nearest "which mod" line above this exception (mod construction / crash report section)
        for back in reversed(lines[max(0, i - 45):i]):
            m = (re.search(r"Failed to create mod instance\. ModID: ([\w\-]+)", back) or
                 re.search(r"Mod loading issue for: ([\w\-]+)", back) or
                 re.search(r"Mod File: .*?[/\\]([^/\\]+\.jar)", back))
            if m:
                add(m.group(1))
                break
        for ln in lines[i + 1:i + 60]:                # frames right under the exception
            m = re.search(r"TRANSFORMER/([a-z0-9_\-]+)@", ln)
            if m and m.group(1).lower() not in IGNORED_DEPS and m.group(1).lower() in known:
                add(m.group(1))
                break
            m = re.search(r"~\[([^\]\[%/\\]+\.jar)(%23\d+)?", ln)    # Forge 1.20.1: ~[ModName-1.0.jar%23272!/:1.0]
            if m and m.group(1).lower() in known:
                add(m.group(1))
                break
            if not re.match(r"\s*(at |\.\.\. \d+ more|Caused by:)", ln):
                break
    if not found:                                     # crash report summary, only when nothing better
        for m in re.finditer(r"Suspected Mods?: ([^\n]+)", "\n".join(lines)):
            for tok in re.findall(r"\(([a-z0-9_\-]+)\)", m.group(1)):
                add(tok)
    return found


def explain(lines: list[str], limit: int = 8) -> str:
    """The lines that say why the server stopped, instead of the bottom of a stack trace."""
    out: list[str] = []
    for ln in lines:
        ln = COLOR_RE.sub("", ln)
        s = ln.strip()
        if not s or NOISE_RE.search(ln) or not CAUSE_RE.search(s):
            continue
        s = re.sub(r"^\[[^\]]*\]\s*(\[[^\]]*\]\s*)*", "", s)[:300]     # drop "[18:12:01] [main/ERROR]" prefixes
        if s not in out:
            out.append(s)
    if not out:
        return "\n".join(lines[-8:])
    return "\n".join(out[-limit:] if len(out) > limit else out)


def missing_deps(lines: list[str]) -> list[str]:
    """'Mod X requires Y' style lines (a mod is missing; maybe one from MANUAL_DOWNLOADS.txt)."""
    pats = (r"requires .* which is missing", r"Missing or unsupported mandatory dependencies",
            r"Mod ID: '[^']+', Requested by: '[^']+'", r"requires .* or above", r"Mod .+ requires .+")
    out = []
    for ln in lines:
        if any(re.search(p, ln) for p in pats):
            s = re.sub(r"^\[[^\]]*\]\s*(\[[^\]]*\]\s*)*", "", ln.strip())[:240]
            if s not in out:
                out.append(s)
    return out[:8]
