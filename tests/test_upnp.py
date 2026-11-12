"""UPnP port forwarding against a small fake IGD router served on localhost."""

import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mcsi.core import upnp

DEVICE = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0"><device>
 <deviceType>urn:schemas-upnp-org:device:InternetGatewayDevice:1</deviceType>
 <deviceList><device><deviceList><device><serviceList><service>
  <serviceType>{svc}</serviceType>
  <controlURL>/ctl/IPConn</controlURL>
 </service></serviceList></device></deviceList></device></deviceList>
</device></root>"""

FAULT = """<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>
<s:Fault><detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0"><errorCode>{code}</errorCode>
</UPnPError></detail></s:Fault></s:Body></s:Envelope>"""


class Router:
    def __init__(self, svc="urn:schemas-upnp-org:service:WANIPConnection:1", external="203.0.113.7",
                 reject_lease0=False, fail_code=None):
        self.svc, self.external = svc, external
        self.reject_lease0, self.fail_code = reject_lease0, fail_code
        self.mappings = {}
        router = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self._send(200, DEVICE.format(svc=router.svc))

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"])).decode()
                action = self.headers["SOAPAction"].strip('"').split("#")[1]
                arg = dict(re.findall(r"<(New\w+)>([^<]*)</New\w+>", body))
                if action == "GetExternalIPAddress":
                    return self._ok(action, f"<NewExternalIPAddress>{router.external}</NewExternalIPAddress>")
                if action == "AddPortMapping":
                    if router.fail_code:
                        return self._send(500, FAULT.format(code=router.fail_code))
                    old = router.mappings.get((arg["NewExternalPort"], arg["NewProtocol"]))
                    if old and old["NewInternalClient"] != arg["NewInternalClient"]:
                        return self._send(500, FAULT.format(code=718))
                    if router.reject_lease0 and arg["NewLeaseDuration"] == "0":
                        return self._send(500, FAULT.format(code=725))
                    router.mappings[(arg["NewExternalPort"], arg["NewProtocol"])] = arg
                    return self._ok(action, "")
                if action == "GetSpecificPortMappingEntry":
                    m = router.mappings.get((arg["NewExternalPort"], arg["NewProtocol"]))
                    if not m:
                        return self._send(500, FAULT.format(code=714))
                    return self._ok(action, f"<NewInternalClient>{m['NewInternalClient']}</NewInternalClient>"
                                            f"<NewPortMappingDescription>{m['NewPortMappingDescription']}"
                                            "</NewPortMappingDescription>")
                if action == "DeletePortMapping":
                    router.mappings.pop((arg["NewExternalPort"], arg["NewProtocol"]), None)
                    return self._ok(action, "")
                if action == "GetStatusInfo":
                    return self._ok(action, "<NewConnectionStatus>Connected</NewConnectionStatus>")
                self._send(500, FAULT.format(code=401))

            def _ok(self, action, inner):
                self._send(200, f'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                                f'<s:Body><u:{action}Response xmlns:u="{router.svc}">{inner}</u:{action}Response>'
                                f'</s:Body></s:Envelope>')

            def _send(self, code, text):
                data = text.encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.location = f"http://127.0.0.1:{self.server.server_port}/rootDesc.xml"

    def gateway(self):
        return upnp.gateway_from_location(self.location)

    def close(self):
        self.server.shutdown()


@pytest.fixture(autouse=True)
def private_lan(monkeypatch):
    """Pretend this PC sits behind a home router (the test machine may have any address)."""
    monkeypatch.setattr(upnp, "_local_ip_towards", lambda host: host if host.startswith("127.") else "192.168.0.23")


@pytest.fixture
def router():
    made = []

    def make(**kw):
        r = Router(**kw)
        made.append(r)
        return r
    yield make
    for r in made:
        r.close()


def test_parses_device_description(router):
    r = router(svc="urn:schemas-upnp-org:service:WANPPPConnection:1")
    gw = r.gateway()
    assert gw.control_url.endswith("/ctl/IPConn") and "WANPPPConnection" in gw.service
    assert gw.host == "127.0.0.1" and gw.local_ip == "127.0.0.1"


def test_forwards_all_rules(router):
    r = router()
    res = upnp.forward_ports([(25565, "TCP"), (19132, "UDP")], "MC <test> & co", gateway=r.gateway())
    assert res.ok and res.external_ip == "203.0.113.7" and not res.double_nat
    assert res.opened == ["25565/TCP", "19132/UDP"]
    assert r.mappings[("25565", "TCP")]["NewPortMappingDescription"] == "MC &lt;test&gt; &amp; co"


def test_falls_back_to_timed_lease(router):
    r = router(reject_lease0=True)
    res = upnp.forward_ports([(25565, "TCP")], gateway=r.gateway())
    assert res.ok and r.mappings[("25565", "TCP")]["NewLeaseDuration"] == "604800"


def test_reports_router_errors(router):
    r = router(fail_code=718)
    res = upnp.forward_ports([(25565, "TCP")], gateway=r.gateway())
    assert not res.ok and "718" in res.errors[0]


def test_detects_cgnat(router):
    r = router(external="100.72.1.5")
    res = upnp.forward_ports([(25565, "TCP")], gateway=r.gateway())
    assert res.double_nat and not res.ok and res.opened == ["25565/TCP"]


def test_port_rules():
    rules = upnp.port_rules({"server-port": 25570, "enable-query": True, "query.port": 25570},
                            ["Geyser", "Simple Voice Chat", "LuckPerms"])
    assert [(p, pr) for p, pr, _w in rules] == [(25570, "TCP"), (25570, "UDP"), (19132, "UDP"), (24454, "UDP")]
    assert len(upnp.port_rules({}, [])) == 1


def test_private_ranges():
    assert upnp.is_private("192.168.0.1") and upnp.is_private("100.100.0.1") and upnp.is_private("10.1.2.3")
    assert not upnp.is_private("8.8.8.8") and not upnp.is_private("203.0.113.7")


# ---------------------------------------------------------------- 718: our own stale mapping is replaced
def _old(port, client, desc):
    return {"NewExternalPort": str(port), "NewProtocol": "TCP", "NewInternalClient": client,
            "NewPortMappingDescription": desc}


def test_replaces_own_stale_mapping(router):
    r = router()
    gw = r.gateway()
    r.mappings[("25565", "TCP")] = _old(25565, "192.168.0.99", "My Server")       # this PC's old IP
    res = upnp.forward_ports([(25565, "TCP")], "My Server", gateway=gw, pmp=False, windows_api=False)
    assert res.ok and r.mappings[("25565", "TCP")]["NewInternalClient"] == gw.local_ip


def test_keeps_someone_elses_mapping(router):
    r = router()
    gw = r.gateway()
    r.mappings[("25565", "TCP")] = _old(25565, "192.168.0.50", "Other PC")
    res = upnp.forward_ports([(25565, "TCP")], "My Server", gateway=gw, pmp=False, windows_api=False)
    assert not res.ok and r.mappings[("25565", "TCP")]["NewInternalClient"] == "192.168.0.50"
    assert any("718" in e for e in res.errors)


# ---------------------------------------------------------------- PCP / NAT-PMP against a fake gateway
class PmpServer:
    """Answers PCP MAP (or only NAT-PMP when pcp=False) on a localhost UDP port."""

    def __init__(self, pcp=True, ext_port_offset=0):
        import socket
        import struct
        self.pcp, self.off = pcp, ext_port_offset
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.maps = []
        self.struct = struct
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        st = self.struct
        while True:
            try:
                d, addr = self.sock.recvfrom(1100)
            except OSError:
                return
            if d[0] == 2:
                if not self.pcp:                     # NAT-PMP-only gateway: "unsupported version"
                    self.sock.sendto(st.pack("!BBHI", 0, 128, 1, 0), addr)
                    continue
                nonce, proto = d[24:36], d[36]
                iport = st.unpack("!H", d[40:42])[0]
                self.maps.append(("PCP", iport, proto))
                resp = (st.pack("!BBBBII", 2, 0x81, 0, 0, 7200, 1) + bytes(12) + nonce
                        + st.pack("!B3xHH", proto, iport, iport + self.off)
                        + bytes(10) + b"\xff\xff" + bytes([203, 0, 113, 9]))
                self.sock.sendto(resp, addr)
            elif d[1] == 0:
                self.sock.sendto(st.pack("!BBHI", 0, 128, 0, 1) + bytes([203, 0, 113, 9]), addr)
            else:
                _v, op, _r, iport, eport, life = st.unpack("!BBHHHI", d[:12])
                self.maps.append(("PMP", iport, op))
                self.sock.sendto(st.pack("!BBHIHHI", 0, 128 + op, 0, 1, iport, eport + self.off, 3600), addr)

    def close(self):
        self.sock.close()


@pytest.fixture
def pmp():
    made = []

    def make(**kw):
        s = PmpServer(**kw)
        made.append(s)
        return s
    yield make
    for s in made:
        s.close()


def test_pcp_map(pmp):
    s = pmp()
    eport, eip, life = upnp.pcp_map("127.0.0.1", "192.168.0.23", 25565, "TCP", pmp_port=s.port)
    assert (eport, eip, life) == (25565, "203.0.113.9", 7200) and s.maps == [("PCP", 25565, 6)]


def test_natpmp_map(pmp):
    s = pmp(pcp=False)
    assert upnp.natpmp_map("127.0.0.1", 19132, "UDP", pmp_port=s.port) == (19132, 3600)
    assert upnp.natpmp_external_ip("127.0.0.1", s.port) == "203.0.113.9"


def test_falls_back_to_pcp_when_upnp_fails(router, pmp, monkeypatch):
    r = router(fail_code=606)
    s = pmp()
    monkeypatch.setattr(upnp, "default_gateway", lambda: "127.0.0.1")
    res = upnp.forward_ports([(25565, "TCP"), (19132, "UDP")], gateway=r.gateway(), windows_api=False,
                             pmp_port=s.port)
    assert res.ok and res.methods == ["PCP"] and sorted(res.opened) == ["19132/UDP", "25565/TCP"]
    assert res.external_ip == "203.0.113.7"


def test_natpmp_only_gateway_and_remapped_port(pmp, monkeypatch):
    s = pmp(pcp=False, ext_port_offset=1)
    monkeypatch.setattr(upnp, "find_gateway", lambda **k: None)
    monkeypatch.setattr(upnp, "default_gateway", lambda: "127.0.0.1")
    res = upnp.forward_ports([(25565, "TCP")], windows_api=False, pmp_port=s.port)
    assert res.ok and res.methods == ["NAT-PMP"] and res.ext_ports == {"25565/TCP": 25566}
    assert res.external_ip == "203.0.113.9"


def test_nothing_answers_is_quick(monkeypatch):
    import time
    monkeypatch.setattr(upnp, "find_gateway", lambda **k: None)
    monkeypatch.setattr(upnp, "default_gateway", lambda: "127.0.0.1")
    t = time.time()
    res = upnp.forward_ports([(25565, "TCP"), (19132, "UDP"), (24454, "UDP")], windows_api=False, pmp_port=9)
    assert not res.ok and time.time() - t < 6         # gives up on 5351 after the first rule


def test_local_ipv4s_has_no_loopback():
    assert all(not ip.startswith("127.") for ip in upnp.local_ipv4s())


def test_public_ip_needs_no_forwarding(monkeypatch):
    monkeypatch.setattr(upnp, "_local_ip_towards", lambda host: "112.167.115.20")
    monkeypatch.setattr(upnp, "default_gateway", lambda: "112.167.115.1")
    monkeypatch.setattr(upnp, "find_gateway", lambda **k: (_ for _ in ()).throw(AssertionError("no search")))
    res = upnp.forward_ports([(19832, "TCP")], windows_api=False)
    assert res.ok and res.methods == [upnp.DIRECT] and res.external_ip == "112.167.115.20"
    assert res.opened == ["19832/TCP"] and "router" in upnp.methods_text(res.methods)
