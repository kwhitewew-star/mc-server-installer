"""Shared glassmorphism widgets and animations."""

from __future__ import annotations

import math
import time

from PyQt6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer,
                          QVariantAnimation, pyqtProperty)
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath,
                         QPen, QRadialGradient)
from PyQt6.QtWidgets import (QAbstractButton, QComboBox, QFrame, QLabel, QLayout, QPushButton, QSizePolicy,
                             QSpinBox, QWidget)

ACCENT = "#2dd4bf"
ACCENT2 = "#60a5fa"
TEXT = "#eef2ff"
MUTED = "#b3bcd6"
DANGER = "#fb7185"
WARN = "#fbbf24"
OK = "#34d399"


def pick_font() -> str:
    """Pick a UI font that covers the current language's script."""
    from ..i18n import get_language
    per_lang = {
        "ko": ("Pretendard", "Pretendard Variable", "SUIT", "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo",
               "Noto Sans CJK KR", "Noto Sans KR"),
        "ja": ("Yu Gothic UI", "Meiryo UI", "Meiryo", "Hiragino Sans", "Noto Sans CJK JP", "Noto Sans JP"),
        "zh_CN": ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Noto Sans SC"),
    }
    latin = ("Pretendard", "Inter", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Noto Sans", "Malgun Gothic")
    fams = set(QFontDatabase.families())
    for f in per_lang.get(get_language(), latin) + latin:
        if f in fams:
            return f
    return QFont().defaultFamily()


def arrow_svg() -> str:
    """Write the dropdown arrow image to a temp folder and return its path."""
    import tempfile
    from pathlib import Path
    p = Path(tempfile.gettempdir()) / "mcsi_arrow.svg"
    if not p.exists():
        p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
                     '<path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="#9aa4bf" stroke-width="1.8" '
                     'stroke-linecap="round" stroke-linejoin="round"/></svg>', encoding="utf-8")
    return p.as_posix()


def qss(font: str) -> str:
    return f"""
* {{ font-family: '{font}'; color: {TEXT}; }}
QWidget {{ font-size: 10pt; background: transparent; }}
QLabel#h1 {{ font-size: 25pt; font-weight: 800; }}
QLabel#h2 {{ font-size: 16pt; font-weight: 700; }}
QLabel#h3 {{ font-size: 11.5pt; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#small {{ color: {MUTED}; font-size: 8.8pt; }}
QLabel#chip {{ background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14);
  border-radius: 9px; padding: 2px 9px; font-size: 8.6pt; color: {MUTED}; }}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.13);
  border-radius: 10px; padding: 7px 11px; selection-background-color: rgba(45,212,191,0.45); }}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border: 1px solid rgba(255,255,255,0.24); }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid rgba(94,234,212,0.85);
  background: rgba(255,255,255,0.09); }}
QLineEdit:disabled, QComboBox:disabled {{ color: #6b7390; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url({arrow_svg()}); width: 12px; height: 12px; margin-right: 10px; }}
QComboBox QAbstractItemView {{ background: #151b30; border: 1px solid rgba(255,255,255,0.14);
  border-radius: 8px; padding: 4px; outline: 0; selection-background-color: rgba(45,212,191,0.28); }}
QSpinBox {{ padding: 7px 2px; }}
QSpinBox::up-button, QSpinBox::down-button {{ subcontrol-origin: border; width: 0px; border: none; }}
QPlainTextEdit {{ background: rgba(4,8,20,0.55); font-family: 'Cascadia Code','Consolas','D2Coding',monospace;
  font-size: 8.8pt; color: #b9f6e9; border-radius: 12px; padding: 10px; }}
QListWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ padding: 9px 12px; border-radius: 9px; margin: 1px 2px; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.07); }}
QListWidget::item:selected {{ background: rgba(45,212,191,0.22); color: white; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 0; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.32); }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
  background: none; height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QToolTip {{ background: #151b30; color: {TEXT}; border: 1px solid rgba(255,255,255,0.16);
  border-radius: 6px; padding: 6px; }}
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,0.12); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 {ACCENT2});
  border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 18px; height: 18px; margin: -7px 0; border-radius: 9px; }}
"""


