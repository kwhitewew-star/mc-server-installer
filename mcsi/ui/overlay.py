"""Base class for glass dialogs that slide in over the main window."""

from __future__ import annotations

from PyQt6.QtCore import QAbstractAnimation, QEasingCurve, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..i18n import _
from .widgets import Button, Glass, label


class Backdrop(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.alpha = 0.0
        self.strength = 185

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(4, 6, 16, int(self.strength * self.alpha)))


class DarkPanel(Glass):
    """Dialog body: dark, mostly opaque glass so the text stays readable."""

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(0, 0, 0, r.height())
        g.setColorAt(0, QColor(26, 33, 58, 250))
        g.setColorAt(1, QColor(14, 18, 34, 250))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.drawRoundedRect(r, self.radius, self.radius)


class Overlay(QWidget):
    """Translucent scrim over the whole window + a centered glass panel with open/close animation.

    Subclasses fill ``self.body`` (a QVBoxLayout below the title row) and may override
    ``before_open``.
    """

    max_size = (720, 620)
    closed = pyqtSignal()

    def __init__(self, win, title: str):
        super().__init__(win)
        self.win = win
        self.back = Backdrop(self)
        self.panel = DarkPanel(self, radius=22, strength=28, frost=False)
        self.body = QVBoxLayout(self.panel)
        self.body.setContentsMargins(26, 22, 26, 20)
        self.body.setSpacing(10)
        top = QHBoxLayout()
        self.title = label(title, "h2")
        top.addWidget(self.title)
        top.addStretch(1)
        self.close_btn = Button(_("Close"), "primary")
        self.close_btn.clicked.connect(self.close_anim)
        top.addWidget(self.close_btn)
        self.body.addLayout(top)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(240)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._step)
        self._closing = False
        self.anim.finished.connect(self._done)
        self.hide()

    def before_open(self) -> None:
        pass

    def open_anim(self):
        self.setGeometry(self.win.rect())
        self.before_open()
        self._closing = False
        self.show()
        self.raise_()
        self.setFocus()
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def close_anim(self):
        self._closing = True
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _done(self):
        if self._closing:
            self.hide()
            self.closed.emit()

    def panel_rect(self, w: int, h: int, v: float):
        """Panel geometry for animation value v (0..1). Centered by default."""
        return (self.width() - w) // 2, (self.height() - h) // 2 + int((1 - v) * 18)

    def _step(self, v):
        v = float(v or 0.0)
        self.back.alpha = v
        self.back.setGeometry(self.rect())
        w, h = min(self.max_size[0], self.width() - 80), min(self.max_size[1], self.height() - 80)
        s = 0.94 + 0.06 * v
        pw, ph = int(w * s), int(h * s)
        x, y = self.panel_rect(pw, ph, v)
        self.panel.setGeometry(x, y, pw, ph)
        self.panel.setWindowOpacity(v)
        self.back.update()

    def resizeEvent(self, e):
        running = self.anim.state() == QAbstractAnimation.State.Running
        cur = self.anim.currentValue() if running else None
        self._step(cur if cur is not None else (1.0 if self.isVisible() else 0.0))

    def mousePressEvent(self, e):
        if not self.panel.geometry().contains(e.position().toPoint()):
            self.close_anim()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close_anim()
