"""Picture guide for manual port forwarding.

Every step is drawn by the app (no screenshots of real router firmware, which looks different on every
model): a generic browser / router admin page, filled in with this PC's real values (router address,
local IP, ports) and an animated pointer showing where to click.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from ..i18n import _
from .widgets import ACCENT

VW, VH = 640.0, 260.0          # virtual canvas, scaled to the widget

STEP_COUNT = 12

PAGE = QColor("#f4f6fb")
PAGE_LINE = QColor("#d5dae6")
INK = QColor("#1f2937")
INK2 = QColor("#6b7280")
SIDEBAR = QColor("#e7ebf3")


class PortPicture(QWidget):
    def __init__(self):
        super().__init__()
        self.step = 0
        self.gw = "192.168.0.1"
        self.lip = "192.168.0.10"
        self.pub = ""
        self.port = 25565
        self.rules: list = [(25565, "TCP", "")]
        self.t = 0.0
        self.setMinimumHeight(220)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    # ---- API ----
    def set_values(self, gw: str, lip: str, pub: str, port: int, rules: list) -> None:
        self.gw, self.lip, self.pub, self.port, self.rules = gw, lip, pub, port, list(rules) or [(port, "TCP", "")]
        self.update()

    def set_step(self, i: int) -> None:
        self.step = max(0, min(STEP_COUNT - 1, i))
        self.t = 0.0
        self.update()

    def showEvent(self, e):
        self.timer.start(33)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _tick(self):
        self.t += 0.033
        self.update()

    def heightForWidth(self, w):
        return int(w * VH / VW)

    def hasHeightForWidth(self):
        return True

    # ---- drawing helpers ----
    def _font(self, size, bold=False):
        f = QFont(self.font())
        f.setPointSizeF(size)
        f.setBold(bold)
        return f

    def _text(self, p, x, y, s, size=9.0, color=INK, bold=False, align=Qt.AlignmentFlag.AlignLeft, w=400.0):
        p.setFont(self._font(size, bold))
        p.setPen(color)
        p.drawText(QRectF(x, y, w, size * 2.2), align | Qt.AlignmentFlag.AlignVCenter, s)

    def _pulse(self, p, r: QRectF, radius=6.0):
        a = 0.55 + 0.45 * math.sin(self.t * 5)
        c = QColor(ACCENT)
        c.setAlphaF(a)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(c, 2.6))
        p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), radius + 3, radius + 3)

    def _cursor(self, p, x, y, click=True):
        bob = math.sin(self.t * 3) * 3
        x, y = x + bob, y + bob
        if click and (self.t % 1.6) < 0.25:
            c = QColor(ACCENT)
            c.setAlphaF(0.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            k = (self.t % 1.6) / 0.25
            p.drawEllipse(QPointF(x, y), 6 + 10 * k, 6 + 10 * k)
        poly = QPolygonF([QPointF(x, y), QPointF(x, y + 18), QPointF(x + 5, y + 14), QPointF(x + 8.5, y + 21),
                          QPointF(x + 11, y + 20), QPointF(x + 7.5, y + 13), QPointF(x + 13, y + 13)])
        p.setPen(QPen(QColor("black"), 1.2))
        p.setBrush(QColor("white"))
        p.drawPolygon(poly)

    def _browser(self, p, url: str) -> QRectF:
        """A generic browser window; returns the page area."""
        frame = QRectF(20, 8, 600, 244)
        p.setPen(QPen(QColor(0, 0, 0, 60), 1))
        p.setBrush(QColor("#dfe3ec"))
        p.drawRoundedRect(frame, 10, 10)
        for i, c in enumerate(("#f87171", "#fbbf24", "#34d399")):
            p.setBrush(QColor(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(36 + i * 14, 22), 4.5, 4.5)
        bar = QRectF(90, 13, 420, 20)
        p.setBrush(QColor("white"))
        p.setPen(QPen(PAGE_LINE, 1))
        p.drawRoundedRect(bar, 10, 10)
        self._text(p, 102, 13, url, 8.5, INK, w=400)
        page = QRectF(24, 38, 592, 210)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(PAGE)
        p.drawRoundedRect(page, 6, 6)
        return page

    def _field(self, p, x, y, w, label_, value, hi=False, h=22.0):
        self._text(p, x, y - 16, label_, 7.5, INK2)
        r = QRectF(x, y + 2, w, h)
        p.setPen(QPen(QColor(ACCENT) if hi else PAGE_LINE, 1.4 if hi else 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(r, 4, 4)
        self._text(p, x + 7, y + 2 + (h - 19.8) / 2, value, 8.5, INK, bold=hi, w=w - 10)
        return r

    def _button(self, p, r: QRectF, text, primary=True):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT) if primary else QColor("#cfd5e2"))
        p.drawRoundedRect(r, 5, 5)
        self._text(p, r.x(), r.y() + (r.height() - 19.8) / 2, text, 8.5, QColor("#06101a") if primary else INK,
                   bold=True, align=Qt.AlignmentFlag.AlignHCenter, w=r.width())

    def _sidebar(self, p, page: QRectF, hi: int) -> list:
        side = QRectF(page.x(), page.y(), 150, page.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(SIDEBAR)
        p.drawRoundedRect(side, 6, 6)
        items = [_("Status"), _("Wireless"), _("DHCP / LAN"), _("Port forwarding"), _("Firewall"), _("System")]
        rects = []
        for i, s in enumerate(items):
            r = QRectF(side.x() + 8, side.y() + 12 + i * 30, side.width() - 16, 24)
            if i == hi:
                p.setBrush(QColor("white"))
                p.drawRoundedRect(r, 5, 5)
            self._text(p, r.x() + 10, r.y() + 2, s, 8.5, INK if i == hi else INK2, bold=(i == hi), w=r.width())
            rects.append(r)
        return rects

    # ---- the steps ----
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        s = min(self.width() / VW, self.height() / VH)
        p.translate((self.width() - VW * s) / 2, (self.height() - VH * s) / 2)
        p.scale(s, s)
        [self._s0, self._s1, self._s2, self._s3, self._s4, self._s5, self._s6, self._s7, self._s8, self._s9,
         self._s10, self._s11][self.step](p)

    def _s0(self, p):
        """How it works: friend -> internet -> router -> this PC."""
        mid = 120
        nodes = [(80, _("Friend"), "🎮", ""), (250, _("Internet"), "🌐", self.pub or _("your public IP")),
                 (410, _("Router"), "📶", self.gw), (565, _("This PC"), "💻", self.lip)]
        for i, (x, name, icon, sub) in enumerate(nodes):
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawEllipse(QPointF(x, mid), 40, 40)
            p.setFont(self._font(22))
            p.setPen(QColor("white"))
            p.drawText(QRectF(x - 40, mid - 40, 80, 80), Qt.AlignmentFlag.AlignCenter, icon)
            self._text(p, x - 80, mid + 46, name, 9.5, QColor("white"), True, Qt.AlignmentFlag.AlignHCenter, 160)
            if sub:
                self._text(p, x - 90, mid + 66, sub, 8, QColor("#9aa4bf"), False, Qt.AlignmentFlag.AlignHCenter, 180)
        # packets travelling right
        for i in range(3):
            x0, x1 = nodes[i][0] + 46, nodes[i + 1][0] - 46
            p.setPen(QPen(QColor(255, 255, 255, 70), 2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x0, mid), QPointF(x1, mid))
            k = (self.t * 0.6 + i * 0.33) % 1
            c = QColor(ACCENT)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(x0 + (x1 - x0) * k, mid), 5, 5)
        # the rule the router needs
        r = QRectF(330, 18, 160, 40)
        p.setPen(QPen(QColor(ACCENT), 1.5))
        p.setBrush(QColor(45, 212, 191, 30))
        p.drawRoundedRect(r, 8, 8)
        self._text(p, r.x(), r.y() + 1, _("port {0} → {1}").format(self.port, self.lip), 8.5, QColor("white"), True,
                   Qt.AlignmentFlag.AlignHCenter, r.width())
        self._text(p, r.x(), r.y() + 18, _("this is the rule you add"), 7.5, QColor("#9aa4bf"), False,
                   Qt.AlignmentFlag.AlignHCenter, r.width())

    def _s1(self, p):
        """Open the router page and log in."""
        page = self._browser(p, f"http://{self.gw}")
        self._pulse(p, QRectF(90, 13, 160, 20), 10)
        box = QRectF(page.center().x() - 120, page.y() + 30, 240, 150)
        p.setPen(QPen(PAGE_LINE, 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(box, 8, 8)
        self._text(p, box.x(), box.y() + 8, _("Router login"), 10, INK, True, Qt.AlignmentFlag.AlignHCenter, box.width())
        self._field(p, box.x() + 20, box.y() + 56, 200, _("ID"), "admin")
        self._field(p, box.x() + 20, box.y() + 100, 200, _("Password"), "●●●●●●●●")
        # the sticker on the router
        st = QRectF(470, 160, 130, 64)
        p.setPen(QPen(QColor("#a3a3a3"), 1))
        p.setBrush(QColor("#fff7cc"))
        p.drawRoundedRect(st, 4, 4)
        self._text(p, st.x() + 8, st.y() + 4, _("Sticker on the router"), 7.5, INK2, True, w=st.width())
        self._text(p, st.x() + 8, st.y() + 22, "ID: admin", 8, INK, w=st.width())
        self._text(p, st.x() + 8, st.y() + 38, "PW: ********", 8, INK, w=st.width())
        self._cursor(p, 240, 26)

    def _s2(self, p):
        """Find the port forwarding menu."""
        page = self._browser(p, f"http://{self.gw}")
        rects = self._sidebar(p, page, 3)
        self._pulse(p, rects[3])
        self._text(p, 200, page.y() + 14, _("Port forwarding"), 12, INK, True)
        self._text(p, 200, page.y() + 40, _("Also called: Virtual Server · NAT · Port Mapping · Port Triggering"),
                   8, INK2, w=400)
        for i in range(3):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e5e9f1"))
            p.drawRoundedRect(QRectF(200, page.y() + 80 + i * 32, 390, 22), 4, 4)
        self._cursor(p, rects[3].right() - 30, rects[3].center().y())

    def _s3(self, p):
        """Reserve this PC's IP (DHCP reservation)."""
        page = self._browser(p, f"http://{self.gw}")
        self._sidebar(p, page, 2)
        self._text(p, 200, page.y() + 14, _("DHCP reservation"), 12, INK, True)
        heads = [_("Device"), _("MAC address"), _("IP address")]
        xs = [200, 320, 470]
        for x, h in zip(xs, heads):
            self._text(p, x, page.y() + 48, h, 8, INK2, True)
        rows = [("THIS-PC", "AA:BB:CC:12:34:56", self.lip, True), ("phone", "11:22:33:44:55:66", "…", False)]
        for i, (a, b, c, hi) in enumerate(rows):
            y = page.y() + 72 + i * 30
            r = QRectF(196, y - 2, 400, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("white") if hi else QColor("#eef1f6"))
            p.drawRoundedRect(r, 4, 4)
            for x, v in zip(xs, (a, b, c)):
                self._text(p, x + 4, y + 1, v, 8.5, INK, bold=hi and x == 470)
            if hi:
                self._pulse(p, QRectF(466, y - 1, 126, 24), 4)
        add = QRectF(496, page.y() + 160, 100, 26)
        self._button(p, add, _("Reserve"))
        self._cursor(p, add.center().x(), add.center().y())

    def _s4(self, p):
        """Add the port forwarding rule(s), filled in with the real values."""
        page = self._browser(p, f"http://{self.gw}")
        self._sidebar(p, page, 3)
        self._text(p, 200, page.y() + 8, _("Add a rule"), 11, INK, True)
        port, proto = self.rules[0][0], self.rules[0][1]
        y = page.y() + 52
        self._field(p, 200, y, 120, _("Name"), "Minecraft")
        self._field(p, 330, y, 120, _("Protocol"), proto, hi=True)
        self._field(p, 460, y, 130, _("External port"), str(port), hi=True)
        y += 48
        self._field(p, 200, y, 250, _("Internal IP (this PC)"), self.lip, hi=True)
        self._field(p, 460, y, 130, _("Internal port"), str(port), hi=True)
        if len(self.rules) > 1:
            more = ", ".join(f"{po}/{pr}" for po, pr, _w in self.rules[1:])
            self._text(p, 200, y + 30, _("Add one more rule each: {0}").format(more), 8, QColor("#b45309"), True, w=400)
        save = QRectF(490, page.y() + 172, 100, 26)
        self._button(p, save, _("Add / Save"))
        self._pulse(p, save, 5)
        self._cursor(p, save.center().x(), save.center().y())

    # ---- Windows Defender Firewall: a new inbound rule, step by step ----
    def _win(self, p, title: str, rect=QRectF(30, 10, 580, 240)) -> QRectF:
        """A generic Windows-style window; returns the content area."""
        p.setPen(QPen(QColor(0, 0, 0, 70), 1))
        p.setBrush(QColor("#f3f3f3"))
        p.drawRoundedRect(rect, 7, 7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e6e6e6"))
        p.drawRoundedRect(QRectF(rect.x(), rect.y(), rect.width(), 26), 7, 7)
        p.drawRect(QRectF(rect.x(), rect.y() + 14, rect.width(), 12))
        self._text(p, rect.x() + 12, rect.y() + 3, "🛡 " + title, 8.5, INK, w=rect.width() - 100)
        for i, ch in enumerate(("—", "☐", "✕")):
            self._text(p, rect.right() - 84 + i * 28, rect.y() + 3, ch, 8.5, INK2, w=20)
        return QRectF(rect.x() + 1, rect.y() + 27, rect.width() - 2, rect.height() - 28)

    def _wizard(self, p, cur: int) -> QRectF:
        """The New Inbound Rule Wizard frame with its step list; returns the right-hand area."""
        c = self._win(p, _("New Inbound Rule Wizard"))
        steps = [_("Rule Type"), _("Protocol and Ports"), _("Action"), _("Profile"), _("Name")]
        self._text(p, c.x() + 14, c.y() + 6, _("Steps:"), 8, INK, True, w=140)
        for i, st in enumerate(steps):
            col = INK if i == cur else INK2
            self._text(p, c.x() + 14, c.y() + 26 + i * 20, ("● " if i == cur else "○ ") + st, 8, col, i == cur, w=150)
        p.setPen(QPen(QColor("#d0d0d0"), 1))
        p.drawLine(QPointF(c.x() + 170, c.y() + 6), QPointF(c.x() + 170, c.bottom() - 40))
        self._button(p, QRectF(c.right() - 196, c.bottom() - 32, 86, 24), _("< Back"), primary=False)
        return QRectF(c.x() + 186, c.y() + 6, c.width() - 200, c.height() - 48)

    def _radio(self, p, x, y, text, on, hi=False):
        p.setPen(QPen(QColor(ACCENT) if on else QColor("#8a8a8a"), 1.4))
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(x + 6, y + 10), 6, 6)
        if on:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(QPointF(x + 6, y + 10), 3.2, 3.2)
        self._text(p, x + 18, y, text, 8.5, INK, on, w=300)
        if hi:
            self._pulse(p, QRectF(x - 2, y + 1, 150, 18), 4)

    def _check(self, p, x, y, text, on=True):
        p.setPen(QPen(QColor(ACCENT) if on else QColor("#8a8a8a"), 1.4))
        p.setBrush(QColor(ACCENT) if on else QColor("white"))
        p.drawRoundedRect(QRectF(x, y + 4, 12, 12), 2, 2)
        if on:
            self._text(p, x + 1, y - 1, "✓", 8, QColor("#06101a"), True, w=14)
        self._text(p, x + 18, y, text, 8.5, INK, w=320)

    def _next(self, p, area: QRectF, text=None) -> QRectF:
        r = QRectF(area.right() - 96, area.bottom() + 10, 96, 24)
        self._button(p, r, text or _("Next >"))
        return r

    def _s5(self, p):
        """Control Panel -> Windows Defender Firewall -> Advanced settings."""
        c = self._win(p, _("Windows Defender Firewall"))
        self._text(p, c.x() + 14, c.y() + 4, _("Control Panel › System and Security › Windows Defender Firewall"),
                   8, INK2, w=540)
        links = [_("Allow an app or feature through Windows Defender Firewall"), _("Change notification settings"),
                 _("Turn Windows Defender Firewall on or off"), _("Restore defaults"), _("Advanced settings")]
        for i, s in enumerate(links):
            y = c.y() + 34 + i * 26
            self._text(p, c.x() + 18, y, s, 8.5, QColor("#1d4ed8") if i == 4 else INK2, i == 4, w=380)
        hi = QRectF(c.x() + 14, c.y() + 34 + 4 * 26 + 1, 120, 18)
        self._pulse(p, hi, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e8f5e9"))
        p.drawRoundedRect(QRectF(c.x() + 400, c.y() + 40, 160, 90), 6, 6)
        self._text(p, c.x() + 410, c.y() + 46, "🛡 " + _("Firewall is on"), 8.5, QColor("#166534"), True, w=150)
        self._text(p, c.x() + 410, c.y() + 70, _("Private networks"), 8, INK2, w=150)
        self._text(p, c.x() + 410, c.y() + 90, _("Public networks"), 8, INK2, w=150)
        self._cursor(p, hi.right() - 10, hi.center().y())

    def _s6(self, p):
        """Advanced Security: Inbound Rules -> New Rule..."""
        c = self._win(p, _("Windows Defender Firewall with Advanced Security"))
        tree = [_("Inbound Rules"), _("Outbound Rules"), _("Connection Security Rules"), _("Monitoring")]
        for i, s in enumerate(tree):
            r = QRectF(c.x() + 10, c.y() + 10 + i * 24, 170, 20)
            if i == 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#dbeafe"))
                p.drawRoundedRect(r, 3, 3)
            self._text(p, r.x() + 8, r.y(), s, 8.5, INK, i == 0, w=165)
        for i in range(5):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e9e9e9") if i % 2 else QColor("#f8f8f8"))
            p.drawRect(QRectF(c.x() + 190, c.y() + 10 + i * 22, 230, 20))
        act = QRectF(c.x() + 430, c.y() + 6, 140, c.height() - 12)
        p.setBrush(QColor("#ececec"))
        p.drawRoundedRect(act, 4, 4)
        self._text(p, act.x() + 8, act.y() + 4, _("Actions"), 8.5, INK, True, w=130)
        new = QRectF(act.x() + 6, act.y() + 30, act.width() - 12, 22)
        self._text(p, new.x() + 6, new.y(), _("New Rule..."), 8.5, QColor("#1d4ed8"), True, w=120)
        self._text(p, act.x() + 12, act.y() + 58, _("Filter by Profile"), 8, INK2, w=120)
        self._pulse(p, QRectF(c.x() + 10, c.y() + 10, 170, 20), 3)
        self._pulse(p, new, 4)
        self._cursor(p, new.center().x() + 20, new.center().y())

    def _s7(self, p):
        """Rule type: Port."""
        a = self._wizard(p, 0)
        self._text(p, a.x(), a.y(), _("What type of rule would you like to create?"), 9, INK, True, w=a.width())
        for i, s in enumerate((_("Program"), _("Port"), _("Predefined"), _("Custom"))):
            self._radio(p, a.x() + 10, a.y() + 34 + i * 28, s, i == 1, hi=(i == 1))
        n = self._next(p, a)
        self._cursor(p, a.x() + 60, a.y() + 34 + 28 + 10)
        del n

    def _s8(self, p):
        """Protocol and ports: TCP + the port."""
        a = self._wizard(p, 1)
        port, proto = self.rules[0][0], self.rules[0][1]
        self._text(p, a.x(), a.y(), _("Does this rule apply to TCP or UDP?"), 9, INK, True, w=a.width())
        self._radio(p, a.x() + 10, a.y() + 26, "TCP", proto == "TCP", hi=proto == "TCP")
        self._radio(p, a.x() + 10, a.y() + 50, "UDP", proto == "UDP", hi=proto == "UDP")
        self._text(p, a.x(), a.y() + 84, _("Does this rule apply to all local ports or specific local ports?"), 8.5,
                   INK, w=a.width())
        self._radio(p, a.x() + 10, a.y() + 106, _("All local ports"), False)
        self._radio(p, a.x() + 10, a.y() + 128, _("Specific local ports:"), True)
        f = self._field(p, a.x() + 190, a.y() + 128, 120, "", str(port), hi=True, h=20)
        self._pulse(p, f, 4)
        if len(self.rules) > 1:
            more = ", ".join(f"{po}/{pr}" for po, pr, _w in self.rules[1:])
            self._text(p, a.x(), a.y() + 156, _("Make one more rule each for: {0}").format(more), 8,
                       QColor("#b45309"), True, w=a.width())
        self._next(p, a)
        self._cursor(p, f.right() - 20, f.center().y())

    def _s9(self, p):
        """Action: allow the connection."""
        a = self._wizard(p, 2)
        self._text(p, a.x(), a.y(), _("What action should be taken when a connection matches?"), 9, INK, True,
                   w=a.width())
        self._radio(p, a.x() + 10, a.y() + 30, _("Allow the connection"), True, hi=True)
        self._radio(p, a.x() + 10, a.y() + 58, _("Allow the connection if it is secure"), False)
        self._radio(p, a.x() + 10, a.y() + 86, _("Block the connection"), False)
        r = self._next(p, a)
        self._cursor(p, r.center().x(), r.center().y())

    def _s10(self, p):
        """Profile + name, then Finish."""
        a = self._wizard(p, 4)
        port, proto = self.rules[0][0], self.rules[0][1]
        self._text(p, a.x(), a.y(), _("Profile: leave all three checked"), 9, INK, True, w=a.width())
        for i, s in enumerate((_("Domain"), _("Private"), _("Public"))):
            self._check(p, a.x() + 10 + i * 110, a.y() + 24, s)
        f = self._field(p, a.x(), a.y() + 82, a.width() - 10, _("Name"), f"Minecraft {proto} {port}", hi=True)
        self._pulse(p, f, 4)
        r = self._next(p, a, _("Finish"))
        self._pulse(p, r, 5)
        self._cursor(p, r.center().x(), r.center().y())

    def _s11(self, p):
        """Test from outside: a check page reports the server as online."""
        addr = (self.pub or _("your public IP")) + ("" if self.port == 25565 else f":{self.port}")
        page = self._browser(p, "https://mcsrvstat.us/server/" + (self.pub or "…"))
        card = QRectF(page.x() + 60, page.y() + 30, 470, 120)
        p.setPen(QPen(PAGE_LINE, 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(card, 8, 8)
        ok = (self.t % 3) > 0.8
        dot = QColor("#22c55e") if ok else QColor("#a3a3a3")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dot)
        p.drawEllipse(QPointF(card.x() + 30, card.y() + 34), 9, 9)
        self._text(p, card.x() + 50, card.y() + 22, _("Online") if ok else _("Checking…"), 12, INK, True)
        self._text(p, card.x() + 50, card.y() + 50, addr, 10, INK2, w=400)
        self._text(p, card.x() + 50, card.y() + 76, _("Friends can now join this address."), 8.5, INK2, w=400)
        path = QPainterPath()
        path.addRoundedRect(QRectF(page.x() + 60, page.y() + 162, 470, 30), 6, 6)
        p.fillPath(path, QBrush(QColor("#fff7cc")))
        self._text(p, page.x() + 72, page.y() + 167, _("Tip: test from mobile data, not your own Wi-Fi."), 8.5,
                   QColor("#92400e"), w=450)


STEP_TITLES = [
    _("How it works"), _("Open the router page"), _("Find the menu"), _("Fix this PC's IP"), _("Add the rule"),
    _("Windows firewall: open it"), _("Windows firewall: new rule"), _("Windows firewall: Port"),
    _("Windows firewall: TCP {0}"), _("Windows firewall: allow"), _("Windows firewall: name and finish"),
    _("Test from outside"),
]