# ------------------------------------------------------------------ Background
class Background(QWidget):
    """Slowly drifting color-blob gradient (the base behind the glass)."""

    BLOBS = [("#14b8a6", 0.20, 0.25, 0.55), ("#7c3aed", 0.80, 0.20, 0.50), ("#2563eb", 0.65, 0.85, 0.60),
             ("#db2777", 0.15, 0.85, 0.40), ("#0ea5e9", 0.45, 0.50, 0.35)]

    def __init__(self, parent=None, radius: float = 18):
        super().__init__(parent)
        self.radius = radius
        self.t0 = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.setClipPath(path)
        p.fillRect(r, QColor("#0a0f1f"))
        t = time.time() - self.t0
        w, h = r.width(), r.height()
        for i, (col, x, y, size) in enumerate(self.BLOBS):
            cx = w * (x + 0.08 * math.sin(t * 0.13 + i * 1.7))
            cy = h * (y + 0.08 * math.cos(t * 0.11 + i * 2.3))
            rad = max(w, h) * size * (1 + 0.06 * math.sin(t * 0.2 + i))
            g = QRadialGradient(QPointF(cx, cy), rad)
            c = QColor(col)
            c.setAlpha(120)
            g.setColorAt(0, c)
            c2 = QColor(col)
            c2.setAlpha(0)
            g.setColorAt(1, c2)
            p.fillRect(r, QBrush(g))
        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0, QColor(8, 12, 28, 70))
        veil.setColorAt(1, QColor(8, 12, 28, 150))
        p.fillRect(r, QBrush(veil))
        p.setPen(QPen(QColor(255, 255, 255, 36), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), self.radius, self.radius)


class Glass(QFrame):
    """Translucent glass panel. With frost=True the OpenGL background really blurs and refracts this area."""

    import weakref as _weakref
    registry: "Glass._weakref.WeakSet" = _weakref.WeakSet()
    gl_mode = False

    def __init__(self, parent=None, radius: float = 18, strength: int = 16, frost: bool = True):
        super().__init__(parent)
        self.radius = radius
        self.strength = strength
        self.frost = frost
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        if frost:
            Glass.registry.add(self)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(0, 0, 0, r.height())
        fill = 2 if (Glass.gl_mode and self.frost) else self.strength
        g.setColorAt(0, QColor(255, 255, 255, fill + (6 if fill < 6 else 10)))
        g.setColorAt(1, QColor(255, 255, 255, fill))
        p.setBrush(QBrush(g))
        border = QLinearGradient(0, 0, r.width(), r.height())
        border.setColorAt(0, QColor(255, 255, 255, 70))
        border.setColorAt(0.5, QColor(255, 255, 255, 22))
        border.setColorAt(1, QColor(255, 255, 255, 45))
        p.setPen(QPen(QBrush(border), 1))
        p.drawRoundedRect(r, self.radius, self.radius)


# ------------------------------------------------------------------ Animation helpers
class Hover:
    """Attach an animated 0..1 hover value to a widget."""

    def __init__(self, w: QWidget, ms: int = 160):
        self.w = w
        self.value = 0.0
        self.anim = QVariantAnimation(w)
        self.anim.setDuration(ms)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._set)

    def _set(self, v):
        self.value = float(v)
        self.w.update()

    def to(self, target: float):
        self.anim.stop()
        self.anim.setStartValue(self.value)
        self.anim.setEndValue(float(target))
        self.anim.start()


def mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


