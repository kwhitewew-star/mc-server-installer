"""Add mods / plugins / datapacks step (Modrinth search + local files)."""

from __future__ import annotations
from ..i18n import _

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
                             QVBoxLayout, QWidget)

from ..core import modrinth as M
from ..core.net import get_bytes
from .pages_setup import Page
from .pages_config import Chip
from ..core.providers import PROVIDERS
from .state import icon_pool, run_async
from .widgets import DANGER, MUTED, OK, WARN, Button, ElideLabel, Glass, Spinner, label, wrap_label

_icon_cache: dict[str, QPixmap] = {}


class Icon(QLabel):
    def __init__(self, url: str, text: str):
        super().__init__(text[:1].upper())
        self.setFixedSize(42, 42)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: rgba(255,255,255,0.10); border-radius: 10px; font-weight: 800;")
        if url:
            if url in _icon_cache:
                self._set(_icon_cache[url])
            else:
                run_async(lambda sig: get_bytes(url, timeout=8, cache_sec=3600, retries=1), self._got(url),
                          lambda m: None, pool=icon_pool())

    def _got(self, url):
        def f(data):
            pm = QPixmap()
            if pm.loadFromData(data):
                pm = pm.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
                _icon_cache[url] = pm
                try:
                    self._set(pm)
                except RuntimeError:  # widget already deleted
                    pass
        return f

    def _set(self, pm):
        self.setText("")
        self.setPixmap(pm)
        self.setStyleSheet("border-radius: 10px;")


class HitRow(Glass):
    def __init__(self, hit: M.Hit, page: "AddonsPage"):
        super().__init__(radius=12, strength=8, frost=False)
        self.hit, self.page = hit, page
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(12)
        h.addWidget(Icon(hit.icon_url, hit.title), 0, Qt.AlignmentFlag.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(2)
        t = QHBoxLayout()
        t.setSpacing(8)
        name = ElideLabel(hit.title, "h3")
        name.setStyleSheet("font-size:10.5pt;")
        t.addWidget(name, 1)
        dl = label(f"⬇ {M.fmt_downloads(hit.downloads)}", "small")
        t.addWidget(dl, 0)
        v.addLayout(t)
        v.addWidget(ElideLabel(f"by {hit.author}", "small"))
        desc = hit.description.strip()
        d = wrap_label(desc[:110] + ("…" if len(desc) > 110 else ""))
        d.setToolTip(desc)
        v.addWidget(d)
        self.msg = wrap_label("")
        self.msg.hide()
        v.addWidget(self.msg)
        h.addLayout(v, 1)
        self.btn = Button(_("Add"))
        self.btn.setFixedWidth(88)
        self.btn.clicked.connect(lambda: page.add_hit(self))
        h.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.sync()

    def sync(self):
        added = self.page.has(self.hit.project_id)
        self.btn.setEnabled(not added)
        self.btn.setText(_("Added ✓") if added else _("Add"))
        self.btn.kind = "ghost" if added else "primary"
        self.btn.update()

    def busy(self):
        self.btn.setEnabled(False)
        self.btn.setText(_("Checking…"))

    def error(self, msg, warn=False):
        self.msg.setText(msg)
        self.msg.setStyleSheet(f"color:{WARN if warn else DANGER}")
        self.msg.show()
        if not warn:
            self.btn.setEnabled(True)
            self.btn.setText(_("Retry"))


class SelRow(QWidget):
    def __init__(self, a: M.Addon, page: "AddonsPage"):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 2, 0, 2)
        color = {"mod": "#fbbf24", "plugin": "#60a5fa", "datapack": "#c084fc"}.get(a.kind, MUTED)
        tag = label(M.KIND_LABEL[a.kind], "small")
        tag.setStyleSheet(f"color:{color}; font-weight:700;")
        tag.setFixedWidth(52)
        h.addWidget(tag)
        v = QVBoxLayout()
        v.setSpacing(0)
        v.addWidget(ElideLabel(a.title))
        sub = a.version_number or (Path(a.local_path).name if a.local_path else "")
        if a.dependency_of:
            sub += _("  ·  required by {0} (auto)").format(a.dependency_of)
        if a.local_path:
            sub = _("Local file · ") + sub
        v.addWidget(wrap_label(sub))
        h.addLayout(v, 1)
        x = Button("✕")
        x.setFixedSize(34, 30)
        x.clicked.connect(lambda: page.remove(a))
        h.addWidget(x)


