"""Automatic port forwarding (standard library only).

Modelled on what established programs do (miniupnpc / libtorrent / Syncthing / Windows' own NAT API):

1. UPnP IGD: SSDP M-SEARCH sent out of *every* local interface (VPN, Hyper-V or VirtualBox adapters
   otherwise swallow the multicast on Windows) plus straight to the default gateway, then the
   *valid* IGD is chosen like miniupnpc's UPNP_GetValidIGD: connected, with a routable external IP,
   preferring the default gateway. ``AddPortMapping`` with lease fallbacks; a stale mapping of our own
   (e.g. after this PC got a new IP) is replaced.
2. PCP / NAT-PMP (UDP 5351 on the gateway) for rules UPnP could not open; many routers that have
   UPnP off still answer these.
3. Windows only: the built-in UPnP NAT COM API (HNetCfg.NATUPnP), which goes through Windows' own
   SSDP service.

Also detects the default gateway and double NAT / CGNAT so the manual guide can give accurate advice.
"""

from __future__ import annotations

import ipaddress
import os
import platform
import re
import select
import socket
import struct
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
from . import proc

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

    def status(self) -> str:
        """"Connected", "Disconnected", ... or "" when the router does not say."""
        try:
            return self._soap("GetStatusInfo", {}, timeout=4).get("NewConnectionStatus", "")
        except UPnPError:
            return ""

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


def local_ipv4s() -> list[str]:
    """IPv4 addresses of this PC's network interfaces (best first: the one with the default route)."""
    ips: list[str] = []
    try:
        ips.append(_local_ip_towards("8.8.8.8"))      # UDP connect sends nothing; just picks the route
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    out = []
    for ip in ips:
        if ip not in out and not ip.startswith(("127.", "169.254.", "0.")):
            out.append(ip)
    return out


def _msearch(st: str, host: str = SSDP[0]) -> bytes:
    return (f"M-SEARCH * HTTP/1.1\r\nHOST: {host}:{SSDP[1]}\r\nMAN: \"ssdp:discover\"\r\n"
            f"MX: 2\r\nST: {st}\r\n\r\n").encode()


def discover(timeout: float = 3.0, gateway_ip: str = "") -> list[str]:
    """Device description URLs of gateways that answered the SSDP search.

    The search goes out of every local interface (like Syncthing / miniupnpc), and is also sent
    straight to the default gateway, which some routers answer when multicast is filtered."""
    socks: list[socket.socket] = []
    for ip in local_ipv4s() or ["0.0.0.0"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            if ip != "0.0.0.0":
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
                s.bind((ip, 0))
            s.setblocking(False)
            for st in SEARCH_TARGETS:
                s.sendto(_msearch(st), SSDP)
            socks.append(s)
        except OSError:
            continue
    if gateway_ip and socks:
        try:
            for st in SEARCH_TARGETS[:1] + SEARCH_TARGETS[2:3]:
                socks[0].sendto(_msearch(st, gateway_ip), (gateway_ip, SSDP[1]))
        except OSError:
            pass
    found: list[str] = []
    try:
        end = time.time() + timeout
        while socks and time.time() < end:
            ready, _w, _x = select.select(socks, [], [], min(0.3, max(0.0, end - time.time())))
            for s in ready:
                try:
                    data, _addr = s.recvfrom(4096)
                except OSError:
                    continue
                m = re.search(rb"(?im)^location:\s*(\S+)", data)
                if m:
                    loc = m.group(1).decode(errors="replace")
                    if loc not in found:
                        found.append(loc)
        return found
    finally:
        for s in socks:
            s.close()


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


def find_gateway(timeout: float = 3.0, log: Callable[[str], None] = lambda m: None) -> Optional[Gateway]:
    """The best IGD on the network, chosen like miniupnpc's UPNP_GetValidIGD: connected, with a routable
    external IP, preferring the default gateway (a mesh node or the ISP modem may answer too)."""
    gw_ip = default_gateway()
    best, best_score = None, -1
    for loc in discover(timeout, gw_ip)[:8]:
        try:
            gw = gateway_from_location(loc)
        except (OSError, ET.ParseError, ValueError):
            continue
        if not gw:
            continue
        score = 0
        status = gw.status()
        if status in ("", "Connected"):
            score += 4
        try:
            ext = gw.external_ip()
            if ext and not is_private(ext):
                score += 2
        except UPnPError:
            pass
        if gw.host == gw_ip:
            score += 3
        log(_("UPnP device {0} (status: {1})").format(gw.host, status or "?"))
        if score > best_score:
            best, best_score = gw, score
    return best


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
            out = proc.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Sort-Object RouteMetric | Select-Object -First 1).NextHop"],
                timeout=8).stdout.strip()
        elif system == "Darwin":
            out = proc.run(["route", "-n", "get", "default"], timeout=5).stdout
            m = re.search(r"gateway:\s*(\S+)", out)
            out = m.group(1) if m else ""
        else:
            out = proc.run(["ip", "route", "show", "default"], timeout=5).stdout
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
    methods: list = field(default_factory=list)      # ["UPnP", "PCP", "NAT-PMP", "Windows UPnP"]
    ext_ports: dict = field(default_factory=dict)    # "25565/TCP" -> external port, when the router chose another
    firewall: Optional[bool] = None                  # Windows Firewall rules added? (None: not tried)


