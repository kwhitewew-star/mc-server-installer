"""First steps: start (mode), server type, version, location & performance."""

from __future__ import annotations
from ..i18n import _

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit, QListWidget,
                             QListWidgetItem, QScrollArea, QSlider, QVBoxLayout, QWidget)

from ..core import schema
from ..core.java import best_for, find_javas, install_jdk
from ..core.providers import PROVIDERS
from .state import State, default_folder, recommended_ram, run_async, total_ram_gb
from .widgets import (ACCENT, FlowLayout, DANGER, MUTED, OK, WARN, Button, Card, Glass, NoWheelCombo, NoWheelSpin,
                         Progress, Spinner, Toggle, label)
from ..core.versions import is_release, required_java


class Page(QWidget):
    changed = pyqtSignal()        # asks the window to re-evaluate the Next button

    title = ""
    subtitle = ""

    def __init__(self, st: State):
        super().__init__()
        self.st = st
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(34, 28, 34, 10)
        self.root.setSpacing(14)
        if self.title:
            self.root.addWidget(label(self.title, "h2"))
            sub = label(self.subtitle, "muted", True)
            self.root.addWidget(sub)

    def enter(self) -> None:
        pass

    def leave(self) -> None:
        pass

    def can_next(self) -> bool:
        return True

    def validate(self) -> str | None:
        return None


# ------------------------------------------------------------------ 1. Start
class WelcomePage(Page):
    mode_changed = pyqtSignal(str)

    def __init__(self, st):
        super().__init__(st)
        self.root.setContentsMargins(40, 40, 40, 10)
        self.root.addWidget(label(_("Minecraft Server Installer"), "h1"))
        self.root.addWidget(label(_("Pick a server type and version, adjust settings step by step, and everything from install to first launch is done for you."),
                                  "muted", True))
        self.root.addSpacing(18)
        self.root.addWidget(label(_("Choose a setup mode"), "h3"))
        grid = QHBoxLayout()
        grid.setSpacing(14)
        self.group = QButtonGroup(self)
        n_b = sum(1 for s in schema.ALL if s.level == "b")
        modes = [("quick", _("Quick"), "⚡", ACCENT,
                  _("Pick the type, version and folder; everything else uses recommended values."), _("1 min")),
                 ("standard", _("Standard"), "◆", "#60a5fa",
                  _("Adjust the {0} most common settings step by step. (Show all is always available)").format(n_b), _("Recommended")),
                 ("detailed", _("Detailed"), "✦", "#c084fc",
                  _("Configure all {0} options: the full server.properties, game rules and launch options.").format(schema.count()), _("Expert"))]
        self.cards = {}
        for key, title, icon, color, desc, badge in modes:
            c = Card(title, desc, color, badge, icon, height=150)
            self.group.addButton(c)
            c.clicked.connect(lambda _=False, k=key: self._pick(k))
            grid.addWidget(c)
            self.cards[key] = c
        self.root.addLayout(grid)
        self.root.addSpacing(10)
        chips = FlowLayout()
        for t in (_("{0} server types").format(len(PROVIDERS)), _("{0} settings").format(schema.count()), _("Automatic Java install"),
                  _("Verified first run"), _("Backups · firewall · shortcut")):
            chips.addWidget(label(t, "chip"))
        self.root.addLayout(chips)
        self.root.addStretch(1)

    def enter(self):
        self.cards[self.st.mode].setChecked(True)

    def _pick(self, k):
        self.st.mode = k
        self.mode_changed.emit(k)


