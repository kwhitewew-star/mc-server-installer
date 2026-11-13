"""Modpack window: search Modrinth modpacks, or open a .mrpack / CurseForge zip / server pack file."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PyQt6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLineEdit, QScrollArea, QSizePolicy,
                             QVBoxLayout, QWidget)

from ..core import modpack as mp
from ..core.java import APP_DIR
from ..core.providers import PROVIDERS
from ..i18n import _
from ..core.modrinth import fmt_downloads
from .overlay import Overlay
from .remote_icon import RemoteIcon
from .state import run_async
from .widgets import (ACCENT, DANGER, MUTED, TEXT, WARN, Button, ElideLabel, FlowLayout, Hover, NoWheelCombo,
                      Spinner, label, wrap_label)

CACHE = APP_DIR / "modpacks"
PAGE = 20

# Modrinth's tag slugs -> names shown on the chips (loaders get their own colours, like on the site)
LOADER_COLORS = {"fabric": "#dbb69b", "quilt": "#c796f9", "forge": "#959eef", "neoforge": "#f99e6b"}


def tag_name(slug: str) -> str:
    names = {
        "fabric": "Fabric", "quilt": "Quilt", "forge": "Forge", "neoforge": "NeoForge",
        "adventure": _("Adventure"), "challenging": _("Challenging"), "combat": _("Combat"),
        "kitchen-sink": _("Kitchen sink"), "lightweight": _("Lightweight"), "magic": _("Magic"),
        "multiplayer": _("Multiplayer"), "optimization": _("Optimization"), "quests": _("Quests"),
        "technology": _("Technology"), "utility": _("Utility"), "worldgen": _("World generation"),
        "decoration": _("Decoration"), "economy": _("Economy"), "equipment": _("Equipment"),
        "food": _("Food"), "game-mechanics": _("Game mechanics"), "library": _("Library"),
        "management": _("Management"), "minigame": _("Minigame"), "mobs": _("Mobs"), "social": _("Social"),
        "storage": _("Storage"), "transportation": _("Transportation"), "cursed": _("Cursed"),
        "vanilla-like": _("Vanilla-like"), "exploration": _("Exploration"),
    }
    return names.get(slug, slug.replace("-", " ").capitalize())


def ago(iso: str, now: datetime | None = None) -> str:
    """'3 days ago' style text for an ISO timestamp from Modrinth ('' if it can't be read)."""
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    sec = max(0, ((now or datetime.now(timezone.utc)) - t).total_seconds())
    if sec < 3600:
        return _("just now")
    if sec < 86400:
        return _("{0} h ago").format(int(sec // 3600))
    d = int(sec // 86400)
    if d < 31:
        return _("{0} days ago").format(d)
    if d < 365:
        return _("{0} months ago").format(d // 30)
    return _("{0} years ago").format(d // 365)


class Chip(QWidget):
    """Small rounded tag like Modrinth's category pills."""

    def __init__(self, text: str, color: str = ""):
        super().__init__()
        self.text = text
        self.color = QColor(color) if color else QColor(MUTED)
        self.filled = bool(color)
        f = self.font()
        f.setPointSizeF(8.2)
        f.setBold(self.filled)
        self.setFont(f)
        fm = self.fontMetrics()
        self.setFixedSize(fm.horizontalAdvance(text) + 16, fm.height() + 6)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bg = QColor(self.color)
        bg.setAlpha(46 if self.filled else 22)
        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(self.color if self.filled else QColor(MUTED))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text)


class PackRow(QWidget):
    """One search result laid out like a Modrinth project card: icon, title + author, description, tags,
    and downloads / followers / last update on the right."""

    clicked = pyqtSignal(object)

    def __init__(self, hit: mp.PackHit):
        super().__init__()
        self.hit = hit
        self.selected = False
        self.hv = Hover(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 12, 14, 12)
        h.setSpacing(14)
        h.addWidget(RemoteIcon(hit.icon_url, hit.title, 64, 14, hit.color), 0, Qt.AlignmentFlag.AlignTop)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(6)
        name = ElideLabel(hit.title, "h3")
        name.setStyleSheet(f"font-size:11.5pt; font-weight:800; color:{TEXT};")
        name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        top.addWidget(name, 0, Qt.AlignmentFlag.AlignBottom)
        by = ElideLabel(_("by {0}").format(hit.author), "small")
        by.setStyleSheet(f"color:{MUTED};")
        top.addWidget(by, 1, Qt.AlignmentFlag.AlignBottom)
        mid.addLayout(top)
        desc = hit.description.strip()
        d = wrap_label(desc[:150] + ("…" if len(desc) > 150 else ""))
        d.setToolTip(desc)
        mid.addWidget(d)
        tags = QWidget()
        fl = FlowLayout(tags, 5)
        for c in hit.categories[:6]:
            fl.addWidget(Chip(tag_name(c), LOADER_COLORS.get(c, "")))
        if hit.latest_mc:
            fl.addWidget(Chip(hit.latest_mc, ACCENT))
        if hit.server_side == "unsupported":
            fl.addWidget(Chip(_("Client only"), DANGER))
        mid.addWidget(tags)
        h.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(3)
        right.addStretch(1)
        for txt in (_("⬇ {0} downloads").format(fmt_downloads(hit.downloads)),
                    _("♥ {0} followers").format(fmt_downloads(hit.follows)) if hit.follows else "",
                    _("🕒 Updated {0}").format(ago(hit.updated)) if ago(hit.updated) else ""):
            if txt:
                lb = label(txt, "small")
                lb.setAlignment(Qt.AlignmentFlag.AlignRight)
                right.addWidget(lb)
        right.addStretch(1)
        h.addLayout(right, 0)

    def set_selected(self, on: bool):
        self.selected = on
        self.update()

    def enterEvent(self, e):
        self.hv.to(1)

    def leaveEvent(self, e):
        self.hv.to(0)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hv = self.hv.value
        if self.selected:
            fill = QColor(ACCENT)
            fill.setAlpha(34)
            pen = QPen(QColor(ACCENT), 1.6)
        else:
            fill = QColor(255, 255, 255, int(12 + 12 * hv))
            pen = QPen(QColor(255, 255, 255, int(30 + 40 * hv)), 1)
        p.setBrush(fill)
        p.setPen(pen)
        p.drawRoundedRect(r, 14, 14)



class ModpackPicker(Overlay):
    """Emits ``chosen`` with Pack.to_dict() when the user confirms a pack."""

    max_size = (880, 760)
    chosen = pyqtSignal(dict)

    def __init__(self, win, st):
        super().__init__(win, _("Modpack"))
        self.st = st
        self.pack: mp.Pack | None = None
        self.versions: list[mp.PackVersion] = []
        self.busy = False

        # --- Modrinth search
        self.mr_box = QWidget()
        mv = self._vbox(self.mr_box)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText(_("Search Modrinth modpacks (empty = most popular)"))
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.query, 1)
        self.sort = NoWheelCombo()
        for key, text in (("relevance", _("Relevance")), ("downloads", _("Downloads")),
                          ("follows", _("Follows")), ("updated", _("Recently updated")),
                          ("newest", _("Newest"))):
            self.sort.addItem(text, key)
        self.sort.currentIndexChanged.connect(lambda _i: self.search())
        row.addWidget(self.sort)
        self.spin = Spinner()
        self.spin.hide()
        row.addWidget(self.spin)
        b = Button(_("Search"), "primary")
        b.clicked.connect(self.search)
        row.addWidget(b)
        mv.addLayout(row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.scroll.setMinimumHeight(230)
        inner = QWidget()
        self.rows_lay = QVBoxLayout(inner)
        self.rows_lay.setContentsMargins(0, 0, 6, 0)
        self.rows_lay.setSpacing(8)
        self.rows_lay.addStretch(1)
        self.scroll.setWidget(inner)
        self.scroll.verticalScrollBar().valueChanged.connect(self._maybe_more)
        mv.addWidget(self.scroll, 1)
        self.count_lbl = label("", "small")
        mv.addWidget(self.count_lbl)
        self.rows: list[PackRow] = []
        self.hit: mp.PackHit | None = None
        self.total = 0
        self.more_busy = False
        self.search_id = 0

        vr = QHBoxLayout()
        self.sel_icon = RemoteIcon("", "", 34, 9)
        self.sel_icon.hide()
        vr.addWidget(self.sel_icon)
        vr.addWidget(label(_("Version"), "h3"))
        self.vcombo = NoWheelCombo()
        self.vcombo.setEnabled(False)
        vr.addWidget(self.vcombo, 1)
        self.use_mr = Button(_("Use this version"), "primary")
        self.use_mr.setEnabled(False)
        self.use_mr.clicked.connect(self._load_mr)
        vr.addWidget(self.use_mr)
        mv.addLayout(vr)
        self.body.addWidget(self.mr_box, 1)

        # --- from a file
        frow = QHBoxLayout()
        frow.addWidget(wrap_label(_("Or open a file: Modrinth .mrpack, CurseForge modpack .zip, or a CurseForge "
                                    "server pack .zip."), "small"), 1)
        fb = Button(_("Open file…"))
        fb.clicked.connect(self._open_file)
        frow.addWidget(fb)
        self.body.addLayout(frow)

        # --- what was picked
        irow = QHBoxLayout()
        irow.setSpacing(12)
        self.info_icon = RemoteIcon("", "", 48, 12)
        self.info_icon.hide()
        irow.addWidget(self.info_icon, 0, Qt.AlignmentFlag.AlignTop)
        self.info = wrap_label("", "")
        self.info.setTextFormat(Qt.TextFormat.RichText)
        irow.addWidget(self.info, 1)
        self.body.addLayout(irow)
        self.key_box = QWidget()
        kv = QHBoxLayout(self.key_box)
        kv.setContentsMargins(0, 0, 0, 0)
        kv.addWidget(label(_("CurseForge API key"), "h3"))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(_("Paste your key ($2a$10$…)"))
        self.key.textChanged.connect(self._update_use)
        kv.addWidget(self.key, 1)
        kb = Button(_("Get a free key"))
        kb.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(mp.CF_KEY_PAGE)))
        kv.addWidget(kb)
        self.key_box.hide()
        self.body.addWidget(self.key_box)
        brow = QHBoxLayout()
        brow.addStretch(1)
        self.use = Button(_("Use this modpack"), "primary")
        self.use.setMinimumWidth(170)
        self.use.setEnabled(False)
        self.use.clicked.connect(self._confirm)
        brow.addWidget(self.use)
        self.body.addLayout(brow)

    @staticmethod
    def _vbox(w):
        from PyQt6.QtWidgets import QVBoxLayout
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        return v

    # ---- opening ----
    def open_modrinth(self):
        self.mr_box.show()
        self.key.setText(str(self.st.app.get("curseforge_key", "")))
        self.open_anim()
        if not self.rows:
            self.search()

    def open_file(self):
        self.key.setText(str(self.st.app.get("curseforge_key", "")))
        self.open_anim()
        self._open_file()

    # ---- Modrinth ----
    def _busy(self, on: bool, msg: str = ""):
        self.busy = on
        self.spin.start() if on else self.spin.stop()
        self.spin.setVisible(on)
        if msg:
            self.info.setText(f"<span style='color:{MUTED}'>{msg}</span>")
        elif not on:
            self.info.setText(self._pack_text() if self.pack else "")
        self.info_icon.setVisible(bool(self.pack) and not msg)
        self._update_use()

    def _clear_rows(self):
        for r in self.rows:
            r.setParent(None)
            r.deleteLater()
        self.rows = []

    def _add_rows(self, hits):
        for h in hits:
            row = PackRow(h)
            row.clicked.connect(self._pick_row)
            self.rows_lay.insertWidget(self.rows_lay.count() - 1, row)
            self.rows.append(row)
        self.count_lbl.setText(_("{0} of {1} modpacks").format(len(self.rows), f"{self.total:,}")
                               if self.rows else "")

    def search(self):
        if self.busy:
            return
        q = self.query.text().strip()
        sort = self.sort.currentData()
        self.search_id += 1
        sid = self.search_id
        self._busy(True, _("Searching…"))

        def ok(res):
            hits, total = res
            if sid != self.search_id:
                return
            self._busy(False, "")
            self._clear_rows()
            self.total = total
            self.scroll.verticalScrollBar().setValue(0)
            self._add_rows(hits)
            if not hits:
                self.info.setText(_("No modpacks found."))

        run_async(lambda s: mp.search_modrinth_page(q, PAGE, 0, sort), ok, self._err)

    def _maybe_more(self, v):
        sb = self.scroll.verticalScrollBar()
        if v < sb.maximum() - 60 or self.more_busy or self.busy or len(self.rows) >= self.total:
            return
        self.more_busy = True
        q, sort, sid, off = self.query.text().strip(), self.sort.currentData(), self.search_id, len(self.rows)

        def ok(res):
            self.more_busy = False
            if sid == self.search_id:
                self._add_rows(res[0])

        def err(_m):
            self.more_busy = False

        run_async(lambda s: mp.search_modrinth_page(q, PAGE, off, sort), ok, err)

    def _pick_row(self, row: PackRow):
        if self.busy:
            return
        for r in self.rows:
            r.set_selected(r is row)
        h = self.hit = row.hit
        self.sel_icon.set_url(h.icon_url, h.title, h.color)
        self.sel_icon.show()
        pid = h.project_id
        self.vcombo.clear()
        self.vcombo.setEnabled(False)
        self.use_mr.setEnabled(False)
        self._busy(True, _("Loading versions…"))

        def ok(vs):
            self.pack = None
            self._busy(False, "")
            self.versions = vs
            for v in vs:
                self.vcombo.addItem(v.label)
            self.vcombo.setEnabled(bool(vs))
            self.use_mr.setEnabled(bool(vs))
            if not vs:
                self.info.setText(_("This modpack has no version for a server loader this app supports."))

        run_async(lambda s: mp.modrinth_versions(pid), ok, self._err)

    def _load_mr(self):
        i = self.vcombo.currentIndex()
        if i < 0 or i >= len(self.versions) or self.busy:
            return
        v = self.versions[i]
        hit = self.hit
        self._busy(True, _("Downloading the modpack file…"))

        def read(s):
            pack = mp.read_pack(mp.download_mrpack(v, CACHE))
            if hit:
                pack.icon_url, pack.icon_color = hit.icon_url, hit.color
                pack.name = pack.name or hit.title
            return pack

        run_async(read, self._got_pack, self._err)

    # ---- file ----
    def _open_file(self):
        f, _x = QFileDialog.getOpenFileName(self, _("Open modpack"), str(Path.home() / "Downloads"),
                                            _("Modpacks (*.mrpack *.zip)"))
        if not f:
            return
        self._busy(True, _("Reading {0}…").format(Path(f).name))
        run_async(lambda s: mp.read_pack(f), self._got_pack, self._err)

    # ---- result ----
    def _got_pack(self, pack: mp.Pack):
        self.pack = pack
        self.info_icon.set_url(pack.icon_url, pack.name, pack.icon_color)
        self.info_icon.show()
        self._busy(False, "")
        self.key_box.setVisible(pack.kind == "curseforge")
        self._update_use()

    def _pack_text(self) -> str:
        pack = self.pack
        prov = PROVIDERS.get(pack.server)
        loader = f"{prov.name if prov else pack.server} {pack.build or _('(recommended build)')}"
        kind = {"modrinth": "Modrinth", "curseforge": "CurseForge", "serverpack": _("CurseForge server pack")}[pack.kind]
        txt = (f"<b>{pack.name}</b> {pack.version}  <span style='color:{MUTED}'>· {kind}</span><br>"
               + _("Minecraft {0} · {1} · {2}").format(pack.mc, loader, pack.summary))
        if pack.kind == "curseforge":
            txt += "<br><span style='color:{0}'>{1}</span>".format(WARN, _(
                "CurseForge modpacks need an API key to download the mods (free). Mods whose authors block "
                "other downloaders are listed in MANUAL_DOWNLOADS.txt to get by hand. If the pack has a "
                "server pack, that one needs no key."))
        if not prov:
            txt += f"<br><span style='color:{DANGER}'>" + _("This loader is not supported.") + "</span>"
        return txt

    def _err(self, msg):
        self._busy(False, "")
        self.info_icon.hide()
        self.info.setText(f"<span style='color:{DANGER}'>{msg}</span>")

    def _update_use(self):
        ok = bool(self.pack and self.pack.server in PROVIDERS and not self.busy)
        if ok and self.pack.kind == "curseforge":
            ok = bool(self.key.text().strip())
        self.use.setEnabled(ok)

    def _confirm(self):
        if not self.pack:
            return
        if self.pack.kind == "curseforge":
            self.st.app["curseforge_key"] = self.key.text().strip()
            self.st.save()
        self.chosen.emit(self.pack.to_dict())
        self.close_anim()

