"""Project icons loaded from the web (Modrinth), rounded like on the site, cached in memory and on disk."""

from __future__ import annotations

import hashlib
import time

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget

from ..core.java import APP_DIR
from ..core.net import get_bytes
from .state import icon_pool, run_async

DISK = APP_DIR / "cache" / "icons"
DISK_DAYS = 7
_mem: dict[str, QImage] = {}
_waiting: dict[str, list] = {}


def _disk_path(url: str):
    return DISK / (hashlib.sha1(url.encode()).hexdigest() + ".img")


def _fetch(url: str) -> bytes:
    f = _disk_path(url)
    try:
        if f.is_file() and time.time() - f.stat().st_mtime < DISK_DAYS * 86400:
            return f.read_bytes()
    except OSError:
        pass
    data = get_bytes(url, timeout=10, cache_sec=3600, retries=1)
    try:
        DISK.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    except OSError:
        pass
    return data


def load(url: str, cb) -> None:
    """Call cb(QImage) on the main thread once the icon is there (right away if it's cached)."""
    if not url:
        return
    if url in _mem:
        cb(_mem[url])
        return
    if url in _waiting:
        _waiting[url].append(cb)
        return
    _waiting[url] = [cb]

    def ok(data):
        img = QImage()
        if not img.loadFromData(data):
            _waiting.pop(url, None)
            return
        if img.width() > 256 or img.height() > 256:          # some packs ship 1024px icons
            img = img.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        _mem[url] = img
        for f in _waiting.pop(url, []):
            try:
                f(img)
            except RuntimeError:      # the widget was deleted meanwhile
                pass

    run_async(lambda sig: _fetch(url), ok, lambda m: _waiting.pop(url, None), pool=icon_pool())


class RemoteIcon(QWidget):
    """Square icon with rounded corners. Shows the first letter on the project's colour until the image loads."""

    def __init__(self, url: str = "", text: str = "", size: int = 42, radius: float | None = None,
                 color: int = 0, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.radius = size * 0.24 if radius is None else radius
        self.text = (text.strip()[:1] or "?").upper()
        self.color = QColor(color) if color else QColor(255, 255, 255, 26)
        self.img: QImage | None = None
        self._scaled: QPixmap | None = None
        self.url = ""
        self.set_url(url)

    def set_url(self, url: str, text: str | None = None, color: int | None = None):
        if text is not None:
            self.text = (text.strip()[:1] or "?").upper()
        if color is not None:
            self.color = QColor(color) if color else QColor(255, 255, 255, 26)
        self.url = url or ""
        self.img = None
        self._scaled = None
        self.update()
        if self.url:
            want = self.url
            load(want, lambda img: self._got(want, img))

    def _got(self, url, img):
        if url != self.url:
            return
        self.img = img
        self._scaled = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.setClipPath(path)
        if self.img is not None:
            dpr = self.devicePixelRatioF()
            if self._scaled is None or abs(self._scaled.devicePixelRatio() - dpr) > 0.01:
                pm = QPixmap.fromImage(self.img.scaled(int(self.width() * dpr), int(self.height() * dpr),
                                                       Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                       Qt.TransformationMode.SmoothTransformation))
                pm.setDevicePixelRatio(dpr)
                self._scaled = pm
            pm = self._scaled
            x = (self.width() - pm.width() / pm.devicePixelRatio()) / 2
            y = (self.height() - pm.height() / pm.devicePixelRatio()) / 2
            p.fillRect(r, QColor(255, 255, 255, 18))         # behind transparent icons
            p.drawPixmap(int(x), int(y), pm)
        else:
            c = QColor(self.color)
            if c.alpha() == 255:
                c.setAlpha(150)
            p.fillRect(r, c)
            f = QFont(self.font())
            f.setPixelSize(max(10, int(self.height() * 0.42)))
            f.setWeight(QFont.Weight.ExtraBold)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, 230))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text)
        p.setClipping(False)
        p.setPen(QColor(255, 255, 255, 40))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), self.radius, self.radius)