# ------------------------------------------------------------------ 2. Server type
class ServerPage(Page):
    picked = pyqtSignal(str)
    title = _("Server type")
    subtitle = _("Plugins: Paper or Purpur. Mods: Fabric or NeoForge. Both: a hybrid like Youer or Arclight.")

    def __init__(self, st):
        super().__init__(st)
        self.group = QButtonGroup(self)
        self.cards = {}
        icons = {"vanilla": "V", "paper": "P", "purpur": "Pu", "folia": "Fo", "spigot": "S", "bukkit": "B",
                 "fabric": "F", "quilt": "Q", "babric": "β", "legacyfabric": "LF", "forge": "Fg", "neoforge": "N",
                 "mohist": "M", "youer": "Y", "arclight": "A", "banner": "Bn"}
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        box = QVBoxLayout(inner)
        box.setContentsMargins(0, 0, 8, 0)
        box.setSpacing(8)
        for title, kinds in ((_("Vanilla · plugin servers"), ("vanilla", "plugin")), (_("Modded servers"), ("mod",)),
                            (_("Hybrid servers · mods and plugins together"), ("hybrid",))):
            box.addWidget(label(title, "small"))
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            i = 0
            for p in PROVIDERS.values():
                if p.kind not in kinds:
                    continue
                c = Card(p.name, p.desc, p.accent, p.badge, icons.get(p.key, p.name[0]), height=112)
                self.group.addButton(c)
                c.clicked.connect(lambda _=False, k=p.key: self._pick(k))
                grid.addWidget(c, i // 3, i % 3)
                self.cards[p.key] = c
                i += 1
            for j in range(3):
                grid.setColumnStretch(j, 1)
            box.addLayout(grid)
            box.addSpacing(6)
        box.addStretch(1)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)

    def enter(self):
        if self.st.server in self.cards:
            self.cards[self.st.server].setChecked(True)

    def _pick(self, k):
        if k != self.st.server:
            self.st.server = k
            self.st.mc = ""
            self.st.build = ""
        self.changed.emit()
        self.picked.emit(k)

    def can_next(self):
        return self.st.server in PROVIDERS