DIRECT = "direct"          # methods entry when the PC has a public IP and no router is in between


def method_label(m: str) -> str:
    return _("public IP, no router") if m == DIRECT else m


def methods_text(methods: list) -> str:
    return ", ".join(method_label(m) for m in methods)


# ------------------------------------------------------------------ PCP / NAT-PMP (RFC 6887 / RFC 6886)
PMP_PORT = 5351
PCP_RESULTS = {1: "UNSUPP_VERSION", 2: "NOT_AUTHORIZED", 3: "MALFORMED_REQUEST", 4: "UNSUPP_OPCODE",
               5: "UNSUPP_OPTION", 6: "MALFORMED_OPTION", 7: "NETWORK_FAILURE", 8: "NO_RESOURCES",
               9: "UNSUPP_PROTOCOL", 10: "USER_EX_QUOTA", 11: "CANNOT_PROVIDE_EXTERNAL",
               12: "ADDRESS_MISMATCH", 13: "EXCESSIVE_REMOTE_PEERS"}
PMP_RESULTS = {1: "Unsupported version", 2: "Not authorized/refused", 3: "Network failure",
               4: "Out of resources", 5: "Unsupported opcode"}


class PmpError(Exception):
    pass


class PmpUnsupported(PmpError):
    """The gateway answered, but only speaks the older NAT-PMP."""


