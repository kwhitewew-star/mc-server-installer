"""App settings (⚙): a glass dialog over the window."""

from __future__ import annotations
from ..i18n import _

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from ..core.java import APP_DIR
from ..i18n import LANGUAGES, get_language
from .overlay import Overlay
from .widgets import ACCENT, Button, Glass, NoWheelCombo, Toggle, label, wrap_label

APP_DEFAULTS = {
    "skip_welcome": False,
    "remember": True,
    "base_folder": "",
    "first_run_default": True,
    "open_folder_after": False,
    "run_after": False,
    "transitions": True,
    "parallax": True,
    "particles": True,
    "server_anim": True,
    "hide_client_mods": True,
    "launcher_java": True,
    "language": "en",
}

# (key, title, description, group)
ITEMS = [
    ("skip_welcome", _("Skip the start screen"), _("Opens directly at 'Server type', skipping the setup mode screen (uses the last mode)."), _("Start")),
    ("remember", _("Remember last settings"), _("When off, every launch starts from defaults."), _("Start")),
    ("first_run_default", _("First run after install (default)"),
     _("When on, the server is started once after installing to create the world, apply game rules and ops, and verify it works. When off, only files are installed."), _("Install")),
    ("open_folder_after", _("Open the folder when done"), "", _("Install")),
    ("run_after", _("Start the server when done"), _("Runs start.bat in a new console window."), _("Install")),
    ("hide_client_mods", _("Hide client-only mods"), _("Hides mods that do nothing on a server (shaders, minimaps...) from search results."), _("Install")),
    ("launcher_java", _("Include the Minecraft Launcher's Java"), _("Lists the Java bundled with the Minecraft Launcher so the server can use it."), _("Install")),
    ("transitions", _("Page transition animation"), "", _("Display")),
    ("parallax", _("3D view follows the mouse"), "", _("Display")),
    ("particles", _("Particles"), "", _("Display")),
    ("server_anim", _("Server type animation"), _("A 3D animation for the chosen server (e.g. Paper's paper plane, CraftBukkit's lava bucket)"), _("Display")),
]


class SettingsOverlay(Overlay):
    """Translucent scrim over the whole window + a centered glass panel."""

    changed = pyqtSignal(str)          # changed key
    reset_all = pyqtSignal()
    fx_changed = pyqtSignal(str)
    restart_requested = pyqtSignal()

    def __init__(self, win, st):
        super().__init__(win, _("App settings"))
        self.st = st
        lay = self.body
        lay.addWidget(label(_("Changes how the installer itself behaves. Applied instantly and saved automatically."), "small", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 4, 8, 4)
        v.setSpacing(8)
        self.toggles: dict[str, Toggle] = {}
        v.addWidget(self._lang_row())
        last = None
        for key, title, desc, group in ITEMS:
            if group != last:
                h = label(group, "h3")
                h.setStyleSheet(f"color:{ACCENT}; padding-top:6px;")
                v.addWidget(h)
                last = group
            row = Glass(radius=12, strength=10, frost=False)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 9, 14, 9)
            tv = QVBoxLayout()
            tv.setSpacing(1)
            tv.addWidget(label(title, "h3"))
            if desc:
                tv.addWidget(wrap_label(desc))
            rl.addLayout(tv, 1)
            t = Toggle(bool(self.app(key)))
            t.toggled.connect(lambda on, k=key: self.set(k, on))
            rl.addWidget(t)
            self.toggles[key] = t
            v.addWidget(row)
            if key == "launcher_java":
                v.addWidget(self._folder_row())
            if key == "server_anim":
                v.addWidget(self._fx_row())
        v.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        b1 = Button(_("Open settings folder"))
        b1.clicked.connect(self._open_dir)
        b2 = Button(_("Reset all inputs"), "danger")
        b2.clicked.connect(self.reset_all.emit)
        bottom.addWidget(b1)
        bottom.addStretch(1)
        bottom.addWidget(b2)
        lay.addLayout(bottom)

    def app(self, key):
        return self.st.app.get(key, APP_DEFAULTS[key])

    def set(self, key, val):
        self.st.app[key] = val
        self.st.save()
        self.changed.emit(key)

    def _folder_row(self):
        row = Glass(radius=12, strength=10, frost=False)
        rl = QVBoxLayout(row)
        rl.setContentsMargins(14, 9, 14, 9)
        rl.addWidget(label(_("Default install location"), "h3"))
        rl.addWidget(label(_("Server folders are created here as '<type>-<version>'. Empty = Desktop\\MinecraftServers"), "small", True))
        h = QHBoxLayout()
        self.base = QLineEdit(self.app("base_folder"))
        self.base.setPlaceholderText(_("Desktop\\MinecraftServers"))
        self.base.editingFinished.connect(lambda: self.set("base_folder", self.base.text().strip()))
        h.addWidget(self.base, 1)
        b = Button(_("Browse"))
        b.clicked.connect(self._browse)
        h.addWidget(b)
        rl.addLayout(h)
        return row

    def _fx_row(self):
        row = Glass(radius=12, strength=10, frost=False)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 9, 14, 9)
        tv = QVBoxLayout()
        tv.addWidget(label(_("3D background quality"), "h3"))
        tv.addWidget(label(_("Switch to 'Normal' or 'Off' if it feels slow."), "small"))
        rl.addLayout(tv, 1)
        self.fx = NoWheelCombo()
        for k, t in (("high", _("High")), ("normal", _("Normal")), ("off", _("Off"))):
            self.fx.addItem(t, k)
        self.fx.setFixedWidth(150)
        self.fx.currentIndexChanged.connect(lambda i: self.fx_changed.emit(self.fx.itemData(i)))
        rl.addWidget(self.fx)
        return row

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, _("Default install location"), self.base.text() or "")
        if d:
            self.base.setText(d)
            self.set("base_folder", d)

    def _open_dir(self):
        from .state import open_path
        APP_DIR.mkdir(parents=True, exist_ok=True)
        open_path(str(APP_DIR))

    def _lang_row(self):
        row = Glass(radius=12, strength=10, frost=False)
        rl = QVBoxLayout(row)
        rl.setContentsMargins(14, 9, 14, 9)
        h = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(1)
        tv.addWidget(label("Language / 언어 / 言語 / 语言 / Idioma", "h3"))
        tv.addWidget(wrap_label(_("The installer restarts to switch languages.")))
        h.addLayout(tv, 1)
        self.lang = NoWheelCombo()
        for code, name in LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setFixedWidth(150)
        self.lang.setCurrentIndex(max(0, self.lang.findData(get_language())))
        self.lang.currentIndexChanged.connect(self._lang_changed)
        h.addWidget(self.lang)
        rl.addLayout(h)
        self.restart_row = QWidget()
        rr = QHBoxLayout(self.restart_row)
        rr.setContentsMargins(0, 4, 0, 0)
        rr.addWidget(wrap_label(_("Restart now to apply the new language?"), "muted"), 1)
        b = Button(_("Restart now"), "primary")
        b.clicked.connect(self.restart_requested.emit)
        rr.addWidget(b)
        self.restart_row.setVisible(False)
        rl.addWidget(self.restart_row)
        return row

    def _lang_changed(self, i):
        code = self.lang.itemData(i)
        self.set("language", code)
        self.restart_row.setVisible(code != get_language())

    def before_open(self):
        for k, t in self.toggles.items():
            t.blockSignals(True)
            t.setChecked(bool(self.app(k)))
            t.blockSignals(False)
        self.fx.blockSignals(True)
        self.fx.setCurrentIndex(max(0, self.fx.findData(self.st.fx)))
        self.fx.blockSignals(False)