class AddonsPage(Page):
    title = _("Add mods · plugins")
    subtitle = _("Finds only what matches your server type and version on Modrinth. Required dependencies are added automatically.")

    def __init__(self, st):
        super().__init__(st)
        bar = QHBoxLayout()
        self.kind_box = QHBoxLayout()
        self.kind_box.setSpacing(6)
        bar.addLayout(self.kind_box)
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Search (empty = most popular)  e.g. JEI, LuckPerms, Sodium"))
        self.search.returnPressed.connect(lambda: self.do_search(reset=True))
        bar.addWidget(self.search, 1)
        go = Button(_("Search"), "primary")
        go.clicked.connect(lambda: self.do_search(reset=True))
        bar.addWidget(go)
        self.root.addLayout(bar)
        self.note = label("", "small", True)
        self.root.addWidget(self.note)

        body = QHBoxLayout()
        body.setSpacing(14)
        left = Glass()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.results = QVBoxLayout(inner)
        self.results.setContentsMargins(0, 0, 6, 0)
        self.results.setSpacing(8)
        self.results.addStretch(1)
        self.scroll.setWidget(inner)
        ll.addWidget(self.scroll, 1)
        st_row = QHBoxLayout()
        self.spin = Spinner()
        self.spin.hide()
        st_row.addWidget(self.spin)
        self.status = label("", "small", True)
        st_row.addWidget(self.status, 1)
        self.more = Button(_("Load more"))
        self.more.clicked.connect(lambda: self.do_search(reset=False))
        self.more.hide()
        st_row.addWidget(self.more)
        ll.addLayout(st_row)
        body.addWidget(left, 5)

        right = Glass()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 14, 16, 14)
        self.sel_title = ElideLabel(_("To install"), "h3")
        self.sel_title.setTextFormat(Qt.TextFormat.PlainText)
        rl.addWidget(self.sel_title)
        self.sel_scroll = QScrollArea()
        self.sel_scroll.setWidgetResizable(True)
        self.sel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sel_inner = QWidget()
        self.sel_list = QVBoxLayout(sel_inner)
        self.sel_list.setContentsMargins(0, 0, 10, 0)
        self.sel_list.setSpacing(4)
        self.sel_list.addStretch(1)
        self.sel_scroll.setWidget(sel_inner)
        rl.addWidget(self.sel_scroll, 1)
        self.empty = wrap_label(_("Nothing yet. Add from the left or add your own files. You can also skip this step."))
        rl.addWidget(self.empty)
        btns = QHBoxLayout()
        self.local_btn = Button(_("＋ Add local file"))
        self.local_btn.clicked.connect(self.add_local)
        btns.addWidget(self.local_btn)
        clear = Button(_("Clear all"))
        clear.clicked.connect(self.clear_all)
        btns.addWidget(clear)
        rl.addLayout(btns)
        right.setMinimumWidth(250)
        right.setMaximumWidth(330)
        body.addWidget(right, 0)
        self.root.addLayout(body, 1)

        self.kind = "mod"
        self.kind_group = QButtonGroup(self)
        self.offset = 0
        self.token = 0
        self.rows: list[HitRow] = []
        self._ctx = None

    # ---- State ----
    @property
    def addons(self) -> list[M.Addon]:
        return [M.Addon.from_dict(d) for d in self.st.addons]

    def _store(self, items: list[M.Addon]):
        self.st.addons = [a.to_dict() for a in items]

    def has(self, pid: str) -> bool:
        return any(d.get("project_id") == pid for d in self.st.addons)

    def ctx_key(self):
        return (self.st.server, self.st.mc, ",".join(M.loaders_for(self.st.server, "mod", self.st.build)))

    # ---- Entering the page ----
    def enter(self):
        key = self.ctx_key()
        if self.st.addons_ctx and list(self.st.addons_ctx) != list(key) and self.st.addons:
            self.st.addons = [d for d in self.st.addons if d.get("local_path")]
            self.note.setText(_("<span style='color:{0}'>The server type or version changed, so Modrinth items were cleared. (Local files are kept)</span>").format(WARN))
        else:
            self.note.setText("")
        self.st.addons_ctx = list(key)
        while self.kind_box.count():
            w = self.kind_box.takeAt(0).widget()
            if w:
                self.kind_group.removeButton(w)
                w.hide()
                w.deleteLater()
        kinds = M.kinds_for(self.st.server)
        if self.kind not in kinds:
            self.kind = kinds[0]
        for k in kinds:
            c = Chip(M.KIND_LABEL[k])
            self.kind_group.addButton(c)
            c.setChecked(k == self.kind)
            c.clicked.connect(lambda _=False, kk=k: self._kind(kk))
            self.kind_box.addWidget(c)
        p = PROVIDERS[self.st.server]
        if self.st.server == "vanilla":
            self.note.setText(self.note.text() + _("  Vanilla servers cannot use mods or plugins, only datapacks."))
        elif p.kind == "hybrid":
            self.note.setText(self.note.text() + _("  Hybrid server: you can add both mods and plugins."))
        if self._ctx != (key, self.kind):
            self.do_search(reset=True)
        self.refresh_sel()

    def _kind(self, k):
        self.kind = k
        self.do_search(reset=True)

    # ---- Search ----
    def do_search(self, reset: bool):
        if reset:
            self.offset = 0
            for r in self.rows:
                r.hide()
                self.results.removeWidget(r)
                r.deleteLater()
            self.rows = []
        self.token += 1
        tok = self.token
        st, kind, q, off = self.st, self.kind, self.search.text(), self.offset
        hide = bool(getattr(st, "app", {}).get("hide_client_mods", True))
        self._ctx = (self.ctx_key(), kind)
        self.spin.start()
        self.more.hide()
        self.status.setStyleSheet("")
        self.status.setText(_("Searching {0}…").format(M.KIND_LABEL[kind]))

        def ok(res):
            if tok != self.token:
                return
            hits, total = res
            self.spin.stop()
            for h in hits:
                row = HitRow(h, self)
                self.results.insertWidget(self.results.count() - 1, row)
                self.rows.append(row)
            self.offset += len(hits)
            if not self.rows:
                self.status.setText(_("No {1} found for {0}.").format(st.mc, M.KIND_LABEL[kind]))
            else:
                self.status.setText(_("Showing {1} of {0:,} · ").format(total, len(self.rows))
                                    + (_("by relevance") if q.strip() else _("by popularity")))
            self.more.setVisible(self.offset < total)

        def err(m):
            if tok != self.token:
                return
            self.spin.stop()
            self.status.setText(_("Modrinth search failed: {0}").format(m))
            self.status.setStyleSheet(f"color:{DANGER}")

        run_async(lambda sig: M.search(q, kind, st.server, st.mc, st.build, off, 20, hide), ok, err)

    # ---- Add / remove ----
    def add_hit(self, row: HitRow):
        h = row.hit
        row.busy()
        st = self.st
        existing = {d.get("project_id") for d in st.addons if d.get("project_id")}

        def ok(res):
            items, warns = res
            cur = self.addons
            cur += items
            self._store(cur)
            for r in self.rows:
                r.sync()
            self.refresh_sel()
            deps = len(items) - 1
            self.status.setStyleSheet(f"color:{OK}")
            self.status.setText(_("Added '{0}'").format(h.title) + (_(" (+ {0} required dependencies added)").format(deps) if deps else ""))
            if warns:
                row.error("\n".join(warns), warn=True)
                self.status.setStyleSheet(f"color:{WARN}")
                self.status.setText(_("Added '{0}' · {1} dependencies had no compatible file (see the note under the item)").format(h.title, len(warns)))

        def err(m):
            row.error(m)
            self.status.setStyleSheet(f"color:{DANGER}")
            self.status.setText(_("Could not add '{0}': {1}").format(h.title, m))

        run_async(lambda sig: M.resolve(h.project_id, h.title, h.kind, st.server, st.mc, st.build, existing),
                  ok, err)

    def add_local(self):
        kind = self.kind
        filt = _("Datapack (*.zip)") if kind == "datapack" else _("Mod/plugin (*.jar)")
        files, _x = QFileDialog.getOpenFileNames(self, _("Choose {0} files").format(M.KIND_LABEL[kind]), str(Path.home()), filt)
        if not files:
            return
        cur = self.addons
        have = {a.local_path for a in cur}
        for f in files:
            if f not in have:
                cur.append(M.Addon(kind=kind, title=Path(f).stem, local_path=f, filename=Path(f).name))
        self._store(cur)
        self.refresh_sel()

    def remove(self, a: M.Addon):
        cur = [x for x in self.addons if not (x.project_id == a.project_id and x.local_path == a.local_path
                                               and x.title == a.title)]
        # also remove dependencies that were added automatically for this item
        cur = [x for x in cur if x.dependency_of != a.title]
        self._store(cur)
        for r in self.rows:
            r.sync()
        self.refresh_sel()

    def clear_all(self):
        self._store([])
        for r in self.rows:
            r.sync()
        self.refresh_sel()

    def refresh_sel(self):
        while self.sel_list.count() > 1:
            w = self.sel_list.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        items = self.addons
        for a in items:
            self.sel_list.insertWidget(self.sel_list.count() - 1, SelRow(a, self))
        self.empty.setVisible(not items)
        counts = {}
        for a in items:
            counts[a.kind] = counts.get(a.kind, 0) + 1
        txt = " · ".join(f"{M.KIND_LABEL[k]} {n}" for k, n in counts.items())
        self.sel_title.setText(_("To install · {0}").format(txt) if txt else _("To install"))
        self.changed.emit()
