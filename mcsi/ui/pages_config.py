"""Later steps: server settings, game rules, manage & launch, review, install, done."""

from __future__ import annotations
from ..i18n import _

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import (QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit, QPlainTextEdit,
                             QScrollArea, QVBoxLayout, QWidget)

from ..core import schema
from ..core.installer import Installer, Plan, rule_commands, split_names
from ..core.java import APP_DIR
from ..core.net import Cancelled
from .pages_setup import Page
from ..core.providers import PROVIDERS
from .state import local_ip, open_path
from .widgets import (ACCENT, DANGER, MUTED, OK, WARN, Button, CheckBurst, ElideLabel, Glass, NoWheelCombo,
                         NoWheelSpin, Progress, Spinner, Toggle, label, wrap_label)
from ..core.versions import props_moved_to_gamerules


class Chip(Button):
    def __init__(self, text):
        super().__init__(text)
        self.setCheckable(True)
        self.setMinimumHeight(30)
        f = self.font()
        f.setPointSizeF(9)
        self.setFont(f)
        self.toggled.connect(lambda _: self.update())

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 26, 30)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, e):
        if self.isChecked():
            self.kind = "primary"
        else:
            self.kind = "ghost"
        super().paintEvent(e)


class Row(Glass):
    """One settings row: name/description + editor + changed marker."""

    def __init__(self, spec: schema.S, editor: QWidget):
        super().__init__(radius=12, strength=8, frost=False)
        self.spec = spec
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 14, 10)
        lay.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.dot = label("●")
        self.dot.setStyleSheet(f"color:{ACCENT}; font-size:8pt;")
        self.dot.setToolTip(_("Changed from the default"))
        top.addWidget(self.dot)
        name = label(spec.label, "h3")
        name.setStyleSheet("font-size:10pt;")
        top.addWidget(name)
        key = (spec.rule_new or spec.rule_old) if spec.key.startswith("rule:") else spec.key
        top.addStretch(1)
        left.addLayout(top)
        if not spec.key.startswith(("jvm:", "launch:", "manage:")):
            k = ElideLabel(key, "small")
            k.setStyleSheet("color:#8d97b5; font-family:Consolas,monospace; font-size:8.3pt;")
            left.addWidget(k)
        desc = " ".join(x for x in (spec.desc, spec.note) if x)
        if desc:
            left.addWidget(wrap_label(desc))
        lay.addLayout(left, 1)
        lay.addWidget(editor, 0, Qt.AlignmentFlag.AlignVCenter)


