"""Walk through every step offscreen with fake data, save screenshots and check for layout overflow.

Usage:  python scripts/screenshots.py [language] [--out DIR]
Needs no network, Java or GPU (the 3D background is disabled; the 2D fallback is used).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ap = argparse.ArgumentParser()
ap.add_argument("lang", nargs="?", default="en")
ap.add_argument("--out", default="")
ap.add_argument("--size", default="1200x780")
args = ap.parse_args()

from mcsi import i18n  # noqa: E402

i18n.set_language(args.lang)

import fake_api  # noqa: E402

fake_api.install()

from PyQt6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from mcsi.core import upnp  # noqa: E402
from mcsi.core.java import JavaInfo  # noqa: E402
from mcsi.ui import pages_addons, pages_setup, port_guide, state  # noqa: E402

pages_addons.get_bytes = lambda *a, **k: b""
pages_setup.find_javas = lambda: [
    JavaInfo("C:/Program Files/Eclipse Adoptium/jdk-25/bin/java.exe", 25, "25.0.1", "Temurin"),
    JavaInfo("C:/Program Files/Java/jdk-21/bin/java.exe", 21, "21.0.5", "Oracle")]
port_guide.get_json = lambda url, timeout=0: {"ip": "203.0.113.7"}
upnp.default_gateway = lambda: "192.168.0.1"
state.CONFIG = Path(tempfile.mkdtemp()) / "config.json"
state.CONFIG.write_text('{"fx": "off", "app": {"language": "%s"}}' % args.lang, encoding="utf-8")

from mcsi.ui.main_window import MainWindow  # noqa: E402
from mcsi.ui.widgets import pick_font, qss  # noqa: E402

app = QApplication(sys.argv)
font = pick_font()
app.setFont(QFont(font, 10))
app.setStyleSheet(qss(font))
w = MainWindow()
W, H = (int(x) for x in args.size.split("x"))
w.resize(W, H)
w.show()
OUT = Path(args.out or ROOT / "docs" / "screenshots" / args.lang)
OUT.mkdir(parents=True, exist_ok=True)
overflow = []


def wait(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def check(widget, name):
    for sa in widget.findChildren(QScrollArea):
        if sa.isVisible() and sa.widget() and sa.widget().width() > sa.viewport().width() + 1:
            overflow.append(f"{name}: viewport {sa.viewport().width()} < content {sa.widget().width()}")


def shot(name, widget=None):
    wait(200)
    img = QImage(w.size(), QImage.Format.Format_ARGB32)
    img.fill(QColor("#0b1020"))
    p = QPainter(img)
    w.render(p)
    p.end()
    img.save(str(OUT / f"{name}.png"))
    check(widget or w, name)


wait(300)
w.pages["welcome"].cards["standard"].click()
shot("01_welcome")
w.go_next(); wait(600)
w.pages["server"].cards["paper"].click(); wait(100)
shot("02_server")
w.go_next(); wait(1000)
shot("03_version")
w.go_next(); wait(900)
shot("04_addons")
w.go_next(); wait(1000)
shot("05_resource")
for key in ("props", "rules", "manage"):
    w.go_next(); wait(700)
    pg = w.pages[key]
    pg.show_all.setChecked(True); wait(200)
    shot(f"06_{key}")
w.go_next(); wait(700)
w.pages["summary"].eula.setChecked(True); wait(200)
shot("07_summary")

done = w.pages["done"]
w.go(w.steps.index("done")); wait(500)
fwd = upnp.ForwardResult(False, gateway="192.168.0.1", local_ip="192.168.0.23", external_ip="203.0.113.7",
                         errors=["UPnP 606: " + upnp.UPNP_ERRORS["606"]])
w.ports.set_result(fwd)
done.show_result(True, "", ["Paper 26.3 build #30"], fwd)
shot("08_done")
w.ports.open_anim(); wait(600)
shot("09_port_guide", w.ports)
for i in range(12):                      # the picture guide, step by step
    w.ports._go_step(i); wait(150)
    w.ports.pic.grab().save(str(OUT / f"09_port_step{i + 1}.png"))
w.ports.close_anim(); wait(400)
w.open_settings(); wait(600)
shot("10_settings", w.settings)
w.settings.close_anim(); wait(400)
print(f"[{args.lang}] screenshots -> {OUT}")
print("overflow:", overflow or "none")
w.close()
sys.exit(1 if overflow else 0)