def _udp_request(host: str, payload: bytes, port: int = PMP_PORT, tries: int = 3, first: float = 0.25) -> bytes:
    """Send with the RFC's doubling retry timer; raises PmpError when nothing answers."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, port))
        wait = first
        for _i in range(tries):
            s.send(payload)
            s.settimeout(wait)
            try:
                return s.recv(1100)
            except (socket.timeout, ConnectionResetError):
                wait *= 2
        raise PmpError(_("No answer on UDP {0}").format(port))
    except OSError as e:
        raise PmpError(str(e)) from e
    finally:
        s.close()


def _v4mapped(ip: str) -> bytes:
    return b"\x00" * 10 + b"\xff\xff" + socket.inet_aton(ip)


def pcp_map(gw: str, local_ip: str, port: int, proto: str, lifetime: int = 7 * 86400,
            pmp_port: int = PMP_PORT) -> tuple[int, str, int]:
    """PCP MAP request. Returns (external port, external IP, granted lifetime)."""
    nonce = os.urandom(12)
    req = (struct.pack("!BBHI", 2, 1, 0, lifetime) + _v4mapped(local_ip) + nonce
           + struct.pack("!B3xHH", 6 if proto == "TCP" else 17, port, port) + _v4mapped("0.0.0.0"))
    d = _udp_request(gw, req, pmp_port)
    if len(d) >= 4 and d[0] == 0:
        raise PmpUnsupported("NAT-PMP only")
    if len(d) < 60 or d[0] != 2 or d[1] != 0x81:
        raise PmpError(_("Unexpected PCP answer"))
    if d[3] != 0:
        raise PmpError("PCP " + PCP_RESULTS.get(d[3], str(d[3])))
    if d[24:36] != nonce:
        raise PmpError(_("Unexpected PCP answer"))
    life = struct.unpack("!I", d[4:8])[0]
    eport = struct.unpack("!H", d[42:44])[0]
    eip = socket.inet_ntoa(d[56:60])
    return eport, eip, life


def natpmp_external_ip(gw: str, pmp_port: int = PMP_PORT) -> str:
    d = _udp_request(gw, b"\x00\x00", pmp_port)
    if len(d) >= 12 and d[0] == 0 and d[1] == 128 and struct.unpack("!H", d[2:4])[0] == 0:
        return socket.inet_ntoa(d[8:12])
    return ""


def natpmp_map(gw: str, port: int, proto: str, lifetime: int = 7 * 86400,
               pmp_port: int = PMP_PORT) -> tuple[int, int]:
    """NAT-PMP mapping. Returns (external port, granted lifetime). Lifetime 0 would delete it."""
    op = 1 if proto == "UDP" else 2
    d = _udp_request(gw, struct.pack("!BBHHHI", 0, op, 0, port, port, lifetime), pmp_port)
    if len(d) < 16:
        raise PmpError(_("Unexpected NAT-PMP answer"))
    _ver, rop, result, _epoch, _ip, eport, life = struct.unpack("!BBHIHHI", d[:16])
    if rop != 128 + op:
        raise PmpError(_("Unexpected NAT-PMP answer"))
    if result:
        raise PmpError("NAT-PMP: " + PMP_RESULTS.get(result, str(result)))
    return eport, life


# ------------------------------------------------------------------ Windows' own UPnP NAT API
def windows_com_map(rules: list[tuple[int, str]], local_ip: str, desc: str) -> dict[str, str]:
    """Add mappings through HNetCfg.NATUPnP (Windows' SSDP service). Returns {"25565/TCP": "OK" or error}."""
    if platform.system() != "Windows":
        return {}
    d = desc.replace("'", "")
    adds = "\n".join(
        f"try {{ $c.Add({p}, '{pr}', {p}, '{local_ip}', $true, '{d}') | Out-Null; '{p}/{pr} OK' }} "
        f"catch {{ '{p}/{pr} ' + $_.Exception.Message }}" for p, pr in rules)
    script = ("$n = New-Object -ComObject HNetCfg.NATUPnP\n$c = $null\n"
              # the collection is often null on the first try while Windows is still searching
              "for ($i = 0; $i -lt 4 -and $c -eq $null; $i++) { $c = $n.StaticPortMappingCollection; "
              "if ($c -eq $null) { Start-Sleep -Seconds 2 } }\n"
              "if ($c -eq $null) { 'NOGATEWAY'; exit 3 }\n" + adds)
    try:
        out = proc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", proc.PS_UTF8 + script],
                       timeout=40).stdout
    except (OSError, subprocess.SubprocessError) as e:
        return {f"{p}/{pr}": str(e) for p, pr in rules}
    if "NOGATEWAY" in out:
        return {f"{p}/{pr}": _("Windows found no UPnP router") for p, pr in rules}
    res = {}
    for line in out.splitlines():
        m = re.match(r"(\d+/(?:TCP|UDP)) (.*)", line.strip())
        if m:
            res[m.group(1)] = m.group(2).strip()
    return res


# ------------------------------------------------------------------ all together
def _upnp_add(gw: Gateway, port: int, proto: str, desc: str) -> str:
    """Add one mapping; returns "" on success or the last error."""
    last = ""
    for lease in (0, 604800, 86400, 3600):      # some routers only accept permanent, others only timed leases
        try:
            gw.add_mapping(port, proto, desc, lease)
            return ""
        except UPnPError as e:
            last = str(e)
            if "718" in last:
                break
    cur = gw.get_mapping(port, proto)
    if cur and cur.get("NewInternalClient") == gw.local_ip:
        return ""                                # already points at this PC (e.g. a re-install)
    if cur and cur.get("NewPortMappingDescription", "") == desc:
        try:                                     # our own old mapping to this PC's previous IP: replace it
            gw.delete_mapping(port, proto)
            gw.add_mapping(port, proto, desc, 0)
            return ""
        except UPnPError as e:
            last = str(e)
    return last