class SettingsPanel(Page):
    """Shared page that lists settings with search, groups and per-mode filtering."""

    exclude = {"server-port"}

    def __init__(self, st, specs: list[schema.S], banner: str = ""):
        super().__init__(st)
        self.specs = [s for s in specs if s.key not in self.exclude]
        self.editors: dict[str, QWidget] = {}
        self.rows: dict[str, Row] = {}
        if banner:
            b = label(banner, "small", True)
            b.setStyleSheet(f"color:{MUTED}; background: rgba(96,165,250,0.10); border:1px solid "
                            "rgba(96,165,250,0.30); border-radius:10px; padding:8px 12px;")
            self.root.addWidget(b)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Search settings (name, description, key)"))
        self.search.textChanged.connect(self.refilter)
        bar.addWidget(self.search, 1)
        bar.addWidget(label(_("Show all"), "small"))
        self.show_all = Toggle(False)
        self.show_all.toggled.connect(lambda _: self.refilter())
        bar.addWidget(self.show_all)
        reset = Button(_("Defaults"))
        reset.clicked.connect(self.reset)
        bar.addWidget(reset)
        self.count = label("", "small")
        bar.addWidget(self.count)
        self.root.addLayout(bar)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.group_btns = QButtonGroup(self)
        self.group = _("All")
        groups = [_("All")] + list(dict.fromkeys(s.group for s in self.specs))
        for gname in groups:
            c = Chip(gname)
            self.group_btns.addButton(c)
            c.clicked.connect(lambda _=False, g=gname: self._group(g))
            chips.addWidget(c)
            if gname == _("All"):
                c.setChecked(True)
        chips.addStretch(1)
        self.root.addLayout(chips)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 8, 0)
        self.list.setSpacing(8)
        self.headers: dict[str, QWidget] = {}
        last = None
        for s in self.specs:
            if s.group != last:
                h = label(s.group, "h3")
                h.setStyleSheet(f"color:{ACCENT}; padding-top:6px;")
                self.list.addWidget(h)
                self.headers[s.group] = h
                last = s.group
            ed = self.make_editor(s)
            row = Row(s, ed)
            self.editors[s.key] = ed
            self.rows[s.key] = row
            self.list.addWidget(row)
        self.list.addStretch(1)
        self.scroll.setWidget(inner)
        self.root.addWidget(self.scroll, 1)

    # ---- Editors ----
    def make_editor(self, s: schema.S) -> QWidget:
        v = self.st.values.get(s.key, s.default)
        if s.type == "bool":
            w = Toggle(bool(v))
            w.toggled.connect(lambda on, k=s.key: self.set(k, on))
            return w
        if s.type == "int":
            w = NoWheelSpin()
            w.setRange(s.min, min(s.max, 2_147_483_647))
            w.setValue(int(v))
            w.setFixedWidth(150)
            w.valueChanged.connect(lambda x, k=s.key: self.set(k, int(x)))
            return w
        if s.type == "choice":
            w = NoWheelCombo()
            for val, lab in s.choices:
                w.addItem(lab, val)
            i = max(0, w.findData(v))
            w.setCurrentIndex(i)
            w.setFixedWidth(210)
            w.currentIndexChanged.connect(lambda i, k=s.key, ww=w: self.set(k, ww.itemData(i)))
            return w
        if s.key == "manage:icon":
            box = QWidget()
            h = QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            e = QLineEdit(str(v))
            e.setReadOnly(True)
            e.setPlaceholderText(_("Not set"))
            e.setFixedWidth(150)
            b = Button(_("Choose image"))
            b.clicked.connect(lambda: self._pick_icon(e))
            c = Button(_("Clear"))
            c.clicked.connect(lambda: (e.setText(""), self.set("manage:icon", "")))
            h.addWidget(e)
            h.addWidget(b)
            h.addWidget(c)
            box.setText = e.setText  # type: ignore[attr-defined]
            return box
        w = QLineEdit(str(v))
        w.setFixedWidth(250)
        if s.type == "secret":
            w.setEchoMode(QLineEdit.EchoMode.Password)
        if s.key in ("manage:ops", "manage:whitelist"):
            w.setPlaceholderText(_("e.g. Steve, Alex"))
        w.textChanged.connect(lambda t, k=s.key: self.set(k, t))
        return w

    def _pick_icon(self, e: QLineEdit):
        f, _x = QFileDialog.getOpenFileName(self, _("Choose server icon"), str(Path.home()), _("Images (*.png *.jpg *.jpeg *.bmp)"))
        if not f:
            return
        img = QImage(f)
        if img.isNull():
            return
        side = min(img.width(), img.height())
        img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
        img = img.scaled(64, 64, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        out = APP_DIR / "server-icon.png"
        img.save(str(out), "PNG")
        e.setText(str(out))
        self.set("manage:icon", str(out))

    def set(self, key, val):
        self.st.values[key] = val
        spec = schema.BY_KEY[key]
        self.rows[key].dot.setVisible(val != spec.default)
        self._count()

    def load_values(self):
        for s in self.specs:
            w = self.editors[s.key]
            v = self.st.values.get(s.key, s.default)
            w.blockSignals(True)
            if isinstance(w, Toggle):
                w.setChecked(bool(v))
            elif isinstance(w, NoWheelSpin):
                w.setValue(int(v))
            elif isinstance(w, NoWheelCombo):
                w.setCurrentIndex(max(0, w.findData(v)))
            elif isinstance(w, QLineEdit):
                w.setText(str(v))
            elif hasattr(w, "setText"):
                w.setText(str(v))
            w.blockSignals(False)
            self.rows[s.key].dot.setVisible(v != s.default)

    def reset(self):
        for s in self.specs:
            self.st.values[s.key] = s.default
        self.load_values()
        self._count()

    def _group(self, g):
        self.group = g
        self.refilter()

    def enter(self):
        self.load_values()
        self.show_all.blockSignals(True)
        self.show_all.setChecked(self.st.mode == "detailed")
        self.show_all.blockSignals(False)
        self.refilter()

    def visible_specs(self):
        t = self.search.text().strip().lower()
        out = []
        for s in self.specs:
            if not self.show_all.isChecked() and s.level != "b":
                continue
            if self.group != _("All") and s.group != self.group:
                continue
            hay = f"{s.label} {s.desc} {s.key} {s.rule_old or ''} {s.rule_new or ''}".lower()
            if t and t not in hay:
                continue
            out.append(s)
        return out

    def refilter(self):
        vis = {s.key for s in self.visible_specs()}
        groups = set()
        for k, row in self.rows.items():
            on = k in vis
            row.setVisible(on)
            if on:
                groups.add(row.spec.group)
        for g, h in self.headers.items():
            h.setVisible(g in groups)
        self._count()

    def _count(self):
        vis = len(self.visible_specs())
        changed = sum(1 for s in self.specs if self.st.values.get(s.key, s.default) != s.default)
        self.count.setText(_("  {0}/{1} shown · {2} changed").format(vis, len(self.specs), changed))


class PropsPage(SettingsPanel):
    title = _("Server settings (server.properties)")
    subtitle = _("Every option, grouped. The grey key is the name used in the actual file.")

    def __init__(self, st):
        super().__init__(st, schema.PROPS)


class RulesPage(SettingsPanel):
    title = _("Game rules (gamerule)")
    subtitle = _("Only rules that differ from the default are applied through the console on first run.")

    def __init__(self, st):
        super().__init__(st, schema.RULES, _("Game rules are stored in the world, so 'First run' under 'Manage & launch' must be on. The new snake_case names (1.21.11+) or the old names are picked automatically for your version."))


class ManagePage(SettingsPanel):
    title = _("Manage & launch")
    subtitle = _("Ops, whitelist, server icon, JVM options, auto-restart, backups and other extras.")

    def __init__(self, st):
        super().__init__(st, schema.LAUNCH + schema.MANAGE)


# ------------------------------------------------------------------ Review
class SummaryPage(Page):
    title = _("Review & install")
    subtitle = _("The server will be installed with the settings below. Click a step on the left to change something.")

    def __init__(self, st):
        super().__init__(st)
        self.grid_box = Glass()
        self.grid = QGridLayout(self.grid_box)
        self.grid.setContentsMargins(22, 18, 22, 18)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(12)
        self.root.addWidget(self.grid_box)
        self.warns = label("", "", True)
        self.root.addWidget(self.warns)
        eg = Glass()
        el = QHBoxLayout(eg)
        el.setContentsMargins(20, 14, 20, 14)
        txt = label(_("<b>I accept the Minecraft EULA</b><br><span style='color:#9aa4bf'>Required to run the server. <a style='color:#5eead4' href='https://aka.ms/MinecraftEULA'>Read the EULA</a></span>"), "", True)
        txt.setOpenExternalLinks(True)
        el.addWidget(txt, 1)
        self.eula = Toggle(st.eula)
        self.eula.toggled.connect(self._eula)
        el.addWidget(self.eula)
        self.root.addWidget(eg)
        self.root.addStretch(1)

    def _eula(self, on):
        self.st.eula = on
        self.changed.emit()

    def enter(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        st, p = self.st, PROVIDERS[self.st.server]
        java = next((j for j in st.javas if j.path == st.java), None)
        items = [(_("Server"), p.name), (_("Version"), st.mc), (_("Build"), st.build or _("Automatic (recommended)")),
                 (_("Memory"), f"{st.ram} GB"), (_("Port"), str(st.values.get("server-port", 25565))),
                 ("Java", java.label if java else "?"), (_("Install folder"), st.folder),
                 (_("Changed settings"), _("{0} / {1}").format(st.changed_count(), schema.count())),
                 (_("Mods · plugins"), _("{0}").format(len(st.addons)) if st.addons else _("None")),
                 (_("First run"), _("On (world generation + check)") if st.values.get("manage:first_run", True) else _("Off"))]
        for i, (k, v) in enumerate(items):
            r, c = divmod(i, 3)
            box = QVBoxLayout()
            w = QWidget()
            w.setLayout(box)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            box.addWidget(label(k, "small"))
            vl = label(v, "h3", True)
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(vl)
            self.grid.addWidget(w, r, c)
        self.eula.blockSignals(True)
        self.eula.setChecked(st.eula)
        self.eula.blockSignals(False)
        w = []
        cmds = rule_commands(st.values, st.mc) if st.mc else []
        first = st.values.get("manage:first_run", True)
        if cmds and not first:
            w.append(_("{0} game rules were changed, but first run is off so they will not be applied.").format(len(cmds)))
        if st.mc and props_moved_to_gamerules(st.mc):
            moved = [s.label for s in schema.PROPS if s.rule_new and
                     st.values.get(s.key, s.default) != s.default]
            if moved and not first:
                w.append(_("{0} are game rules on {1}, so first run is required.").format(', '.join(moved), st.mc))
        if not st.values.get("online-mode", True):
            w.append(_("Online mode is off. Others can join with your name, so a whitelist is recommended."))
        if p.needs_git:
            w.append(_("Spigot/Bukkit need Git and take a while to build."))
        if st.values.get("white-list") and not split_names(st.values.get("manage:whitelist", "")) and \
                not split_names(st.values.get("manage:ops", "")):
            w.append(_("The whitelist is on but no players are listed. Nobody will be able to join."))
        if Path(st.folder).expanduser().is_dir() and any(Path(st.folder).expanduser().iterdir()):
            w.append(_("The install folder already has files. Server files will be overwritten."))
        self.warns.setText("".join(f"<div style='color:{WARN}; margin:3px 0'>⚠ {x}</div>" for x in w))

    def can_next(self):
        return self.st.eula


# ------------------------------------------------------------------ Install
STAGES = [_("Checking Java"), _("Downloading server files"), _("Downloading mods · plugins"), _("Writing config files"), _("Preparing extras"), _("First run · world generation"),
          _("Port forwarding (UPnP)"), _("Finishing")]


class Worker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    stage = pyqtSignal(int, str)
    done = pyqtSignal(bool, str, list)

    def __init__(self, plan: Plan):
        super().__init__()
        self.plan = plan
        self.cancelled = False
        self.inst: Installer | None = None

    def run(self):
        self.inst = Installer(self.plan, self.log.emit, self.progress.emit, self.stage.emit,
                              lambda: self.cancelled)
        try:
            self.inst.execute()
            self.done.emit(True, "", self.inst.summary)
        except Cancelled:
            self.done.emit(False, _("Installation was cancelled."), [])
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e) or type(e).__name__, [])

    def cancel(self):
        self.cancelled = True
        if self.inst:
            self.inst.kill()


