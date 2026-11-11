"""Port forwarding dialog: automatic UPnP attempt plus a manual guide filled in with this PC's values."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..core import upnp
from ..core.net import get_json
from ..i18n import _
from .overlay import Overlay
from .state import local_ip, run_async
from .widgets import ACCENT, DANGER, MUTED, OK, WARN, Button, Glass, label, wrap_label

# (brand, usual address, menu path). Menu names vary by model and firmware.
ROUTERS = [
    ("ipTIME", "192.168.0.1", _("Advanced Setup → NAT/Routing → Port Forwarding")),
    ("TP-Link", "192.168.0.1 / tplinkwifi.net", _("Advanced → NAT Forwarding → Virtual Servers")),
    ("ASUS", "192.168.50.1 / router.asus.com", _("WAN → Virtual Server / Port Forwarding")),
    ("NETGEAR", "routerlogin.net", _("Advanced → Advanced Setup → Port Forwarding / Port Triggering")),
    ("Linksys", "192.168.1.1", _("Security → Apps and Gaming → Single Port Forwarding")),
    ("KT", "172.30.1.254", _("NAT settings → Port forwarding")),
    ("SK broadband", "192.168.25.1", _("NAT settings → Port forwarding")),
    ("LG U+", "192.168.219.1", _("NAT settings → Port forwarding")),
]


def _card() -> tuple[Glass, QVBoxLayout]:
    g = Glass(radius=12, strength=10, frost=False)
    v = QVBoxLayout(g)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(6)
    return g, v


class PortGuide(Overlay):
    max_size = (780, 680)

    def __init__(self, win, st):
        super().__init__(win, _("Port forwarding"))
        self.st = st
        self.result: upnp.ForwardResult | None = None
        self.gateway = ""
        self.public_ip = ""
        self.busy = False
        self.body.addWidget(wrap_label(_("Players on the same router (Wi-Fi) can join already. For friends outside your "
                                         "network, the router has to forward the ports below to this PC."), "muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.v = QVBoxLayout(inner)
        self.v.setContentsMargins(0, 4, 8, 4)
        self.v.setSpacing(10)
        scroll.setWidget(inner)
        self.body.addWidget(scroll, 1)

        # automatic
        card, cv = _card()
        cv.addWidget(label(_("1. Automatic (UPnP)"), "h3"))
        self.auto_status = wrap_label("", "")
        self.auto_status.setTextFormat(Qt.TextFormat.RichText)
        cv.addWidget(self.auto_status)
        row = QHBoxLayout()
        self.auto_btn = Button(_("Try automatic forwarding"), "primary")
        self.auto_btn.clicked.connect(self.try_auto)
        row.addWidget(self.auto_btn)
        self.copy_btn = Button(_("Copy address for friends"))
        self.copy_btn.clicked.connect(self._copy)
        row.addWidget(self.copy_btn)
        row.addStretch(1)
        cv.addLayout(row)
        self.v.addWidget(card)

        # ports
        card, cv = _card()
        cv.addWidget(label(_("Ports to forward"), "h3"))
        self.ports_grid = QGridLayout()
        self.ports_grid.setHorizontalSpacing(18)
        self.ports_grid.setVerticalSpacing(4)
        cv.addLayout(self.ports_grid)
        self.v.addWidget(card)

        # manual
        card, cv = _card()
        cv.addWidget(label(_("2. Manual setup (if automatic fails)"), "h3"))
        self.steps = wrap_label("", "")
        self.steps.setTextFormat(Qt.TextFormat.RichText)
        self.steps.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cv.addWidget(self.steps)
        row = QHBoxLayout()
        self.router_btn = Button(_("Open router page"))
        self.router_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"http://{self.gateway}")))
        row.addWidget(self.router_btn)
        self.fw_btn = Button(_("Run open_firewall.bat"))
        self.fw_btn.clicked.connect(self._firewall)
        row.addWidget(self.fw_btn)
        test = Button(_("Test from outside"))
        test.clicked.connect(self._test)
        row.addWidget(test)
        row.addStretch(1)
        cv.addLayout(row)
        self.v.addWidget(card)

        # router menus
        card, cv = _card()
        cv.addWidget(label(_("Where to find it on common routers"), "h3"))
        cv.addWidget(wrap_label(_("Menu names differ by model and firmware. The address is the usual default; "
                                  "the one detected above is the right one for your network.")))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(3)
        for i, (brand, addr, path) in enumerate(ROUTERS):
            grid.addWidget(label(f"<b>{brand}</b>", "small"), i, 0)
            grid.addWidget(label(addr, "small"), i, 1)
            grid.addWidget(wrap_label(path), i, 2)
        grid.setColumnStretch(2, 1)
        cv.addLayout(grid)
        self.v.addWidget(card)

        # CGNAT
        card, cv = _card()
        cv.addWidget(label(_("Still can't connect?"), "h3"))
        self.cgnat = wrap_label(_(
            "• If the router's WAN IP is different from your public IP, or starts with 10., 100.64–100.127, "
            "172.16–172.31 or 192.168., you are behind a second router or your ISP's CGNAT. Forwarding then only "
            "works if you also forward on the upstream router (or set the modem to bridge mode), or ask your ISP for "
            "a public IP.\n• Some ISPs block incoming connections entirely. A tunnel service (e.g. playit.gg) works "
            "without port forwarding.\n• You usually cannot join your own public address from inside the same "
            "network. Use the local address yourself and test from outside (e.g. mobile data)."), "small")
        cv.addWidget(self.cgnat)
        self.v.addWidget(card)
        self.v.addStretch(1)

    # ---- values ----
    def rules(self):
        addons = [str(a.get("title", "")) if isinstance(a, dict) else str(getattr(a, "title", ""))
                  for a in self.st.addons]
        return upnp.port_rules(self.st.values, addons)

    def port(self) -> int:
        return int(self.st.values.get("server-port", 25565))

    def friend_address(self) -> str:
        ip = (self.result.external_ip if self.result and self.result.external_ip else "") or self.public_ip
        if not ip:
            return ""
        return ip if self.port() == 25565 else f"{ip}:{self.port()}"

    def set_result(self, res: upnp.ForwardResult | None) -> None:
        self.result = res
        if res and res.gateway:
            self.gateway = res.gateway

    def before_open(self):
        self._fill()
        if not self.gateway:
            run_async(lambda sig: upnp.default_gateway(), self._got_gateway, lambda m: None)
        if not self.public_ip:
            run_async(lambda sig: get_json("https://api.ipify.org?format=json", timeout=8).get("ip", ""),
                      self._got_public, lambda m: None)

    def _got_gateway(self, gw):
        if gw and not self.gateway:
            self.gateway = gw
            self._fill()

    def _got_public(self, ip):
        self.public_ip = str(ip or "")
        self._fill()

    # ---- rendering ----
    def _fill(self):
        while self.ports_grid.count():
            w = self.ports_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        rules = self.rules()
        opened = set(self.result.opened) if self.result else set()
        for i, (port, proto, why) in enumerate(rules):
            mark = f"<span style='color:{OK}'>✓</span>" if f"{port}/{proto}" in opened else "•"
            self.ports_grid.addWidget(label(f"{mark}  <b>{port}</b>"), i, 0)
            self.ports_grid.addWidget(label(proto, "muted"), i, 1)
            self.ports_grid.addWidget(wrap_label(why), i, 2)
        self.ports_grid.setColumnStretch(2, 1)

        r = self.result
        if self.busy:
            txt = f"<span style='color:{MUTED}'>{_('Asking the router…')}</span>"
        elif r is None:
            txt = _("Most home routers support UPnP. If it is enabled, this opens the ports for you.")
        elif r.ok:
            txt = (f"<span style='color:{OK}'>✓ {_('Ports opened automatically.')}</span> "
                   + _("Friends can join at <b>{0}</b>.").format(self.friend_address() or "?"))
        else:
            first = r.errors[0] if r.errors else _("Unknown error")
            done = (_(" Opened: {0}.").format(", ".join(r.opened)) if r.opened else "")
            color = WARN if r.opened else DANGER
            txt = f"<span style='color:{color}'>✕ {_('Automatic forwarding did not work.')}</span>{done}<br>" \
                  f"<span style='color:{MUTED}'>{first}</span><br>" + _("Follow the manual steps below.")
        if self.public_ip and r and r.external_ip and r.external_ip != self.public_ip:
            txt += "<br><span style='color:{0}'>{1}</span>".format(WARN, _(
                "The router reports {0}, but your public IP is {1}: there is another router or CGNAT in front."
            ).format(r.external_ip, self.public_ip))
        self.auto_status.setText(txt)
        self.auto_btn.setEnabled(not self.busy)
        self.copy_btn.setEnabled(bool(self.friend_address()))

        lip = (r.local_ip if r and r.local_ip else "") or local_ip()
        gw = self.gateway or "192.168.0.1"
        port = self.port()
        lines = "".join(f"<br>&nbsp;&nbsp;&nbsp;– {_('External port')} <b>{p}</b> → {_('internal port')} <b>{p}</b>, "
                        f"{_('protocol')} <b>{pr}</b>, {_('internal IP')} <b>{lip}</b>"
                        for p, pr, _why in rules)
        a = f"<span style='color:{ACCENT}'>"
        steps = [
            _("Open the router admin page: {0}http://{1}</span> in a browser. The login is often printed on a sticker "
              "on the router.").format(a, gw),
            _("Reserve this PC's IP {0}{1}</span> in the DHCP settings (\"DHCP reservation\" / \"static lease\"), so the "
              "rule keeps working after a reboot.").format(a, lip),
            _("Find \"Port Forwarding\" (also called Virtual Server, NAT or Port Mapping) and add:") + lines,
            _("Allow the server through the PC firewall: run open_firewall.bat in the server folder as administrator."),
            _("Start the server, then check from outside with \"Test from outside\" or have a friend join "
              "{0}{1}</span>.").format(a, self.friend_address() or _("your public IP") + ("" if port == 25565 else f":{port}")),
        ]
        self.steps.setText("<br>".join(f"<b>{i + 1}.</b> {s}" for i, s in enumerate(steps)))
        self.fw_btn.setVisible(os.name == "nt")

    # ---- actions ----
    def try_auto(self):
        if self.busy:
            return
        self.busy = True
        self._fill()
        rules = [(p, pr) for p, pr, _why in self.rules()]
        title = str(self.st.values.get("launch:title", "Minecraft Server"))[:40] or "Minecraft Server"
        run_async(lambda sig: upnp.forward_ports(rules, title), self._auto_done, self._auto_err)

    def _auto_done(self, res):
        self.busy = False
        self.set_result(res)
        self._fill()

    def _auto_err(self, msg):
        self.busy = False
        self.set_result(upnp.ForwardResult(False, errors=[msg]))
        self._fill()

    def _copy(self):
        if self.friend_address():
            QGuiApplication.clipboard().setText(self.friend_address())
            self.copy_btn.setText(_("Copied ✓"))

    def _firewall(self):
        bat = Path(self.st.folder).expanduser() / "open_firewall.bat"
        if bat.is_file():
            subprocess.Popen(["cmd", "/c", "start", "", str(bat)], cwd=str(bat.parent))

    def _test(self):
        addr = self.friend_address()
        QDesktopServices.openUrl(QUrl("https://mcsrvstat.us/server/" + addr if addr else "https://mcsrvstat.us/"))