def forward_ports(rules: list[tuple[int, str]], desc: str = "Minecraft Server",
                  log: Callable[[str], None] = lambda s: None, gateway: Optional[Gateway] = None,
                  pmp: bool = True, windows_api: bool = True, pmp_port: int = PMP_PORT) -> ForwardResult:
    """Try to open every (port, protocol) rule on the router: UPnP, then PCP / NAT-PMP, then (Windows)
    the system's own UPnP API for whatever is still closed. Never raises."""
    res = ForwardResult(False)
    errors: dict[str, str] = {}
    left = list(rules)

    # 0. No router at all: this PC itself has a public IP (connected straight to the ISP line / modem in
    #    bridge mode). Nothing to forward; only the PC's firewall matters.
    try:
        lip = _local_ip_towards("8.8.8.8")
    except OSError:
        lip = ""
    if lip and not is_private(lip) and gateway is None:
        log(_("This PC has a public IP ({0}) and is connected to the internet directly, without a router. "
              "No port forwarding is needed; only the Windows firewall has to allow the ports.").format(lip))
        res = ForwardResult(True, gateway=default_gateway(), local_ip=lip, external_ip=lip,
                            opened=[f"{p}/{pr}" for p, pr in rules], methods=[DIRECT])
        return res

    # 1. UPnP IGD
    log(_("Searching for a UPnP router..."))
    try:
        gw = gateway or find_gateway(log=log)
    except OSError as e:
        gw = None
        errors["*"] = _("Network error: {0}").format(e)
    if gw:
        res.gateway, res.local_ip = gw.host, gw.local_ip
        log(_("Router found: {0} (this PC: {1})").format(gw.host, gw.local_ip))
        try:
            res.external_ip = gw.external_ip()
        except UPnPError as e:
            errors["ip"] = str(e)
        for port, proto in list(left):
            err = _upnp_add(gw, port, proto, desc)
            key = f"{port}/{proto}"
            if not err:
                res.opened.append(key)
                left.remove((port, proto))
                log(_("Opened {0}/{1}").format(port, proto) + " (UPnP)")
            else:
                errors[key] = err
                log(_("Failed {0}/{1}: {2}").format(port, proto, err))
        if len(left) < len(rules):
            res.methods.append("UPnP")
    else:
        errors.setdefault("*", _("No UPnP router found. UPnP may be turned off on the router."))
        log(errors["*"])

    # 2. PCP / NAT-PMP
    gw_ip = res.gateway or default_gateway()
    if left and pmp and gw_ip:
        lip = res.local_ip or _local_ip_towards(gw_ip)
        res.local_ip = res.local_ip or lip
        res.gateway = res.gateway or gw_ip
        log(_("Trying PCP / NAT-PMP on {0}...").format(gw_ip))
        mode = "PCP"
        for port, proto in list(left):
            key = f"{port}/{proto}"
            try:
                if mode == "PCP":
                    try:
                        eport, eip, life = pcp_map(gw_ip, lip, port, proto, pmp_port=pmp_port)
                        res.external_ip = res.external_ip or (eip if eip != "0.0.0.0" else "")
                    except PmpUnsupported:
                        mode = "NAT-PMP"
                if mode == "NAT-PMP":
                    eport, life = natpmp_map(gw_ip, port, proto, pmp_port=pmp_port)
                    if not res.external_ip:
                        try:
                            res.external_ip = natpmp_external_ip(gw_ip, pmp_port)
                        except PmpError:
                            pass
            except PmpError as e:
                errors[key] = errors.get(key) or str(e)
                log(_("Failed {0}/{1}: {2}").format(port, proto, e))
                if not str(e).startswith(("PCP", "NAT-PMP")):
                    break                         # nothing answers on 5351: don't wait for every rule
                continue
            res.opened.append(key)
            left.remove((port, proto))
            if eport != port:
                res.ext_ports[key] = eport
            if mode not in res.methods:
                res.methods.append(mode)
            log(_("Opened {0}/{1}").format(port, proto) + f" ({mode}, " +
                (_("external port {0}").format(eport) + ", " if eport != port else "") +
                _("{0} h lease").format(life // 3600) + ")")

    # 3. Windows' built-in UPnP NAT API
    if left and windows_api and platform.system() == "Windows":
        lip = res.local_ip or (local_ipv4s() or [""])[0]
        if lip:
            log(_("Trying Windows' UPnP service..."))
            out = windows_com_map(left, lip, desc)
            for port, proto in list(left):
                key = f"{port}/{proto}"
                msg = out.get(key, "")
                if msg == "OK":
                    res.opened.append(key)
                    left.remove((port, proto))
                    if "Windows UPnP" not in res.methods:
                        res.methods.append("Windows UPnP")
                    log(_("Opened {0}/{1}").format(port, proto) + " (Windows UPnP)")
                elif msg:
                    errors[key] = errors.get(key) or msg

    res.double_nat = bool(res.external_ip) and is_private(res.external_ip)
    res.ok = not left and not res.double_nat
    res.errors = [v if k in ("*", "ip") else f"{k}: {v}" for k, v in errors.items()
                  if k in ("*", "ip") or k.split("/")[0].isdigit() and (int(k.split("/")[0]), k.split("/")[1]) in left]
    if res.double_nat:
        res.errors.append(_("The router's external IP ({0}) is a private/CGNAT address. Your ISP or another "
                            "router sits in front, so players outside cannot connect even with forwarding.")
                          .format(res.external_ip))
    if res.ok:
        res.errors = []
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