# ------------------------------------------------------------------ 3. Version
class VersionPage(Page):
    title = _("Choose a version")
    subtitle = _("Versions are loaded live from each server's official API.")

    def __init__(self, st):
        super().__init__(st)
        body = QHBoxLayout()
        body.setSpacing(16)
        left = Glass()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 12)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Search versions  (e.g. 26.1, 1.20.1)"))
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search, 1)
        top.addWidget(label(_("Snapshots"), "small"))
        self.snap = Toggle(st.snapshots)
        self.snap.toggled.connect(self._snap)
        top.addWidget(self.snap)
        ll.addLayout(top)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._picked)
        ll.addWidget(self.list, 1)
        stat = QHBoxLayout()
        self.spin = Spinner()
        self.spin.hide()
        stat.addWidget(self.spin)
        self.status = label("", "small", True)
        stat.addWidget(self.status, 1)
        self.retry = Button(_("Retry"))
        self.retry.clicked.connect(self.reload)
        self.retry.hide()
        stat.addWidget(self.retry)
        ll.addLayout(stat)
        body.addWidget(left, 3)

        right = Glass()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 18, 20, 18)
        rl.setSpacing(10)
        self.sel_title = label("", "h2")
        rl.addWidget(self.sel_title)
        self.sel_desc = label("", "muted", True)
        rl.addWidget(self.sel_desc)
        rl.addSpacing(6)
        rl.addWidget(label(_("Build / loader version"), "h3"))
        bl = QHBoxLayout()
        self.builds = NoWheelCombo()
        self.builds.currentIndexChanged.connect(self._build_picked)
        bl.addWidget(self.builds, 1)
        self.bspin = Spinner()
        self.bspin.hide()
        bl.addWidget(self.bspin)
        rl.addLayout(bl)
        self.build_note = label("", "small", True)
        rl.addWidget(self.build_note)
        rl.addSpacing(6)
        self.java_lbl = label("", "", True)
        rl.addWidget(self.java_lbl)
        self.warn = label("", "small", True)
        rl.addWidget(self.warn)
        rl.addStretch(1)
        body.addWidget(right, 2)
        self.root.addLayout(body, 1)
        self._token = 0
        self._btoken = 0
        self._loaded_for = None
        self._versions: list[str] = []

    def enter(self):
        p = PROVIDERS[self.st.server]
        self.sel_desc.setText(p.desc)
        warn = []
        if p.needs_git:
            warn.append(_("• Git must be installed, and building takes 10-30 minutes."))
        if p.experimental:
            warn.append(_("• Experimental support. If it fails to install, choose another type."))
        if p.key == "babric":
            warn.append(_("• Babric is for Beta 1.7.3 only. For 1.3 – 1.13.2, choose Legacy Fabric."))
        if p.key == "legacyfabric":
            warn.append(_("• Old versions often need Java 8. Adding the Legacy Fabric API mod is recommended."))
        if p.kind == "hybrid":
            warn.append(_("• Hybrid servers can conflict with some mod/plugin combinations. The first run downloads extra files and takes longer."))
        if p.key == "arclight":
            warn.append(_("• Pick the loader you want (Forge / NeoForge / Fabric) in the build list."))
        if p.key == "folia":
            warn.append(_("• Most regular plugins do not work on Folia."))
        self.warn.setText("\n".join(warn))
        self.warn.setStyleSheet(f"color:{WARN}")
        key = (self.st.server, self.st.snapshots)
        if self._loaded_for != key:
            self.reload()
        self._update_title()

    def _snap(self, on):
        self.st.snapshots = on
        self.reload()

    def reload(self):
        self._token += 1
        tok = self._token
        server, snaps = self.st.server, self.st.snapshots
        self.list.clear()
        self.builds.clear()
        self.retry.hide()
        self.spin.start()
        self.status.setText(_("Loading {0} versions…").format(PROVIDERS[server].name))
        self.status.setStyleSheet("")

        def ok(vs):
            if tok != self._token:
                return
            self.spin.stop()
            self._loaded_for = (server, snaps)
            self._versions = vs
            self._fill(vs)
            self.status.setText(_("{0} versions · newest first").format(len(vs)))

        def err(msg):
            if tok != self._token:
                return
            self.spin.stop()
            self._loaded_for = None
            self.status.setText(_("Failed to load: {0}").format(msg))
            self.status.setStyleSheet(f"color:{DANGER}")
            self.retry.show()

        run_async(lambda sig: PROVIDERS[server].list_versions(snaps), ok, err)

    def _fill(self, vs):
        self.list.blockSignals(True)
        self.list.clear()
        first_release = next((v for v in vs if is_release(v)), None)
        for v in vs:
            tag = _("   ·  latest") if v == first_release else ("" if is_release(v) else _("   ·  pre-release"))
            it = QListWidgetItem(v + tag)
            it.setData(Qt.ItemDataRole.UserRole, v)
            self.list.addItem(it)
        self.list.blockSignals(False)
        target = self.st.mc if self.st.mc in vs else first_release or (vs[0] if vs else "")
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == target:
                self.list.setCurrentRow(i)
                self.list.scrollToItem(self.list.item(i))
                break
        self._filter(self.search.text())

    def _filter(self, text):
        t = text.strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def _picked(self, cur, prev):
        if not cur:
            return
        mc = cur.data(Qt.ItemDataRole.UserRole)
        if mc != self.st.mc:
            self.st.build = ""
        self.st.mc = mc
        if not self.st.folder_custom:
            self.st.folder = default_folder(self.st.server, mc)
        self._update_title()
        self._load_builds(mc)
        self.changed.emit()

    def _update_title(self):
        p = PROVIDERS[self.st.server]
        self.sel_title.setText(f"{p.name}  {self.st.mc or ''}")
        if self.st.mc:
            need = required_java(self.st.mc) if p.key != "babric" else 17
            self.java_lbl.setText(_("Required Java: <b>{0} or newer</b>").format(need))

    def _load_builds(self, mc):
        self._btoken += 1
        tok = self._btoken
        server = self.st.server
        self.builds.blockSignals(True)
        self.builds.clear()
        self.builds.blockSignals(False)
        self.build_note.setText("")
        if server in ("vanilla", "spigot", "bukkit"):
            self.builds.addItem(_("Not applicable (official file)") if server == "vanilla" else _("Latest BuildTools"))
            self.builds.setEnabled(False)
            return
        self.builds.setEnabled(False)
        self.bspin.start()

        def ok(builds):
            if tok != self._btoken:
                return
            self.bspin.stop()
            self.builds.blockSignals(True)
            self.builds.clear()
            sel = 0
            for i, b in enumerate(builds):
                self.builds.addItem(("★ " if b.recommended else "") + b.label, b.id)
                if (self.st.build and b.id == self.st.build) or (not self.st.build and b.recommended):
                    sel = i
            self.builds.setCurrentIndex(sel)
            self.builds.blockSignals(False)
            self.builds.setEnabled(bool(builds))
            if builds:
                self.st.build = self.builds.currentData()
                self.build_note.setText(_("★ = recommended build. Leave it unless you have a reason."))
            else:
                self.builds.addItem(_("No builds"))
                self.build_note.setText(_("This version has no builds. Choose another version."))
            self.changed.emit()

        def err(msg):
            if tok != self._btoken:
                return
            self.bspin.stop()
            self.builds.clear()
            self.builds.addItem(_("Automatic (latest recommended)"))
            self.st.build = ""
            self.build_note.setText(_("Could not load the build list; one will be picked automatically when installing. ({0})").format(msg))

        run_async(lambda sig: PROVIDERS[server].list_builds(mc), ok, err)

    def _build_picked(self, i):
        d = self.builds.itemData(i)
        self.st.build = d or ""

    def can_next(self):
        return bool(self.st.mc) and not (self.builds.isEnabled() and self.builds.count() and
                                         self.builds.currentText() == _("No builds"))