# ------------------------------------------------------------------ Buttons
class Button(QPushButton):
    def __init__(self, text: str, kind: str = "ghost", parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self.h = Hover(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        f = self.font()
        f.setBold(kind == "primary")
        self.setFont(f)

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(max(s.width() + 28, 96), 42)

    def enterEvent(self, e):
        self.h.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.h.to(0)
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        en = self.isEnabled()
        hv = self.h.value if en else 0
        if self.kind == "primary":
            g = QLinearGradient(r.topLeft(), r.topRight())
            c1, c2 = QColor(ACCENT), QColor(ACCENT2)
            if not en:
                c1.setAlpha(70)
                c2.setAlpha(70)
            g.setColorAt(0, c1.lighter(int(100 + 15 * hv)))
            g.setColorAt(1, c2.lighter(int(100 + 15 * hv)))
            if en and hv > 0:
                glow = QColor(ACCENT)
                glow.setAlpha(int(70 * hv))
                p.setPen(QPen(glow, 6))
                p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 12, 12)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 12, 12)
            p.setPen(QColor("#04121a") if en else QColor(255, 255, 255, 90))
        elif self.kind == "danger":
            p.setPen(QPen(QColor(251, 113, 133, int(120 + 100 * hv)), 1))
            p.setBrush(QColor(251, 113, 133, int(25 + 35 * hv)))
            p.drawRoundedRect(r, 12, 12)
            p.setPen(QColor(DANGER) if en else QColor(255, 255, 255, 80))
        else:
            p.setPen(QPen(QColor(255, 255, 255, int(40 + 50 * hv)), 1))
            p.setBrush(QColor(255, 255, 255, int(12 + 20 * hv)))
            p.drawRoundedRect(r, 12, 12)
            p.setPen(QColor(TEXT) if en else QColor(255, 255, 255, 80))
        p.setFont(self.font())
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())


