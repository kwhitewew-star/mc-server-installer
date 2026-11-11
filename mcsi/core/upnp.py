"""Automatic port forwarding through UPnP IGD (standard library only).

Flow: SSDP discovery (multicast M-SEARCH) -> device description XML -> WANIPConnection /
WANPPPConnection control URL -> SOAP ``AddPortMapping``.  Also detects the default gateway and
double NAT / CGNAT so the manual guide can give accurate advice.
"""

from __future__ import annotations

import ipaddress
import platform
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape

from ..i18n import _

SSDP = ("239.255.255.250", 1900)
SEARCH_TARGETS = [
    "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
    "urn:schemas-upnp-org:device:InternetGatewayDevice:2",
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
]
WAN_SERVICES = ("WANIPConnection", "WANPPPConnection")
NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0

# Never send LAN requests through a system HTTP proxy.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class UPnPError(Exception):
    pass


UPNP_ERRORS = {
    "402": _("Invalid arguments"),
    "501": _("Action failed"),
    "606": _("Action not authorized (UPnP may be in read-only mode on the router)"),
    "714": _("No such mapping entry"),
    "715": _("Wildcard source IP not supported"),
    "716": _("Wildcard external port not supported"),
    "718": _("Port is already forwarded to another device"),
    "724": _("External and internal ports must be the same"),
    "725": _("Router only supports permanent mappings"),
}


@dataclass
class Gateway:
    location: str
    control_url: str
    service: str
    local_ip: str

    @property
    def host(self) -> str:
        return urlparse(self.location).hostname or ""

    def _soap(self, action: str, args: dict[str, str], timeout: float = 6) -> dict[str, str]:
        body = "".join(f"<{k}>{escape(v)}</{k}>" for k, v in args.items())
        envelope = ('<?xml version="1.0"?>'
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
                    f'<u:{action} xmlns:u="{self.service}">{body}</u:{action}>'
                    '</s:Body></s:Envelope>').encode("utf-8")
        req = urllib.request.Request(self.control_url, data=envelope, method="POST", headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{self.service}#{action}"',
        })
        try:
            with _opener.open(req, timeout=timeout) as resp:
                xml = resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            code = re.search(r"<errorCode>(\d+)</errorCode>", raw)
            c = code.group(1) if code else str(e.code)
            raise UPnPError(f"UPnP {c}: {UPNP_ERRORS.get(c) or _('Router refused the request')}") from e
        except OSError as e:
            raise UPnPError(_("Could not reach the router: {0}").format(e)) from e
        out = {}
        for el in ET.fromstring(xml).iter():
            tag = el.tag.split("}")[-1]
            if el.text and not list(el):
                out[tag] = el.text.strip()
        return out

    def external_ip(self) -> str:
        return self._soap("GetExternalIPAddress", {}).get("NewExternalIPAddress", "")

    def add_mapping(self, port: int, proto: str, desc: str, lease: int = 0) -> None:
        self._soap("AddPortMapping", {
            "NewRemoteHost": "", "NewExternalPort": str(port), "NewProtocol": proto,
            "NewInternalPort": str(port), "NewInternalClient": self.local_ip, "NewEnabled": "1",
            "NewPortMappingDescription": desc, "NewLeaseDuration": str(lease)})

    def get_mapping(self, port: int, proto: str) -> Optional[dict]:
        try:
            return self._soap("GetSpecificPortMappingEntry", {
                "NewRemoteHost": "", "NewExternalPort": str(port), "NewProtocol": proto})
        except UPnPError:
            return None

    def delete_mapping(self, port: int, proto: str) -> None:
        self._soap("DeletePortMapping", {"NewRemoteHost": "", "NewExternalPort": str(port), "NewProtocol": proto})