# ------------------------------------------------------------------ 4. Location & performance
class ResourcePage(Page):
    title = _("Location · performance")
    subtitle = _("About half of your RAM is a good amount. If Java is missing, it can be downloaded for you.")

    def __init__(self, st):
        super().__init__(st)
        self.total = total_ram_gb()
        g = Glass()
        lay = QVBoxLayout(g)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(16)

        lay.addWidget(label(_("Install folder"), "h3"))
        fl = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.textEdited.connect(self._folder_edit)
        fl.addWidget(self.folder, 1)
        b = Button(_("Browse"))
        b.clicked.connect(self._browse)
        fl.addWidget(b)
        lay.addLayout(fl)
        self.folder_note = label("", "small", True)
        lay.addWidget(self.folder_note)

        lay.addWidget(label(_("Memory (RAM)"), "h3"))
        rl = QHBoxLayout()
        self.ram = QSlider(Qt.Orientation.Horizontal)
        self.ram.setRange(1, max(2, self.total))
        self.ram.valueChanged.connect(self._ram)
        rl.addWidget(self.ram, 1)
        self.ram_lbl = label("", "h3")
        self.ram_lbl.setMinimumWidth(70)
        self.ram_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rl.addWidget(self.ram_lbl)
        rec = Button(_("Recommended {0}GB").format(recommended_ram(self.total)))
        rec.clicked.connect(lambda: self.ram.setValue(recommended_ram(self.total)))
        rl.addWidget(rec)
        lay.addLayout(rl)
        self.ram_note = label("", "small", True)
        lay.addWidget(self.ram_note)

        pl = QHBoxLayout()
        pl.addWidget(label(_("Server port"), "h3"))
        pl.addStretch(1)
        self.port = NoWheelSpin()
        self.port.setRange(1, 65535)
        self.port.setFixedWidth(120)
        self.port.valueChanged.connect(lambda v: self.st.values.__setitem__("server-port", v))
        pl.addWidget(self.port)
        lay.addLayout(pl)

        jl = QHBoxLayout()
        jl.addWidget(label("Java", "h3"))
        self.java_need = label("", "small")
        jl.addWidget(self.java_need)
        jl.addStretch(1)
        self.jspin = Spinner()
        self.jspin.hide()
        jl.addWidget(self.jspin)
        lay.addLayout(jl)
        jr = QHBoxLayout()
        self.java = NoWheelCombo()
        self.java.currentIndexChanged.connect(self._java_pick)
        jr.addWidget(self.java, 1)
        self.rescan = Button(_("Rescan"))
        self.rescan.clicked.connect(self.scan)
        jr.addWidget(self.rescan)
        self.get_java = Button(_("Install Java"), "primary")
        self.get_java.clicked.connect(self._install_java)
        jr.addWidget(self.get_java)
        lay.addLayout(jr)
        self.java_status = label("", "", True)
        lay.addWidget(self.java_status)
        self.jprog = Progress()
        self.jprog.hide()
        lay.addWidget(self.jprog)
        self.root.addWidget(g)
        self.root.addStretch(1)
        self._scanned = False
        self._installing = False

    def enter(self):
        if not self.st.folder:
            self.st.folder = default_folder(self.st.server, self.st.mc)
        self.folder.setText(self.st.folder)
        self._check_folder()
        self.ram.setValue(min(self.st.ram or recommended_ram(self.total), self.ram.maximum()))
        self._ram(self.ram.value())
        self.port.setValue(int(self.st.values.get("server-port", 25565)))
        need = PROVIDERS[self.st.server].java_for(self.st.mc) if self.st.server == "babric" else \
            required_java(self.st.mc)
        self.st.java_need = need
        self.java_need.setText(_("  {0} servers need Java {1} or newer").format(self.st.mc, need))
        self.get_java.setText(_("Install Java {0} automatically").format(need))
        if not self._scanned:
            self.scan()
        else:
            self._fill_java()

    def scan(self):
        self.jspin.start()
        self.java.clear()
        self.java.addItem(_("Looking for Java…"))
        self.java.setEnabled(False)

        def ok(javas):
            self.jspin.stop()
            self._scanned = True
            self.st.javas = javas
            self._fill_java()

        def err(m):
            self.jspin.stop()
            self.java_status.setText(_("Java search failed: {0}").format(m))

        run_async(lambda sig: find_javas(), ok, err)

    def _fill_java(self, prefer: str = ""):
        need = self.st.java_need
        self.java.blockSignals(True)
        self.java.clear()
        for j in self.st.javas:
            mark = "✓ " if j.major >= need else "✕ "
            self.java.addItem(mark + j.label, j.path)
            self.java.setItemData(self.java.count() - 1, j.path, Qt.ItemDataRole.ToolTipRole)
        self.java.blockSignals(False)
        self.java.setEnabled(bool(self.st.javas))
        if not self.st.javas:
            self.java.addItem(_("No installed Java found"))
            self.st.java = ""
        else:
            paths = [j.path for j in self.st.javas]
            cur = prefer or self.st.java
            okj = [j for j in self.st.javas if j.major >= need]
            if cur in paths and (any(j.path == cur and j.major >= need for j in self.st.javas) or not okj):
                pick = cur
            else:
                b = best_for(self.st.javas, need)
                pick = b.path if b else paths[0]
            self.java.setCurrentIndex(paths.index(pick))
            self.st.java = pick
        self._java_status()

    def _java_pick(self, i):
        d = self.java.itemData(i)
        if d:
            self.st.java = d
        self._java_status()

    def _java_status(self):
        need = self.st.java_need
        j = next((x for x in self.st.javas if x.path == self.st.java), None)
        if j and j.major >= need:
            self.java_status.setText(_("<span style='color:{0}'>● Ready</span>  <span style='color:{1}'>{2}</span>").format(OK, MUTED, j.path))
            self.get_java.setVisible(False)
        elif j:
            self.java_status.setText(_("<span style='color:{0}'>● Java {1} is too old.</span> Choose Java {2} or newer, or click automatic install.").format(DANGER, j.major, need))
            self.get_java.setVisible(True)
        else:
            self.java_status.setText(_("<span style='color:{0}'>● No Java found.</span> 'Install Java {1} automatically' downloads Temurin JDK into the installer's own folder.").format(WARN, need))
            self.get_java.setVisible(True)
        self.changed.emit()

    def _install_java(self):
        need = self.st.java_need
        self._installing = True
        self.get_java.setEnabled(False)
        self.rescan.setEnabled(False)
        self.jprog.show()
        self.jprog.set_value(0)
        self.java_status.setText(_("Downloading Temurin JDK {0}… (about 200 MB)").format(need))

        def work(sig):
            return install_jdk(need, lambda d, t: sig.prog.emit(d, t))

        def prog(d, t):
            if t:
                self.jprog.set_value(d * 100 / t)
                self.java_status.setText(_("Downloading Temurin JDK {0}… {1:.0f} / {2:.0f} MB").format(need, d / 1048576, t / 1048576))

        def ok(info):
            self._installing = False
            self.jprog.hide()
            self.get_java.setEnabled(True)
            self.rescan.setEnabled(True)
            if all(j.path != info.path for j in self.st.javas):
                self.st.javas.insert(0, info)
            self._fill_java(prefer=info.path)

        def err(m):
            self._installing = False
            self.jprog.hide()
            self.get_java.setEnabled(True)
            self.rescan.setEnabled(True)
            self.java_status.setText(_("<span style='color:{0}'>Java install failed:</span> {1}").format(DANGER, m))

        run_async(work, ok, err, prog)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, _("Choose install folder"), self.st.folder)
        if d:
            self.folder.setText(d)
            self._folder_edit(d)

    def _folder_edit(self, t):
        self.st.folder = t.strip()
        self.st.folder_custom = True
        self._check_folder()
        self.changed.emit()

    def _check_folder(self):
        from pathlib import Path
        p = Path(self.st.folder).expanduser() if self.st.folder else None
        if not p:
            self.folder_note.setText(_("Enter a folder."))
        elif p.is_dir() and any(p.iterdir()):
            self.folder_note.setText(_("<span style='color:{0}'>Files already exist.</span> server.properties will be merged and server files overwritten.").format(WARN))
        else:
            self.folder_note.setText(_("A new folder will be created."))

    def _ram(self, v):
        self.st.ram = v
        self.ram_lbl.setText(f"{v} GB")
        warn = ""
        if v > self.total - 2:
            warn = _("  <span style='color:{0}'>· Windows may run low on memory</span>").format(WARN)
        self.ram_note.setText(_("System RAM {0}GB · recommended {1}GB{2}").format(self.total, recommended_ram(self.total), warn))

    def can_next(self):
        if self._installing or not self.st.folder:
            return False
        j = next((x for x in self.st.javas if x.path == self.st.java), None)
        return bool(j and j.major >= self.st.java_need)

    def validate(self):
        if not self.can_next():
            return _("Choose Java {0} or newer, or install it automatically.").format(self.st.java_need)
        return None