class Toggle(QAbstractButton):
    """Animated toggle switch."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self.anim = QPropertyAnimation(self, b"knob", self)
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)

    def _animate(self, on: bool):
        self.anim.stop()
        self.anim.setStartValue(self._pos)
        self.anim.setEndValue(1.0 if on else 0.0)
        self.anim.start()

    def setChecked(self, on: bool):  # noqa: N802
        super().setChecked(on)
        if not self.signalsBlocked():
            return
        self._pos = 1.0 if on else 0.0
        self.update()

    def get_pos(self):
        return self._pos

    def set_pos(self, v):
        self._pos = v
        self.update()

    knob = pyqtProperty(float, get_pos, set_pos)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        off, on = QColor(255, 255, 255, 40), QColor(ACCENT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mix(off, on, self._pos))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Card(QAbstractButton):
    """Selectable card (mode / server type). Glows in its accent color when checked."""

    def __init__(self, title: str, desc: str, accent: str = ACCENT, badge: str = "", icon: str = "",
                 parent=None, height: int = 104):
        super().__init__(parent)
        self.title, self.desc, self.accent, self.badge, self.icon = title, desc, QColor(accent), badge, icon
        self.setCheckable(True)
        self.h = Hover(self)
        self.sel = Hover(self, 220)
        self.toggled.connect(lambda on: self.sel.to(1 if on else 0))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(220, self.minimumHeight())

    def enterEvent(self, e):
        self.h.to(1)

    def leaveEvent(self, e):
        self.h.to(0)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hv, sv = self.h.value, self.sel.value
        r = QRectF(self.rect()).adjusted(3, 3 - 2 * hv, -3, -3 - 2 * hv)
        base = QColor(255, 255, 255, int(14 + 12 * hv))
        acc = QColor(self.accent)
        acc.setAlpha(46)
        p.setBrush(mix(base, acc, sv))
        border = QColor(255, 255, 255, int(34 + 40 * hv))
        a2 = QColor(self.accent)
        a2.setAlpha(230)
        p.setPen(QPen(mix(border, a2, sv), 1 + sv))
        p.drawRoundedRect(r, 16, 16)
        if sv > 0:
            glow = QColor(self.accent)
            glow.setAlpha(int(60 * sv))
            p.setPen(QPen(glow, 7))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 18, 18)
        x = r.left() + 18
        if self.icon:
            dot = QRectF(x, r.top() + 16, 34, 34)
            g = QLinearGradient(dot.topLeft(), dot.bottomRight())
            c = QColor(self.accent)
            g.setColorAt(0, c.lighter(120))
            g.setColorAt(1, c.darker(140))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(dot, 10, 10)
            f = self.font()
            f.setPointSizeF(13)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#06101a"))
            p.drawText(dot, Qt.AlignmentFlag.AlignCenter, self.icon)
            x = dot.right() + 12
        f = self.font()
        f.setPointSizeF(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        limit = r.right() - 36                       # keep clear of the check mark
        title = p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, int(limit - x))
        p.drawText(QRectF(x, r.top() + 14, limit - x, 24), Qt.AlignmentFlag.AlignLeft, title)
        shift = 0
        if self.badge:
            fm = p.fontMetrics()
            bx = x + fm.horizontalAdvance(title) + 10
            f2 = self.font()
            f2.setPointSizeF(8)
            f2.setBold(True)
            p.setFont(f2)
            bw = p.fontMetrics().horizontalAdvance(self.badge) + 14
            by = r.top() + 17
            if bx + bw > limit:                      # no room next to the title: put it on its own line
                bx, by = x, r.top() + 38
                shift = 0 if self.icon else 20
            br = QRectF(bx, by, bw, 18)
            bc = QColor(self.accent)
            bc.setAlpha(60)
            p.setBrush(bc)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(br, 9, 9)
            p.setPen(QColor(self.accent).lighter(130))
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, self.badge)
        f3 = self.font()
        f3.setPointSizeF(9.2)
        p.setFont(f3)
        p.setPen(QColor(MUTED))
        top = r.top() + (56 if self.icon else 44) + shift
        p.drawText(QRectF(r.left() + 18, top, r.width() - 34, r.bottom() - top - 8),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop) | int(Qt.TextFlag.TextWordWrap),
                   self.desc)
        if sv > 0.01:  # check mark
            c = QRectF(r.right() - 30, r.top() + 12, 18, 18)
            p.setPen(Qt.PenStyle.NoPen)
            cc = QColor(self.accent)
            cc.setAlpha(int(255 * sv))
            p.setBrush(cc)
            p.drawEllipse(c)
            p.setPen(QPen(QColor(6, 16, 26, int(255 * sv)), 2))
            path = QPainterPath(QPointF(c.left() + 4.5, c.center().y()))
            path.lineTo(c.left() + 8, c.bottom() - 5)
            path.lineTo(c.right() - 4, c.top() + 5)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)


class NoWheelSpin(QSpinBox):
    """Only accept the mouse wheel when focused, so scrolling the page doesn't change values."""

    def __init__(self, *a):
        super().__init__(*a)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lineEdit().setTextMargins(10, 0, 4, 0)

    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class NoWheelCombo(QComboBox):
    def __init__(self, *a):
        super().__init__(*a)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class Progress(QWidget):
    """Smoothly easing progress bar with a shimmer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target = 0.0
        self.value = 0.0
        self.busy = False
        self.setFixedHeight(12)
        self.t = QTimer(self)
        self.t.timeout.connect(self._tick)
        self.t.start(16)
        self.phase = 0.0

    def set_value(self, v: float):
        self.target = max(0.0, min(100.0, v))

    def _tick(self):
        self.value += (self.target - self.value) * 0.12
        self.phase = (self.phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 26))
        p.drawRoundedRect(r, 6, 6)
        w = r.width() * self.value / 100
        if w > 1:
            fr = QRectF(0, 0, w, r.height())
            g = QLinearGradient(0, 0, r.width(), 0)
            g.setColorAt(0, QColor(ACCENT))
            g.setColorAt(1, QColor(ACCENT2))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(fr, 6, 6)
            sx = fr.width() * self.phase
            sh = QLinearGradient(sx - 60, 0, sx + 60, 0)
            sh.setColorAt(0, QColor(255, 255, 255, 0))
            sh.setColorAt(0.5, QColor(255, 255, 255, 90))
            sh.setColorAt(1, QColor(255, 255, 255, 0))
            p.setClipRect(fr)
            p.setBrush(QBrush(sh))
            p.drawRoundedRect(fr, 6, 6)


class Spinner(QWidget):
    def __init__(self, size: int = 22, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.a = 0
        self.t = QTimer(self)
        self.t.timeout.connect(self._tick)

    def start(self):
        self.show()
        self.t.start(16)

    def stop(self):
        self.t.stop()
        self.hide()

    def _tick(self):
        self.a = (self.a + 7) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        p.setPen(QPen(QColor(255, 255, 255, 40), 3))
        p.drawEllipse(r)
        pen = QPen(QColor(ACCENT), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, -self.a * 16, 100 * 16)


class CheckBurst(QWidget):
    """Check-mark animation on the done page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.t = 0.0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(1100)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._set)
        self.ok = True

    def play(self, ok: bool = True):
        self.ok = ok
        self.anim.stop()
        self.anim.start()

    def _set(self, v):
        self.t = float(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(OK if self.ok else DANGER)
        r = QRectF(self.rect()).adjusted(14, 14, -14, -14)
        glow = QColor(c)
        glow.setAlpha(int(60 * self.t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(r.adjusted(-10 * self.t, -10 * self.t, 10 * self.t, 10 * self.t))
        pen = QPen(c, 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(r, 90 * 16, int(-360 * 16 * min(1.0, self.t * 1.6)))
        k = max(0.0, (self.t - 0.45) / 0.55)
        if k <= 0:
            return
        if self.ok:
            path = QPainterPath(QPointF(r.left() + r.width() * 0.28, r.center().y() + 2))
            path.lineTo(QPointF(r.left() + r.width() * 0.45, r.bottom() - r.height() * 0.3))
            path.lineTo(QPointF(r.right() - r.width() * 0.26, r.top() + r.height() * 0.32))
            p.drawPath(path if k >= 1 else _partial(path, k))
        else:
            a, b = r.width() * 0.32, r.width() * 0.68
            for (x1, y1, x2, y2), kk in (((a, a, b, b), min(1.0, k * 2)), ((b, a, a, b), max(0.0, k * 2 - 1))):
                if kk > 0:
                    s = QPointF(r.left() + x1, r.top() + y1)
                    e_ = QPointF(r.left() + x2, r.top() + y2)
                    p.drawLine(s, s + (e_ - s) * kk)


def _partial(path: QPainterPath, k: float) -> QPainterPath:
    out = QPainterPath()
    n = 40
    out.moveTo(path.pointAtPercent(0))
    for i in range(1, int(n * k) + 1):
        out.lineTo(path.pointAtPercent(i / n))
    return out


class ElideLabel(QLabel):
    """Elides with '…' when too narrow and shows the full text as a tooltip. Never widens the layout."""

    def __init__(self, text: str, obj: str = ""):
        super().__init__()
        self._full = text
        if obj:
            self.setObjectName(obj)
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(16)
        super().setText(text)

    def setText(self, text: str):  # noqa: N802
        self._full = text
        self.setToolTip(text)
        self._elide()

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, max(8, self.width())))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(min(self.fontMetrics().horizontalAdvance(self._full) + 4, 600), s.height())


class FlowLayout(QLayout):
    """Lays widgets out left to right and wraps to the next line when the row is full."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._sp = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # noqa: N802
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, w):  # noqa: N802
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line = rect.x(), rect.y(), 0
        for it in self._items:
            hint = it.sizeHint()
            if x + hint.width() > rect.right() + 1 and line > 0:
                x, y, line = rect.x(), y + line + self._sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._sp
            line = max(line, hint.height())
        return y + line - rect.y()


def wrap_label(text: str, obj: str = "small") -> QLabel:
    """Word-wrapping label that never widens the layout, even with long words."""
    l = QLabel(text)
    l.setObjectName(obj)
    l.setWordWrap(True)
    l.setMinimumWidth(1)
    l.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    return l


def label(text: str, obj: str = "", wrap: bool = False) -> QLabel:
    l = QLabel(text)
    if obj:
        l.setObjectName(obj)
    l.setWordWrap(wrap)
    return l