class StageRow(QWidget):
    def __init__(self, text):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        self.icon = label("○")
        self.icon.setFixedWidth(22)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin = Spinner(18)
        self.spin.hide()
        self.text = label(text)
        h.addWidget(self.icon)
        h.addWidget(self.spin)
        h.addWidget(self.text, 1)
        self.set("wait")

    def set(self, state):
        self.spin.stop()
        self.icon.show()
        if state == "run":
            self.icon.hide()
            self.spin.start()
            self.text.setStyleSheet("color:white; font-weight:700;")
        elif state == "ok":
            self.icon.setText("✓")
            self.icon.setStyleSheet(f"color:{OK}; font-weight:800;")
            self.text.setStyleSheet(f"color:{MUTED};")
        elif state == "err":
            self.icon.setText("✕")
            self.icon.setStyleSheet(f"color:{DANGER}; font-weight:800;")
            self.text.setStyleSheet(f"color:{DANGER};")
        elif state == "skip":
            self.icon.setText("–")
            self.icon.setStyleSheet(f"color:{MUTED};")
            self.text.setStyleSheet("color:#5f6886;")
        else:
            self.icon.setText("○")
            self.icon.setStyleSheet("color:#8790ad;")
            self.text.setStyleSheet("color:#a7b0ca;")


