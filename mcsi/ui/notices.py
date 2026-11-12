"""Startup notices (new version, new event loader), event loader cards and the UFO day stunt."""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                         QRadialGradient)
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QWidget

from .. import __version__
from ..core import events as ev
from ..core.update import Release
from ..i18n import _
from .overlay import Overlay
from .widgets import Button, Card, label, wrap_label


class BigIcon(QWidget):
    """Large emoji on a glowing disc in the event's color (shown instead of a picture)."""

    def __init__(self, icon: str, accent: str, size: int = 96):
        super().__init__()
        self.icon, self.accent = icon, QColor(accent)
        self.setFixedSize(size, size)
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def _tick(self):
        self.t += 0.033
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        g = QRadialGradient(r.center(), r.width() / 2)
        c = QColor(self.accent)
        c.setAlpha(150)
        g.setColorAt(0, c)
        c2 = QColor(self.accent)
        c2.setAlpha(0)
        g.setColorAt(1, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(r)
        f = QFont(self.font())
        f.setPointSizeF(self.width() * 0.34)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.translate(r.center())
        p.rotate(math.sin(self.t * 2.2) * 7)
        p.scale(1 + 0.04 * math.sin(self.t * 4.4), 1 + 0.04 * math.sin(self.t * 4.4))
        p.drawText(QRectF(-r.width() / 2, -r.height() / 2, r.width(), r.height()), Qt.AlignmentFlag.AlignCenter,
                   self.icon)


class SideOverlay(Overlay):
    """Overlay whose panel sits on the left with a light scrim, so the 3D animation on the right stays visible."""

    max_size = (470, 400)

    def __init__(self, win, title: str):
        super().__init__(win, title)
        self.back.strength = 90

    def panel_rect(self, w, h, v):
        return 60 - int((1 - v) * 30), (self.height() - h) // 2


# ------------------------------------------------------------------ new version
class UpdateNotice(Overlay):
    max_size = (560, 430)

    def __init__(self, win, st):
        super().__init__(win, _("Update available"))
        self.st = st
        self.rel: Release | None = None
        self.close_btn.setText(_("Later"))
        self.head = wrap_label("", "")
        self.head.setTextFormat(Qt.TextFormat.RichText)
        self.body.addWidget(self.head)
        self.notes = wrap_label("", "muted")
        self.notes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.body.addWidget(self.notes, 1)
        row = QHBoxLayout()
        self.skip = Button(_("Skip this version"))
        self.skip.clicked.connect(self._skip)
        row.addWidget(self.skip)
        row.addStretch(1)
        self.dl = Button(_("Download"), "primary")
        self.dl.clicked.connect(self._download)
        row.addWidget(self.dl)
        self.body.addLayout(row)

    def show_release(self, rel: Release):
        self.rel = rel
        self.head.setText(_("<b>Version {0}</b> is out. You have {1}.").format(rel.version, __version__))
        lines = [ln.strip() for ln in rel.notes.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
        text = "\n".join(lines[:10]) + ("\n…" if len(lines) > 10 else "")
        self.notes.setText(text.replace("**", "") or _("See the release page for what's new."))
        self.open_anim()

    def _download(self):
        if self.rel:
            QDesktopServices.openUrl(QUrl(self.rel.url))
        self.close_anim()

    def _skip(self):
        if self.rel:
            self.st.app["skip_version"] = self.rel.version
            self.st.save()
        self.close_anim()


# ------------------------------------------------------------------ new event loader
class EventNotice(SideOverlay):
    try_it = pyqtSignal(str)

    def __init__(self, win):
        super().__init__(win, _("New loader added!"))
        self.close_btn.setText(_("Later"))
        self.ev: ev.Event | None = None
        self.icon_box = QHBoxLayout()
        self.body.addLayout(self.icon_box)
        self.head = wrap_label("", "h3")
        self.body.addWidget(self.head)
        self.desc = wrap_label("", "muted")
        self.body.addWidget(self.desc)
        self.when = label("", "small")
        self.body.addWidget(self.when)
        self.body.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        go = Button(_("Try it now"), "primary")
        go.clicked.connect(self._go)
        row.addWidget(go)
        self.body.addLayout(row)
        self.big = None

    def show_event(self, e: ev.Event):
        self.ev = e
        if self.big:
            self.big.deleteLater()
        self.big = BigIcon(e.icon, e.accent)
        self.icon_box.addWidget(self.big)
        self.icon_box.addStretch(1)
        self.head.setText(e.headline or _("{0} has arrived!").format(e.name))
        self.desc.setText(e.desc)
        self.when.setText(_("Available {0} only. Find it at the top of 'Server type'.").format(e.window_text()))
        self.open_anim()

    def _go(self):
        if self.ev:
            self.try_it.emit(self.ev.key)
        self.close_anim()


def event_card(e: ev.Event, new: bool) -> Card:
    return Card(e.name, e.desc, e.accent, _("NEW") if new else e.window_text(), e.icon, height=112)


# ------------------------------------------------------------------ World UFO day: the UFO steals the menu
class UfoHeist(QWidget):
    """A UFO flies in, beams up the visible menu items, chews, spits them back and leaves.

    The real widgets are only made invisible with an opacity effect while their snapshots fly, and are
    always restored at the end (also if anything goes wrong).
    """

    DURATION = 5200

    def __init__(self, win, targets: list[QWidget]):
        super().__init__(win)
        self.win = win
        self.setGeometry(win.rect())
        self.items = []
        for w in targets:
            try:
                if not w.isVisible() or w.width() < 4:
                    continue
                pm = w.grab()
                tl = w.mapTo(win, w.rect().topLeft())
                self.items.append({"w": w, "pm": pm, "r": QRectF(tl.x(), tl.y(), w.width(), w.height()),
                                   "spin": random.choice((-1, 1)) * random.uniform(120, 300)})
            except RuntimeError:
                continue
        self.items.sort(key=lambda it: (it["r"].top(), it["r"].left()))
        self.t = 0.0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(self.DURATION)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.valueChanged.connect(self._t)
        self.anim.finished.connect(self.finish)
        self._done = False

    def start(self):
        for it in self.items:
            eff = QGraphicsOpacityEffect(it["w"])
            eff.setOpacity(0.0)
            it["w"].setGraphicsEffect(eff)
        self.show()
        self.raise_()
        self.anim.start()
        QTimer.singleShot(self.DURATION + 2500, self.finish)      # safety net

    def finish(self):
        if self._done:
            return
        self._done = True
        for it in self.items:
            try:
                it["w"].setGraphicsEffect(None)
                it["w"].update()
            except RuntimeError:
                pass
        self.hide()
        self.deleteLater()

    def mousePressEvent(self, e):          # swallow clicks while the menu is "gone"
        e.accept()

    def _t(self, v):
        self.t = float(v)
        self.update()

    # ---- timeline helpers
    @staticmethod
    def _seg(t, a, b):
        return max(0.0, min(1.0, (t - a) / (b - a)))

    def _ufo_pos(self, t) -> QPointF:
        hx, hy = self.width() * 0.5, 92.0
        if t < 0.12:
            k = 1 - (1 - t / 0.12) ** 3
            return QPointF(-160 + (hx + 160) * k, -80 + (hy + 80) * k)
        if t > 0.84:
            k = ((t - 0.84) / 0.16) ** 2
            return QPointF(hx + (self.width() + 220 - hx) * k, hy - 180 * k)
        wob = 10 if 0.55 < t < 0.62 else 3
        return QPointF(hx + math.sin(t * 60) * wob, hy + math.sin(t * 23) * 4)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        t = self.t
        u = self._ufo_pos(t)
        n = max(1, len(self.items))
        stag = min(0.03, 0.3 / n)
        # tractor beam
        beam = self._seg(t, 0.13, 0.2) * (1 - self._seg(t, 0.74, 0.8))
        if beam > 0:
            path = QPainterPath(QPointF(u.x() - 40, u.y() + 18))
            path.lineTo(u.x() + 40, u.y() + 18)
            path.lineTo(u.x() + self.width() * 0.48, self.height())
            path.lineTo(u.x() - self.width() * 0.48, self.height())
            path.closeSubpath()
            g = QLinearGradient(0, u.y(), 0, self.height())
            g.setColorAt(0, QColor(163, 230, 53, int(150 * beam)))
            g.setColorAt(1, QColor(163, 230, 53, int(10 * beam)))
            p.fillPath(path, QBrush(g))
            p.setPen(QPen(QColor(220, 255, 160, int(70 * beam)), 1.5))
            for i in range(14):
                yy = (i / 14 + t * 3) % 1
                y = u.y() + 18 + (self.height() - u.y()) * yy
                half = 40 + (self.width() * 0.48 - 40) * yy
                p.drawLine(QPointF(u.x() - half * 0.9, y), QPointF(u.x() + half * 0.9, y))
        # menu items
        for i, it in enumerate(self.items):
            take = self._seg(t, 0.17 + i * stag, 0.31 + i * stag) ** 2
            give_raw = self._seg(t, 0.62 + i * stag * 0.6, 0.76 + i * stag * 0.6)
            c1, c3 = 1.70158, 2.70158
            give = 1 + c3 * (give_raw - 1) ** 3 + c1 * (give_raw - 1) ** 2 if give_raw > 0 else 0.0
            k = take * (1 - give) if give_raw > 0 else take
            if take >= 1 and give_raw <= 0:
                continue                                   # inside the UFO
            r = it["r"]
            home = r.center()
            pos = QPointF(home.x() + (u.x() - home.x()) * k, home.y() + (u.y() - home.y()) * k)
            s = max(0.05, 1 - 0.95 * k)
            p.save()
            p.translate(pos)
            p.rotate(it["spin"] * k)
            p.scale(s, s)
            p.setOpacity(max(0.0, min(1.0, 1.15 - k * 0.6)))
            p.drawPixmap(QPointF(-r.width() / 2, -r.height() / 2), it["pm"])
            p.restore()
        p.setOpacity(1.0)
        self._draw_ufo(p, u, t)
        f = QFont(self.font())
        f.setPointSizeF(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#fde047"))
        if 0.55 < t < 0.62:
            p.drawText(QPointF(u.x() + 96, u.y() + 6), _("*munch munch*"))
        elif 0.62 < t < 0.72:
            p.drawText(QPointF(u.x() + 96, u.y() + 6), _("*ptooey!*"))

    def _draw_ufo(self, p: QPainter, u: QPointF, t: float):
        tilt = math.sin(t * 9) * 6 if 0.12 < t < 0.84 else (-12 if t <= 0.12 else 14)
        p.save()
        p.translate(u)
        p.rotate(tilt)
        dome = QRectF(-34, -40, 68, 52)
        g = QLinearGradient(0, -40, 0, 10)
        g.setColorAt(0, QColor(186, 230, 253, 230))
        g.setColorAt(1, QColor(56, 189, 248, 120))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
        p.drawEllipse(dome)
        # little alien
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#a3e635"))
        p.drawEllipse(QRectF(-10, -26, 20, 22))
        p.setBrush(QColor("#0b1020"))
        p.drawEllipse(QRectF(-7, -20, 6, 8))
        p.drawEllipse(QRectF(1, -20, 6, 8))
        disc = QRectF(-90, -8, 180, 34)
        g2 = QLinearGradient(0, -8, 0, 26)
        g2.setColorAt(0, QColor("#e2e8f0"))
        g2.setColorAt(0.5, QColor("#94a3b8"))
        g2.setColorAt(1, QColor("#334155"))
        p.setBrush(QBrush(g2))
        p.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
        p.drawEllipse(disc)
        for i in range(7):
            a = i / 6
            x = -70 + 140 * a
            on = int(t * 24 + i) % 3 == 0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#fde047") if on else QColor("#f472b6"))
            p.drawEllipse(QPointF(x, 10 - abs(a - 0.5) * 6), 5, 5)
        p.restore()
