"""OpenGL 3D glass background widget. On failure it emits `failed` and the app falls back to the 2D background."""

from __future__ import annotations
from ..i18n import _

import colorsys
import ctypes
import math
import time
import traceback
from typing import Callable

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QSurfaceFormat
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from .anims import ANIM_BURST, ANIM_CENTER, ANIM_DUR, ANIM_ID, DEFAULT_DUR
from .shaders import COMPOSITE_FS, FULLSCREEN_VS, PARTICLE_FS, PARTICLE_VS, SCENE_FS
from ..core.java import APP_DIR

def gl_text(value) -> str:
    """Turn whatever PyOpenGL returns for a GL string into str.

    Depending on the PyOpenGL version and platform this is bytes, str, a ctypes char array or a
    ctypes c_byte array (seen on Windows with PyOpenGL 3.1.10), possibly with trailing NULs.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.split("\0", 1)[0]
    if not isinstance(value, (bytes, bytearray)):
        try:
            value = bytes(value)                     # ctypes arrays of c_char / c_byte / c_ubyte
        except ValueError:                           # c_byte holds negative numbers for non-ASCII bytes
            value = bytes(b & 0xFF for b in value)
        except TypeError:
            value = bytes(ctypes.string_at(ctypes.addressof(value)))
    return bytes(value).split(b"\0", 1)[0].decode("utf-8", errors="replace")


QUALITY = {
    "high": {"scale": 0.75, "steps": 140, "particles": 1400, "blur": 0.9},
    "normal": {"scale": 0.5, "steps": 96, "particles": 800, "blur": 0.4},
}

# object shape per step: 0 sphere, 1 block, 2 torus, 3 gem, 4 twisted pillar
STEP_SHAPE = {"welcome": 0, "server": 1, "version": 2, "resource": 3, "props": 1, "rules": 4,
              "manage": 3, "summary": 0, "install": 2, "done": 0}
STEP_POS = {"welcome": (1.3, -0.05, 0.0, 1.2), "install": (0.55, 0.05, 0.0, 1.05),
            "done": (-0.05, 0.1, 0.0, 1.15)}
DEFAULT_POS = (1.65, 0.05, 0.4, 1.0)


def set_default_format() -> None:
    f = QSurfaceFormat()
    f.setVersion(3, 3)
    f.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    f.setSwapInterval(1)
    f.setDepthBufferSize(0)
    QSurfaceFormat.setDefaultFormat(f)


def theme(accent: str) -> tuple:
    c = QColor(accent)
    h, s, v = colorsys.rgb_to_hsv(c.redF(), c.greenF(), c.blueF())
    c1 = colorsys.hsv_to_rgb(h, min(1, s * 1.05), 1.0)
    c2 = colorsys.hsv_to_rgb((h + 0.12) % 1, min(1, s * 0.9), 1.0)
    c3 = colorsys.hsv_to_rgb((h + 0.55) % 1, min(1, s * 0.8), 0.85)
    return c1, c2, c3


class Smooth:
    def __init__(self, v):
        self.v = list(v) if isinstance(v, (tuple, list)) else v
        self.t = self.v

    def step(self, k: float):
        if isinstance(self.v, list):
            self.v = [a + (b - a) * k for a, b in zip(self.v, self.t)]
        else:
            self.v += (self.t - self.v) * k
        return self.v


class GLBackground(QOpenGLWidget):
    failed = pyqtSignal(str)
    lowered = pyqtSignal(str)

    def __init__(self, parent, rects_provider: Callable[[], list], quality: str = "high"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.rects_provider = rects_provider
        self.quality = quality if quality in QUALITY else "high"
        self.ok = False
        self.dead = False
        self.t0 = time.perf_counter()
        self.last = self.t0
        self.spin = 0.0
        self.c = [Smooth(c) for c in theme("#2dd4bf")]
        self.pos = Smooth(DEFAULT_POS)
        self.energy = Smooth(0.0)
        self.progress = Smooth(0.0)
        self.flash = 0.0
        self.flash_col = (1.0, 1.0, 1.0)
        self.burst = -1.0
        self.dir = Smooth(1.0)
        self.shape_a, self.shape_b, self.morph = 0.0, 0.0, 1.0
        self.mouse = Smooth((0.0, 0.0))
        self.parallax = True
        self.particles = True
        self.anim_on = True
        self.anim = 0
        self.anim_key = ""
        self.anim_t = 0.0
        self.anim_dur = DEFAULT_DUR
        self.glass_vis = Smooth(1.0)
        self.reveal = Smooth(0.0)
        self.burst_world = None
        self.fbo = self.tex = 0
        self.fbo_size = (0, 0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._frame)
        self.timer.start(16)
        self.fps = 0.0
        self._frames = 0
        self._fps_t = self.t0
        self._slow = 0

    def _frame(self):
        w = self.window()
        if w is not None and w.isMinimized():
            return
        self.update()

    # ---------------------------------------------------------------- State control (called by the app)
    def set_step(self, key: str) -> None:
        shape = float(STEP_SHAPE.get(key, 0))
        if shape != self.shape_b:
            self.shape_a = self.shape_b if self.morph > 0.5 else self.shape_a
            self.shape_b = shape
            self.morph = 0.0
        self.pos.t = list(STEP_POS.get(key, DEFAULT_POS))
        if key not in ("install", "done"):
            self.energy.t = 0.0
            self.dir.t = 1.0

    def set_accent(self, accent: str) -> None:
        for s, c in zip(self.c, theme(accent)):
            s.t = list(c)

    def set_installing(self, progress: float) -> None:
        self.energy.t = 1.0
        self.progress.t = max(0.0, min(1.0, progress))

    def set_result(self, ok: bool) -> None:
        self.energy.t = 0.25 if ok else 0.05
        self.progress.t = 0.0
        self.flash = 1.0
        if ok:
            self.flash_col = (0.3, 1.0, 0.65)
            self.burst = 0.0
            self.set_accent("#34d399")
            self.dir.t = 1.0
        else:
            self.flash_col = (1.0, 0.25, 0.3)
            self.set_accent("#fb7185")
            self.dir.t = -1.0

    def play_anim(self, key: str) -> None:
        """Play the server type's signature animation from the start."""
        if not self.anim_on or key not in ANIM_ID:
            return
        self.anim = ANIM_ID[key]
        self.anim_key = key
        self.anim_t = 0.0
        self.anim_dur = ANIM_DUR.get(key, DEFAULT_DUR)
        self.glass_vis.t = 0.0
        self.reveal.t = 1.0
        self._burst_done = False

    def set_quality(self, q: str) -> None:
        if q in QUALITY:
            self.quality = q
            self.fbo_size = (0, 0)

    # ---------------------------------------------------------------- GL
    def _fail(self, where: str) -> None:
        msg = f"{where}: {traceback.format_exc()}"
        self.dead = True
        self.timer.stop()
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            (APP_DIR / "gl_error.log").write_text(msg, encoding="utf-8")
        except OSError:
            pass
        QTimer.singleShot(0, lambda: self.failed.emit(msg))

    def _compile(self, vs: str, fs: str) -> int:
        from OpenGL import GL
        prog = GL.glCreateProgram()
        for src, kind in ((vs, GL.GL_VERTEX_SHADER), (fs, GL.GL_FRAGMENT_SHADER)):
            sh = GL.glCreateShader(kind)
            GL.glShaderSource(sh, src)
            GL.glCompileShader(sh)
            if not GL.glGetShaderiv(sh, GL.GL_COMPILE_STATUS):
                raise RuntimeError(_("Shader compile failed:\n") + gl_text(GL.glGetShaderInfoLog(sh)))
            GL.glAttachShader(prog, sh)
        GL.glLinkProgram(prog)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            raise RuntimeError(_("Shader link failed:\n") + gl_text(GL.glGetProgramInfoLog(prog)))
        return prog

    def initializeGL(self):  # noqa: N802
        try:
            from OpenGL import GL
            self.GL = GL
            self.vao = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(self.vao)
            self.p_scene = self._compile(FULLSCREEN_VS, SCENE_FS)
            self.p_part = self._compile(PARTICLE_VS, PARTICLE_FS)
            self.p_comp = self._compile(FULLSCREEN_VS, COMPOSITE_FS)
            self.loc = {}
            for name, prog in (("s", self.p_scene), ("p", self.p_part), ("c", self.p_comp)):
                n = GL.glGetProgramiv(prog, GL.GL_ACTIVE_UNIFORMS)
                for i in range(n):
                    uname = gl_text(GL.glGetActiveUniform(prog, i)[0]).split("[")[0]
                    self.loc[(name, uname)] = GL.glGetUniformLocation(prog, uname)
            self.renderer = gl_text(GL.glGetString(GL.GL_RENDERER))
            self.ok = True
        except Exception:
            self._fail("initializeGL")

    def _ensure_fbo(self, w: int, h: int) -> None:
        GL = self.GL
        s = QUALITY[self.quality]["scale"]
        size = (max(16, int(w * s)), max(16, int(h * s)))
        if size == self.fbo_size and self.fbo:
            return
        if self.fbo:
            GL.glDeleteFramebuffers(1, [self.fbo])
            GL.glDeleteTextures([self.tex])
        self.tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA16F, size[0], size[1], 0, GL.GL_RGBA, GL.GL_FLOAT, None)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        self.fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self.tex, 0)
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(_("Could not create the framebuffer"))
        self.fbo_size = size

    def _u(self, prog: str, name: str):
        return self.loc.get((prog, name), -1)

    def _tick(self, dt: float) -> None:
        k = 1 - math.exp(-dt * 3.0)
        for s in self.c:
            s.step(1 - math.exp(-dt * 1.8))
        self.pos.step(1 - math.exp(-dt * 2.2))
        self.energy.step(k)
        self.progress.step(1 - math.exp(-dt * 4.0))
        self.dir.step(1 - math.exp(-dt * 1.5))
        self.morph = min(1.0, self.morph + dt / 0.9)
        if self.morph >= 1.0:
            self.shape_a = self.shape_b
        self.flash = max(0.0, self.flash - dt * 1.2)
        if self.anim:
            prev = self.anim_t
            self.anim_t += dt / self.anim_dur
            b = ANIM_BURST.get(self.anim_key)
            if b and prev < b[0] <= self.anim_t:
                self.burst = 0.0
                self.burst_world = tuple(ANIM_CENTER[i] + b[1][i] for i in range(3))
            if self.anim_t >= 0.86:
                self.glass_vis.t = 1.0
                self.reveal.t = 0.0
            if self.anim_t >= 1.0:
                self.anim = 0
        self.glass_vis.step(1 - math.exp(-dt * 5.0))
        self.reveal.step(1 - math.exp(-dt * 4.0))
        if self.burst >= 0:
            self.burst += dt / 2.2
            if self.burst > 1:
                self.burst = -1.0
                self.burst_world = None
        self.spin += dt * (0.35 + 2.4 * self.energy.v)
        win = self.window()
        p = win.mapFromGlobal(QCursor.pos()) if win else QPoint(0, 0)
        w, h = max(1, win.width()), max(1, win.height())
        mx = max(-1.0, min(1.0, p.x() / w * 2 - 1))
        my = max(-1.0, min(1.0, 1 - p.y() / h * 2))
        self.mouse.t = [mx, my] if self.parallax else [0.0, 0.0]
        self.mouse.step(1 - math.exp(-dt * 2.5))

    def paintGL(self):  # noqa: N802
        if not self.ok or self.dead:
            return
        try:
            self._paint()
        except Exception:
            self._fail("paintGL")

    def _paint(self) -> None:
        GL = self.GL
        now = time.perf_counter()
        dt = min(0.1, now - self.last)
        self.last = now
        self._tick(dt)
        self._frames += 1
        if now - self._fps_t > 1:
            self.fps = self._frames / (now - self._fps_t)
            self._frames, self._fps_t = 0, now
            # lower quality automatically when too slow (below 25 fps for 3 s)
            self._slow = self._slow + 1 if self.fps < 25 else 0
            if self._slow >= 3 and self.quality == "high":
                self._slow = 0
                self.set_quality("normal")
                QTimer.singleShot(0, lambda: self.lowered.emit("normal"))
        t = now - self.t0
        dpr = self.devicePixelRatioF()
        W, H = int(self.width() * dpr), int(self.height() * dpr)
        q = QUALITY[self.quality]
        GL.glBindVertexArray(self.vao)
        self._ensure_fbo(W, H)
        sw, sh = self.fbo_size
        c1, c2, c3 = (s.v for s in self.c)

        # 1) 3D scene
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glViewport(0, 0, sw, sh)
        GL.glDisable(GL.GL_BLEND)
        GL.glUseProgram(self.p_scene)
        u = lambda n: self._u("s", n)  # noqa: E731
        GL.glUniform2f(u("uRes"), sw, sh)
        GL.glUniform1f(u("uTime"), t)
        GL.glUniform2f(u("uMouse"), *self.mouse.v)
        GL.glUniform3f(u("uC1"), *c1)
        GL.glUniform3f(u("uC2"), *c2)
        GL.glUniform3f(u("uC3"), *c3)
        GL.glUniform1f(u("uShapeA"), self.shape_a)
        GL.glUniform1f(u("uShapeB"), self.shape_b)
        GL.glUniform1f(u("uMorph"), self.morph)
        GL.glUniform1f(u("uEnergy"), self.energy.v)
        GL.glUniform1f(u("uProgress"), self.progress.v)
        GL.glUniform1f(u("uFlash"), self.flash)
        GL.glUniform3f(u("uFlashCol"), *self.flash_col)
        px, py, pz, ps = self.pos.v
        GL.glUniform3f(u("uObj"), px, py, pz)
        GL.glUniform1f(u("uScale"), ps * (1 + 0.04 * math.sin(t * 2.2) * self.energy.v))
        GL.glUniform1i(u("uSteps"), q["steps"])
        GL.glUniform1f(u("uSpin"), self.spin)
        GL.glUniform1i(u("uAnim"), int(self.anim))
        GL.glUniform1f(u("uAT"), min(1.0, self.anim_t))
        GL.glUniform1f(u("uGlassVis"), max(0.0, min(1.0, self.glass_vis.v)))
        GL.glUniform3f(u("uAC"), *ANIM_CENTER)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)

        # 2) particles (additive blending)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
        GL.glEnable(GL.GL_PROGRAM_POINT_SIZE)
        GL.glUseProgram(self.p_part)
        u = lambda n: self._u("p", n)  # noqa: E731
        GL.glUniform1f(u("uTime"), t)
        GL.glUniform1f(u("uEnergy"), self.energy.v)
        GL.glUniform1f(u("uBurst"), self.burst)
        GL.glUniform1f(u("uDir"), 1.0 if self.dir.v >= 0 else -1.0)
        GL.glUniform1f(u("uPx"), sw / 900.0 * 1.4)
        GL.glUniform2f(u("uRes"), sw, sh)
        GL.glUniform2f(u("uMouse"), *self.mouse.v)
        aspect = sh / sw
        bx, by, bz = self.burst_world if self.burst_world else (px, py, pz)
        cam = 5.2 + bz
        GL.glUniform2f(u("uCenter"), (bx - self.mouse.v[0] * 0.25) * 1.55 / cam * 2 * aspect,
                       (by - self.mouse.v[1] * 0.15) * 1.55 / cam * 2)
        GL.glUniform3f(u("uC1"), *c1)
        GL.glUniform3f(u("uC2"), *c2)
        if self.particles:
            GL.glDrawArrays(GL.GL_POINTS, 0, q["particles"])
        GL.glDisable(GL.GL_BLEND)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)

        # 3) composite glass panels -> screen
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.defaultFramebufferObject())
        GL.glViewport(0, 0, W, H)
        GL.glUseProgram(self.p_comp)
        u = lambda n: self._u("c", n)  # noqa: E731
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glUniform1i(u("uScene"), 0)
        GL.glUniform2f(u("uRes"), W, H)
        GL.glUniform2f(u("uSceneRes"), sw, sh)
        GL.glUniform1f(u("uTime"), t)
        GL.glUniform2f(u("uMouse"), *self.mouse.v)
        GL.glUniform3f(u("uC1"), *c1)
        GL.glUniform1f(u("uBlur"), q["blur"])
        GL.glUniform1f(u("uReveal"), max(0.0, min(1.0, self.reveal.v)))
        rects = self.rects_provider()[:16]
        flat, rads = [], []
        for x, y, w, h, r in rects:
            flat += [x * dpr, H - (y + h) * dpr, w * dpr, h * dpr]
            rads.append(r * dpr)
        n = len(rects)
        GL.glUniform1i(u("uN"), n)
        if n:
            GL.glUniform4fv(u("uRect"), n, (ctypes.c_float * len(flat))(*flat))
            GL.glUniform1fv(u("uRad"), n, (ctypes.c_float * n)(*rads))
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        GL.glBindVertexArray(0)
        GL.glUseProgram(0)
