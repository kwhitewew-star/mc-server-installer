"""Main window: frameless glass window, step rail, page transitions."""

from __future__ import annotations
from ..i18n import _

import os
import sys

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QHBoxLayout, QMessageBox, QStackedWidget, QVBoxLayout, QWidget)

from .app_settings import APP_DEFAULTS, SettingsOverlay
from .port_guide import PortGuide

RESTART = {"on": False}
from .pages_setup import Page, ResourcePage, ServerPage, VersionPage, WelcomePage
from .pages_addons import AddonsPage
from .pages_config import DonePage, InstallPage, ManagePage, PropsPage, RulesPage, SummaryPage
from .state import MODE_STEPS, STEP_NAMES, State
from .widgets import ACCENT, ACCENT2, MUTED, TEXT, Background, Button, Glass, Hover, pick_font, qss


class TitleButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.h = Hover(self)
        self.setFixedSize(42, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self.h.to(1)

    def leaveEvent(self, e):
        self.h.to(0)

    def mousePressEvent(self, e):
        # accept the press here so the title bar (window drag) doesn't swallow it -> single click works
        e.accept()

    def mouseReleaseEvent(self, e):
        e.accept()
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hv = self.h.value
        bg = QColor(232, 17, 35, int(220 * hv)) if self.kind == "close" else QColor(255, 255, 255, int(30 * hv))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 8, 8)
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.3))
        c = QPointF(self.width() / 2, self.height() / 2)
        if self.kind == "min":
            p.drawLine(QPointF(c.x() - 5, c.y()), QPointF(c.x() + 5, c.y()))
        elif self.kind == "max":
            p.drawRect(QRectF(c.x() - 5, c.y() - 5, 10, 10))
        else:
            p.drawLine(QPointF(c.x() - 5, c.y() - 5), QPointF(c.x() + 5, c.y() + 5))
            p.drawLine(QPointF(c.x() + 5, c.y() - 5), QPointF(c.x() - 5, c.y() + 5))


class TitleBar(QWidget):
    def __init__(self, win: QWidget):
        super().__init__()
        self.win = win
        self.setFixedHeight(44)
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 8, 10, 0)
        h.setSpacing(4)
        logo = Logo()
        h.addWidget(logo)
        h.addSpacing(8)
        from .widgets import label
        h.addWidget(label("MC Server Installer", "h3"))
        h.addStretch(1)
        self.gear = Button(_("⚙  Settings"))
        self.gear.setMinimumHeight(30)
        self.gear.setToolTip(_("App settings"))
        self.gear.clicked.connect(win.open_settings)
        h.addWidget(self.gear)
        h.addSpacing(4)
        self.fx = Button("")
        self.fx.setMinimumHeight(30)
        self.fx.setToolTip(_("3D background quality (High → Normal → Off)"))
        self.fx.clicked.connect(win.cycle_fx)
        h.addWidget(self.fx)
        h.addSpacing(6)
        for kind, fn in (("min", win.showMinimized), ("max", self.toggle_max), ("close", win.close)):
            b = TitleButton(kind)
            b.clicked.connect(fn)
            h.addWidget(b)

    def toggle_max(self):
        self.win.showNormal() if self.win.isMaximized() else self.win.showMaximized()

    def _on_empty_area(self, pos) -> bool:
        w = self.childAt(pos)
        while w is not None and w is not self:
            if isinstance(w, (TitleButton, QAbstractButton)):
                return False
            w = w.parentWidget()
        return True

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.win.windowHandle() \
                and self._on_empty_area(e.position().toPoint()):
            self.win.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        if self._on_empty_area(e.position().toPoint()):
            self.toggle_max()


class Logo(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(26, 26)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 26, 26)
        g.setColorAt(0, QColor(ACCENT))
        g.setColorAt(1, QColor(ACCENT2))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, 26, 26), 8, 8)
        p.setBrush(QColor(6, 16, 26, 200))
        for x, y in ((6, 6), (14, 6), (6, 14), (14, 14)):
            if (x, y) != (14, 6):
                p.drawRoundedRect(QRectF(x, y, 6, 6), 1.5, 1.5)