class InstallPage(Page):
    title = _("Installing")
    subtitle = _("Do not close the window. This can take a few minutes depending on the server type.")
    finished = pyqtSignal(bool)

    def __init__(self, st):
        super().__init__(st)
        top = Glass()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(22, 18, 22, 18)
        tl.setSpacing(8)
        self.rows = [StageRow(s) for s in STAGES]
        for r in self.rows:
            tl.addWidget(r)
        tl.addSpacing(6)
        pr = QHBoxLayout()
        self.bar = Progress()
        pr.addWidget(self.bar, 1)
        self.pct = label("0%", "h3")
        self.pct.setFixedWidth(52)
        self.pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        pr.addWidget(self.pct)
        tl.addLayout(pr)
        self.status = label("", "small", True)
        tl.addWidget(self.status)
        self.root.addWidget(top)
        lb = QHBoxLayout()
        self.log_toggle = Button(_("Hide log"))
        self.log_toggle.clicked.connect(self._toggle_log)
        lb.addWidget(self.log_toggle)
        lb.addStretch(1)
        self.cancel_btn = Button(_("Cancel"), "danger")
        self.cancel_btn.clicked.connect(self._cancel)
        lb.addWidget(self.cancel_btn)
        self.root.addLayout(lb)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        self.root.addWidget(self.log, 1)
        self.worker: Worker | None = None
        self.running = False
        self.result: tuple[bool, str, list] = (False, "", [])
        self.forward = None
        self._cur = -1

    def start(self):
        st = self.st
        java = next((j for j in st.javas if j.path == st.java), None)
        plan = Plan(server=st.server, mc=st.mc, build=st.build, folder=st.folder, ram_gb=st.ram, java=st.java,
                    java_major=java.major if java else 0, values=dict(st.values), eula=st.eula,
                    addons=list(st.addons))
        self.log.clear()
        for r in self.rows:
            r.set("wait")
        if not st.addons:
            self.rows[2].set("skip")
        if not st.values.get("manage:first_run", True):
            self.rows[5].set("skip")
        if not st.values.get("manage:upnp", True):
            self.rows[6].set("skip")
        self.forward = None
        self.bar.set_value(0)
        self._cur = -1
        self.running = True
        self.cancel_btn.setEnabled(True)
        self.worker = Worker(plan)
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.progress.connect(self._prog)
        self.worker.stage.connect(self._stage)
        self.worker.done.connect(self._done)
        self.worker.start()

    def _prog(self, v):
        self.bar.set_value(v)
        self.pct.setText(f"{v}%")

    def _stage(self, i, text):
        for j in range(max(0, self._cur), i):
            if self.rows[j].icon.text() != "–":
                self.rows[j].set("ok")
        self._cur = i
        self.rows[i].set("run")
        self.status.setText(text)

    def _done(self, ok, msg, summary):
        self.running = False
        self.cancel_btn.setEnabled(False)
        if ok:
            for r in self.rows:
                if r.icon.text() != "–":
                    r.set("ok")
            self._prog(100)
            self.status.setText(_("Done"))
            try:
                (Path(self.st.folder).expanduser() / "install.log").write_text(self.log.toPlainText(), encoding="utf-8")
            except OSError:
                pass
        else:
            if 0 <= self._cur < len(self.rows):
                self.rows[self._cur].set("err")
            self.status.setText(msg.splitlines()[0] if msg else _("Failed"))
            self.status.setStyleSheet(f"color:{DANGER}")
            self.log.appendPlainText(_("\n[Error] ") + msg)
        self.forward = self.worker.inst.forward if self.worker and self.worker.inst else None
        self.result = (ok, msg, summary)
        self.finished.emit(ok)

    def _cancel(self):
        if self.worker and self.running:
            self.status.setText(_("Cancelling…"))
            self.worker.cancel()

    def _toggle_log(self):
        v = not self.log.isVisible()
        self.log.setVisible(v)
        self.log_toggle.setText(_("Hide log") if v else _("Show log"))