def discover(timeout: float = 3.0) -> list[str]:
    """Return device description URLs of gateways that answered the SSDP search."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(0.4)
    try:
        for st in SEARCH_TARGETS:
            msg = (f"M-SEARCH * HTTP/1.1\r\nHOST: {SSDP[0]}:{SSDP[1]}\r\nMAN: \"ssdp:discover\"\r\n"
                   f"MX: 2\r\nST: {st}\r\n\r\n").encode()
            sock.sendto(msg, SSDP)
        found: list[str] = []
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, _addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            m = re.search(rb"(?im)^location:\s*(\S+)", data)
            if m:
                loc = m.group(1).decode(errors="replace")
                if loc not in found:
                    found.append(loc)
        return found
    finally:
        sock.close()


def _local_ip_towards(host: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 1900))
        return s.getsockname()[0]
    finally:
        s.close()


def gateway_from_location(location: str) -> Optional[Gateway]:
    with _opener.open(location, timeout=5) as resp:
        root = ET.fromstring(resp.read())
    base = location
    for el in root.iter():
        if el.tag.endswith("URLBase") and el.text:
            base = el.text.strip()
    for svc in root.iter():
        if not svc.tag.endswith("service"):
            continue
        fields = {c.tag.split("}")[-1]: (c.text or "").strip() for c in svc}
        stype = fields.get("serviceType", "")
        if any(w in stype for w in WAN_SERVICES) and fields.get("controlURL"):
            host = urlparse(location).hostname or ""
            return Gateway(location, urljoin(base, fields["controlURL"]), stype, _local_ip_towards(host))
    return None


def find_gateway(timeout: float = 3.0) -> Optional[Gateway]:
    for loc in discover(timeout):
        try:
            gw = gateway_from_location(loc)
            if gw:
                return gw
        except (OSError, ET.ParseError):
            continue
    return None


# Addresses a router's WAN side can have when it is NOT directly on the internet.
_NON_PUBLIC = [ipaddress.ip_network(n) for n in
               ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "169.254.0.0/16", "127.0.0.0/8",
                "0.0.0.0/8")]


def is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(a in n for n in _NON_PUBLIC) if a.version == 4 else a.is_private


def default_gateway() -> str:
    """Best-effort default gateway IP (used by the manual guide)."""
    try:
        system = platform.system()
        if system == "Windows":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Sort-Object RouteMetric | Select-Object -First 1).NextHop"],
                capture_output=True, text=True, timeout=8, creationflags=NO_WINDOW).stdout.strip()
        elif system == "Darwin":
            out = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"gateway:\s*(\S+)", out)
            out = m.group(1) if m else ""
        else:
            out = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"default via (\S+)", out)
            out = m.group(1) if m else ""
        ipaddress.ip_address(out)
        return out
    except Exception:  # noqa: BLE001
        return ""


@dataclass
class ForwardResult:
    ok: bool
    gateway: str = ""
    local_ip: str = ""
    external_ip: str = ""
    double_nat: bool = False
    opened: list = field(default_factory=list)       # ["25565/TCP", ...]
    errors: list = field(default_factory=list)


def forward_ports(rules: list[tuple[int, str]], desc: str = "Minecraft Server",
                  log: Callable[[str], None] = lambda s: None, gateway: Optional[Gateway] = None) -> ForwardResult:
    """Try to open every (port, protocol) rule on the router. Never raises."""
    log(_("Searching for a UPnP router..."))
    try:
        gw = gateway or find_gateway()
    except OSError as e:
        return ForwardResult(False, errors=[_("Network error: {0}").format(e)])
    if not gw:
        return ForwardResult(False, errors=[_("No UPnP router found. UPnP may be turned off on the router.")])
    res = ForwardResult(False, gateway=gw.host, local_ip=gw.local_ip)
    log(_("Router found: {0} (this PC: {1})").format(gw.host, gw.local_ip))
    try:
        res.external_ip = gw.external_ip()
        res.double_nat = is_private(res.external_ip)
    except UPnPError as e:
        res.errors.append(str(e))
    for port, proto in rules:
        done, last = False, ""
        for lease in (0, 604800):           # some routers only accept permanent, others only timed leases
            try:
                gw.add_mapping(port, proto, desc, lease)
                done = True
                break
            except UPnPError as e:
                last = str(e)
        if not done:                         # 718: maybe it already points at this PC (e.g. a re-install)
            cur = gw.get_mapping(port, proto)
            done = bool(cur and cur.get("NewInternalClient") == gw.local_ip)
        if done:
            res.opened.append(f"{port}/{proto}")
            log(_("Opened {0}/{1}").format(port, proto))
        else:
            res.errors.append(f"{port}/{proto}: {last}")
            log(_("Failed {0}/{1}: {2}").format(port, proto, last))
    res.ok = len(res.opened) == len(rules) and not res.double_nat
    if res.double_nat:
        res.errors.append(_("The router's external IP ({0}) is a private/CGNAT address. Your ISP or another "
                            "router sits in front, so players outside cannot connect even with forwarding.")
                          .format(res.external_ip))
    return res


def port_rules(values: dict, addon_titles: list[str]) -> list[tuple[int, str, str]]:
    """Ports the server actually needs to expose: (port, protocol, reason)."""
    port = int(values.get("server-port", 25565))
    rules = [(port, "TCP", _("Java Edition players"))]
    if values.get("enable-query"):
        q = int(values.get("query.port", 25565))
        rules.append((q, "UDP", _("Query (server list tools)")))
    if any("geyser" in t.lower() for t in addon_titles):
        rules.append((19132, "UDP", _("Bedrock Edition players (Geyser)")))
    if any("simple voice chat" in t.lower() or t.lower() == "voicechat" for t in addon_titles):
        rules.append((24454, "UDP", _("Simple Voice Chat")))
    seen, out = set(), []
    for r in rules:
        if (r[0], r[1]) not in seen:
            seen.add((r[0], r[1]))
            out.append(r)
    return out