class StepRail(QWidget):
    """Step list on the left. The highlight bar slides to the current step."""

    jump = pyqtSignal(int)
    ITEM = 46

    def __init__(self):
        super().__init__()
        self.steps: list[str] = []
        self.cur = 0
        self.reached = 0
        self.y = 0.0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(320)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._y)
        self.setMinimumWidth(210)
        self.setMouseTracking(True)
        self.hover = -1

    def set_steps(self, steps, cur, reached):
        self.steps, self.reached = steps, reached
        self.set_current(cur)
        self.setMinimumHeight(len(steps) * self.ITEM + 20)
        self.update()

    def set_current(self, i):
        self.cur = i
        self.anim.stop()
        self.anim.setStartValue(self.y)
        self.anim.setEndValue(float(i * self.ITEM))
        self.anim.start()

    def _y(self, v):
        self.y = float(v)
        self.update()

    def mouseMoveEvent(self, e):
        i = int((e.position().y() - 10) // self.ITEM)
        self.hover = i if 0 <= i < len(self.steps) and i <= self.reached else -1
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.hover >= 0 else Qt.CursorShape.ArrowCursor)
        self.update()

    def leaveEvent(self, e):
        self.hover = -1
        self.update()

    def mousePressEvent(self, e):
        if self.hover >= 0:
            self.jump.emit(self.hover)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = 10
        n = len(self.steps)
        if n > 1:  # connector line
            p.setPen(QPen(QColor(255, 255, 255, 30), 2))
            p.drawLine(QPointF(31, top + self.ITEM / 2), QPointF(31, top + (n - 0.5) * self.ITEM))
            prog = QColor(ACCENT)
            prog.setAlpha(160)
            p.setPen(QPen(prog, 2))
            p.drawLine(QPointF(31, top + self.ITEM / 2), QPointF(31, top + self.ITEM / 2 + self.y))
        pill = QRectF(8, top + self.y + 4, self.width() - 16, self.ITEM - 8)
        g = QLinearGradient(pill.topLeft(), pill.topRight())
        a, b = QColor(ACCENT), QColor(ACCENT2)
        a.setAlpha(60)
        b.setAlpha(20)
        g.setColorAt(0, a)
        g.setColorAt(1, b)
        p.setBrush(g)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRoundedRect(pill, 12, 12)
        f = QFont(self.font())
        for i, key in enumerate(self.steps):
            y = top + i * self.ITEM
            c = QRectF(20, y + self.ITEM / 2 - 11, 22, 22)
            done = i < self.cur or (i <= self.reached and i != self.cur)
            if i == self.cur:
                p.setBrush(QColor(ACCENT))
                p.setPen(Qt.PenStyle.NoPen)
            elif done:
                p.setBrush(QColor(45, 212, 191, 50))
                p.setPen(QPen(QColor(ACCENT), 1.2))
            else:
                p.setBrush(QColor(20, 26, 46))
                p.setPen(QPen(QColor(255, 255, 255, 50), 1.2))
            p.drawEllipse(c)
            f.setPointSizeF(8.5)
            f.setBold(True)
            p.setFont(f)
            if done and i != self.cur:
                p.setPen(QPen(QColor(ACCENT), 1.8))
                p.drawLine(QPointF(c.left() + 6, c.center().y()), QPointF(c.left() + 9.5, c.bottom() - 7))
                p.drawLine(QPointF(c.left() + 9.5, c.bottom() - 7), QPointF(c.right() - 5.5, c.top() + 7))
            else:
                p.setPen(QColor("#06101a") if i == self.cur else QColor(MUTED))
                p.drawText(c, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            f.setPointSizeF(10)
            f.setBold(i == self.cur)
            p.setFont(f)
            col = QColor(TEXT) if i == self.cur else (QColor("#d5dbec") if i <= self.reached else QColor("#9aa3bf"))
            if i == self.hover and i != self.cur:
                col = QColor("white")
            p.setPen(col)
            p.drawText(QRectF(54, y, self.width() - 60, self.ITEM), int(Qt.AlignmentFlag.AlignVCenter),
                       STEP_NAMES[key])


class Transition(QWidget):
    """Transition that slides and fades snapshots of the old and new page."""

    def __init__(self, parent, old: QPixmap, new: QPixmap, direction: int, done):
        super().__init__(parent)
        self.old, self.new, self.dir = old, new, direction
        self.t = 0.0
        self.setGeometry(parent.rect())
        self.a = QVariantAnimation(self)
        self.a.setDuration(340)
        self.a.setStartValue(0.0)
        self.a.setEndValue(1.0)
        self.a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.a.valueChanged.connect(self._t)
        self.a.finished.connect(done)
        self.show()
        self.raise_()
        self.a.start()

    def _t(self, v):
        self.t = float(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        d = 60 * self.dir
        p.setOpacity(max(0.0, 1 - self.t * 1.4))
        p.drawPixmap(QPointF(-d * self.t, 0), self.old)
        p.setOpacity(min(1.0, self.t * 1.2))
        p.drawPixmap(QPointF(d * (1 - self.t), 0), self.new)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MC Server Installer")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.resize(1200, 780)
        self.setMinimumSize(1000, 680)
        self.st = State.load()
        self._apply_app_settings(startup=True)
        self.bg = Background(self, radius=0)
        self.gl = None
        if self.st.fx != "off":
            self._start_gl()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.bar = TitleBar(self)
        outer.addWidget(self.bar)
        body = QHBoxLayout()
        body.setContentsMargins(16, 6, 16, 16)
        body.setSpacing(14)
        side = Glass(radius=20)
        self._outer_glass = []
        self._outer_glass.append(side)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(6, 12, 6, 12)
        self.rail = StepRail()
        self.rail.jump.connect(self._jump)
        sl.addWidget(self.rail)
        sl.addStretch(1)
        body.addWidget(side)
        main = Glass(radius=20)
        self._outer_glass.append(main)
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 16)
        self.stack = QStackedWidget()
        ml.addWidget(self.stack, 1)
        nav = QHBoxLayout()
        nav.setContentsMargins(34, 0, 28, 0)
        self.back = Button(_("←  Back"))
        self.back.clicked.connect(self.go_back)
        self.hint = QWidget()
        from .widgets import label
        self.hint_lbl = label("", "small")
        self.next = Button(_("Next  →"), "primary")
        self.next.setMinimumWidth(150)
        self.next.clicked.connect(self.go_next)
        nav.addWidget(self.back)
        nav.addStretch(1)
        nav.addWidget(self.hint_lbl)
        nav.addSpacing(12)
        nav.addWidget(self.next)
        ml.addLayout(nav)
        body.addWidget(main, 1)
        outer.addLayout(body, 1)

        st = self.st
        self.pages: dict[str, Page] = {
            "welcome": WelcomePage(st), "server": ServerPage(st), "version": VersionPage(st), "addons": AddonsPage(st),
            "resource": ResourcePage(st), "props": PropsPage(st), "rules": RulesPage(st),
            "manage": ManagePage(st), "summary": SummaryPage(st), "install": InstallPage(st),
            "done": DonePage(st)}
        for pg in self.pages.values():
            self.stack.addWidget(pg)
            pg.changed.connect(self.refresh_nav)
        self.pages["welcome"].mode_changed.connect(self._mode)
        self.pages["install"].finished.connect(self._installed)
        self.pages["done"].restart.connect(self._restart)
        self.pages["done"].back_to.connect(self._back_to)
        self.idx = 0
        self.reached = 0
        self._busy = False
        start = "server" if self.app("skip_welcome") else "welcome"
        self.idx = self.steps.index(start)
        self.reached = self.idx
        self.stack.setCurrentWidget(self.pages[start])
        self.rail.set_steps(self.steps, self.idx, self.reached)
        self.pages["welcome"].enter()
        self.pages[start].enter()
        self.refresh_nav()
        self.settings = SettingsOverlay(self, st)
        self.settings.changed.connect(self._app_changed)
        self.settings.fx_changed.connect(self.set_fx)
        self.settings.reset_all.connect(self._reset_all)
        self.settings.restart_requested.connect(self.restart_app)
        self.ports = PortGuide(self, st)
        self.pages["done"].port_guide.connect(self.ports.open_anim)
        self._fx_label(self.st.fx)
        self.pages["server"].changed.connect(self._sync_gl)
        self.pages["server"].picked.connect(lambda k: self.gl and self.gl.play_anim(k))
        self._sync_gl()

    # ---- 3D background ----
    def _start_gl(self):
        try:
            from ..gfx.scene import GLBackground
            self.gl = GLBackground(self, self.glass_rects, self.st.fx)
        except Exception as e:  # e.g. PyOpenGL missing
            self._gl_failed(str(e))
            return
        self.gl.failed.connect(self._gl_failed)
        self.gl.parallax = bool(self.app("parallax"))
        self.gl.particles = bool(self.app("particles"))
        self.gl.anim_on = bool(self.app("server_anim"))
        self.gl.lowered.connect(self._gl_lowered)
        self.gl.setGeometry(self.rect())
        self.gl.lower()
        self.bg.hide()
        self.bg.timer.stop()
        Glass.gl_mode = True

    def _gl_failed(self, msg):
        if self.gl:
            self.gl.hide()
            self.gl.deleteLater()
            self.gl = None
        Glass.gl_mode = False
        self.bg.show()
        self.bg.timer.start(33)
        self.bg.lower()
        self.st.fx = "off"
        self._fx_label("off", failed=True)
        self.update()

    def _gl_lowered(self, q):
        self.st.fx = q
        self._fx_label(q)
        self.bar.fx.setToolTip(_("Quality was lowered automatically to match your graphics performance"))

    def _fx_label(self, fx, failed=False):
        names = {"high": _("High"), "normal": _("Normal"), "off": _("Off")}
        self.bar.fx.setText((_("✦ 3D effects: ") + names.get(fx, fx)) if not failed else _("✦ 3D effects: not supported"))

    # ---- App settings ----
    def app(self, key):
        return self.st.app.get(key, APP_DEFAULTS[key])

    def _apply_app_settings(self, startup=False):
        from ..core.java import INCLUDE_LAUNCHER
        from .state import BASE_FOLDER
        BASE_FOLDER["path"] = self.app("base_folder")
        INCLUDE_LAUNCHER["on"] = bool(self.app("launcher_java"))
        if getattr(self, "gl", None):
            self.gl.parallax = bool(self.app("parallax"))
            self.gl.particles = bool(self.app("particles"))
            self.gl.anim_on = bool(self.app("server_anim"))

    def _app_changed(self, key):
        self._apply_app_settings()
        if key == "first_run_default":
            self.st.values["manage:first_run"] = bool(self.app("first_run_default"))
        if key == "base_folder" and not self.st.folder_custom and self.st.mc:
            from .state import default_folder
            self.st.folder = default_folder(self.st.server, self.st.mc)
        if key == "launcher_java":
            self.pages["resource"]._scanned = False

    def open_settings(self):
        if self.pages["install"].running:
            return
        self.settings.open_anim()

    def _reset_all(self):
        from ..core import schema
        r = QMessageBox.question(self, _("Reset"), _("Reset server type, version, all inputs and the mod list to defaults?\n(App settings are kept)"))
        if r != QMessageBox.StandardButton.Yes:
            return
        st = self.st
        st.values = schema.defaults()
        st.values["manage:first_run"] = bool(self.app("first_run_default"))
        st.server, st.mc, st.build, st.folder, st.folder_custom = "paper", "", "", "", False
        st.addons, st.addons_ctx, st.eula = [], [], False
        st.save()
        self.settings.close_anim()
        self.reached = 0
        self.go(0)

    def set_fx(self, q):
        order = ["high", "normal", "off"]
        if q not in order:
            return
        self.st.fx = order[(order.index(q) - 1) % 3]
        self.cycle_fx()

    def cycle_fx(self):
        order = ["high", "normal", "off"]
        nxt = order[(order.index(self.st.fx) + 1) % 3] if self.st.fx in order else "high"
        self.st.fx = nxt
        if nxt == "off":
            if self.gl:
                self.gl.hide()
                self.gl.timer.stop()
            Glass.gl_mode = False
            self.bg.show()
            self.bg.timer.start(33)
            self.bg.lower()
        else:
            if self.gl is None:
                self._start_gl()
                self._sync_gl()
            else:
                self.gl.set_quality(nxt)
                self.gl.show()
                self.gl.timer.start(16)
                self.bg.hide()
                self.bg.timer.stop()
                Glass.gl_mode = True
        self._fx_label(nxt)
        self.st.save()
        self.update()
        for g in list(Glass.registry):
            g.update()

    def glass_rects(self):
        out = []
        for g in list(Glass.registry):
            if not g.isVisible() or g.window() is not self or g.width() < 4:
                continue
            if self._busy and g not in self._outer_glass:
                continue
            tl = g.mapTo(self, g.rect().topLeft())
            out.append((tl.x(), tl.y(), g.width(), g.height(), g.radius))
        out.sort(key=lambda r: -(r[2] * r[3]))
        return out

    def _sync_gl(self):
        if not self.gl:
            return
        from ..core.providers import PROVIDERS
        key = self.steps[self.idx]
        self.gl.set_step(key)
        if key not in ("install", "done"):
            self.gl.set_accent(PROVIDERS[self.st.server].accent if key != "welcome" else ACCENT)

    # ---- Resizing (drag the edges) ----
    def resizeEvent(self, e):
        self.bg.setGeometry(self.rect())
        if self.gl:
            self.gl.setGeometry(self.rect())
        for ov in (getattr(self, "settings", None), getattr(self, "ports", None)):
            if ov is not None and ov.isVisible():
                ov.setGeometry(self.rect())
        super().resizeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if sys.platform == "win32":  # Windows 11 rounded corners
            try:
                import ctypes
                pref = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 33, ctypes.byref(pref),
                                                           ctypes.sizeof(pref))
            except Exception:
                pass

    def mousePressEvent(self, e):
        m = 8
        x, y = e.position().x(), e.position().y()
        edges = Qt.Edge(0)
        if x < m:
            edges |= Qt.Edge.LeftEdge
        if x > self.width() - m:
            edges |= Qt.Edge.RightEdge
        if y < m:
            edges |= Qt.Edge.TopEdge
        if y > self.height() - m:
            edges |= Qt.Edge.BottomEdge
        if edges != Qt.Edge(0) and self.windowHandle():
            self.windowHandle().startSystemResize(edges)

    # ---- Steps ----
    @property
    def steps(self) -> list[str]:
        return MODE_STEPS[self.st.mode]

    def _mode(self, m):
        self.reached = min(self.reached, 0)
        self.rail.set_steps(self.steps, self.idx, self.reached)
        self.refresh_nav()

    def page(self) -> Page:
        return self.pages[self.steps[self.idx]]

    def refresh_nav(self):
        key = self.steps[self.idx]
        pg = self.page()
        self.back.setVisible(key not in ("welcome", "done"))
        self.back.setEnabled(key != "install" or not self.pages["install"].running)
        self.next.setVisible(key not in ("install", "done"))
        self.next.setEnabled(pg.can_next() and not self._busy)
        self.next.setText(_("Install  ✓") if key == "summary" else _("Next  →"))
        hints = {"server": "", "version": "", "summary": "" if self.st.eula else _("You must accept the EULA to install")}
        if key == "resource" and not pg.can_next():
            self.hint_lbl.setText(_("Java {0} or newer is required").format(self.st.java_need))
        else:
            self.hint_lbl.setText(hints.get(key, ""))

    def go(self, new_idx: int):
        if new_idx == self.idx or self._busy:
            return
        direction = 1 if new_idx > self.idx else -1
        old_w = self.page()
        old_w.leave()
        self.idx = new_idx
        self.reached = max(self.reached, new_idx)
        new_w = self.page()
        new_w.enter()
        if not self.app("transitions"):
            self.stack.setCurrentWidget(new_w)
            self.rail.set_steps(self.steps, self.idx, self.reached)
            self._sync_gl()
            self.refresh_nav()
            if self.steps[self.idx] == "install":
                self._start_install()
            return
        pm_old = old_w.grab()
        self.stack.setCurrentWidget(new_w)
        new_w.resize(self.stack.size())
        pm_new = new_w.grab()
        self._busy = True
        self.stack.hide()
        holder = self.stack.parentWidget()

        def done():
            self.stack.show()
            tr.deleteLater()
            self._busy = False
            self.refresh_nav()

        self._sync_gl()
        tr = Transition(holder, pm_old, pm_new, direction, done)
        tr.setGeometry(self.stack.geometry())
        self.rail.set_steps(self.steps, self.idx, self.reached)
        self.refresh_nav()
        if self.steps[self.idx] == "install":
            self._start_install()

    def _start_install(self):
        ip = self.pages["install"]
        ip.start()
        if self.gl:
            self.gl.set_installing(0.0)
            ip.worker.progress.connect(lambda v: self.gl and self.gl.set_installing(v / 100))

    def go_next(self):
        pg = self.page()
        msg = pg.validate()
        if msg:
            QMessageBox.warning(self, _("Check required"), msg)
            return
        if self.steps[self.idx] == "summary":
            self.st.save()
        if self.idx < len(self.steps) - 1:
            self.go(self.idx + 1)

    def go_back(self):
        if self.idx > 0:
            self.go(self.idx - 1)

    def _jump(self, i):
        if self.pages["install"].running:
            return
        if self.steps[i] in ("install", "done") and self.steps[self.idx] != "done":
            return
        self.go(i)

    def _installed(self, ok):
        ok_, msg, summary = self.pages["install"].result
        if self.gl:
            self.gl.set_result(ok_)
        fwd = self.pages["install"].forward
        self.ports.set_result(fwd)
        self.pages["done"].show_result(ok_, msg, summary, fwd)
        if ok_:
            from pathlib import Path
            from .state import open_path
            if self.app("open_folder_after"):
                open_path(str(Path(self.st.folder).expanduser()))
            if self.app("run_after"):
                self.pages["done"]._run()
        self.go(self.steps.index("done"))

    def restart_app(self):
        """Close and start a fresh instance (used after switching the language)."""
        RESTART["on"] = True
        self.close()
        if self.isVisible():          # close was cancelled
            RESTART["on"] = False

    def _restart(self):
        self.reached = 0
        self.go(0)

    def _back_to(self, key):
        if key in self.steps:
            self.go(self.steps.index(key))

    def closeEvent(self, e):
        ip = self.pages["install"]
        if ip.running:
            r = QMessageBox.question(self, _("Quit"), _("Installation is in progress. Cancel and quit?"))
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            ip.worker.cancel()
            ip.worker.wait(8000)
        self.st.save()
        # stop leftover background work (icons, lists, Java scan) so it can't delay exit
        from PyQt6.QtCore import QThreadPool
        from .state import icon_pool
        QThreadPool.globalInstance().clear()
        icon_pool().clear()
        if self.gl:
            self.gl.timer.stop()
        self.bg.timer.stop()
        e.accept()
        QApplication.instance().quit()


def main():
    try:
        from ..gfx.scene import set_default_format
        set_default_format()
    except Exception:
        pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("MC Server Installer")
    font = pick_font()
    app.setFont(QFont(font, 10))
    app.setStyleSheet(qss(font))
    w = MainWindow()
    w.show()
    code = app.exec()
    if RESTART["on"]:
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        subprocess.Popen([sys.executable, "-m", "mcsi"], cwd=str(root))
    # exit immediately even if worker threads are waiting on the network (settings were saved in closeEvent)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