# ------------------------------------------------------------------ Done
class DonePage(Page):
    restart = pyqtSignal()
    back_to = pyqtSignal(str)
    port_guide = pyqtSignal()

    def __init__(self, st):
        super().__init__(st)
        self.root.setContentsMargins(40, 36, 40, 10)
        top = QHBoxLayout()
        self.burst = CheckBurst()
        top.addWidget(self.burst)
        tv = QVBoxLayout()
        self.h = label("", "h1")
        self.sub = label("", "muted", True)
        tv.addStretch(1)
        tv.addWidget(self.h)
        tv.addWidget(self.sub)
        tv.addStretch(1)
        top.addLayout(tv, 1)
        self.root.addLayout(top)
        self.info = Glass()
        il = QVBoxLayout(self.info)
        il.setContentsMargins(22, 16, 22, 16)
        il.setSpacing(10)
        self.addr = label("", "", True)
        self.addr.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        il.addWidget(self.addr)
        self.extra = label("", "small", True)
        self.extra.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        il.addWidget(self.extra)
        self.root.addWidget(self.info)
        btns = QHBoxLayout()
        self.run_btn = Button(_("▶  Start server"), "primary")
        self.run_btn.clicked.connect(self._run)
        self.copy_btn = Button(_("Copy address"))
        self.copy_btn.clicked.connect(self._copy)
        self.port_btn = Button(_("Port forwarding"))
        self.port_btn.clicked.connect(self.port_guide.emit)
        self.open_btn = Button(_("Open folder"))
        self.open_btn.clicked.connect(lambda: open_path(str(Path(self.st.folder).expanduser())))
        self.again = Button(_("Start over"))
        self.again.clicked.connect(self.restart.emit)
        self.retry = Button(_("Change settings"))
        self.retry.clicked.connect(lambda: self.back_to.emit("summary"))
        for b in (self.run_btn, self.copy_btn, self.port_btn, self.open_btn, self.retry, self.again):
            btns.addWidget(b)
        btns.addStretch(1)
        self.root.addLayout(btns)
        self.root.addStretch(1)
        self._addr = ""

    def show_result(self, ok: bool, msg: str, summary: list, forward=None):
        st = self.st
        port = st.values.get("server-port", 25565)
        ip = local_ip()
        self._addr = f"{ip}:{port}" if port != 25565 else ip
        self.burst.play(ok)
        self.run_btn.setVisible(ok)
        self.copy_btn.setVisible(ok)
        self.port_btn.setVisible(ok)
        self.retry.setVisible(not ok)
        if ok:
            self.h.setText(_("Installed!"))
            self.sub.setText(_("Your {0} {1} server is ready.").format(PROVIDERS[st.server].name, st.mc))
            local = _("<b>This PC</b>  <span style='color:{0}'>localhost{1}</span><br><b>Same router (Wi-Fi)</b>  "
                      "<span style='color:{2}'>{3}</span>").format(ACCENT, '' if port == 25565 else f':{port}', ACCENT,
                                                                   self._addr)
            if forward is not None and forward.ok and forward.external_ip:
                ext = forward.external_ip if port == 25565 else f"{forward.external_ip}:{port}"
                outside = _("<b>Outside (internet)</b>  <span style='color:{0}'>{1}</span>  <span style='color:{2}'>"
                            "· ports opened automatically (UPnP)</span>").format(ACCENT, ext, OK)
            elif forward is not None:
                outside = "<span style='color:{0}'>{1}</span>".format(WARN, _(
                    "Automatic port forwarding did not work. Click 'Port forwarding' for step-by-step instructions."))
            else:
                outside = "<span style='color:{0}'>{1}</span>".format(MUTED, _(
                    "For players outside your network, the port must be forwarded. Click 'Port forwarding' for help."))
            self.addr.setText(local + "<br>" + outside)
            files = _("Run with start.bat · back up with backup.bat · install log in install.log")
            self.extra.setText("<br>".join([files] + [str(s) for s in summary]))
        else:
            self.h.setText(_("Installation failed"))
            self.sub.setText(_("Check the cause below and try again. The full log is on the install step."))
            self.addr.setText(f"<span style='color:{DANGER}'>{msg.replace(chr(10), '<br>')}</span>")
            self.extra.setText("")

    def _run(self):
        d = Path(self.st.folder).expanduser()
        if os.name == "nt":
            subprocess.Popen(["cmd", "/c", "start", "", "start.bat"], cwd=str(d), shell=False)
        else:
            subprocess.Popen(["bash", "start.sh"], cwd=str(d), start_new_session=True)

    def _copy(self):
        QGuiApplication.clipboard().setText(self._addr)
        self.copy_btn.setText(_("Copied ✓"))
