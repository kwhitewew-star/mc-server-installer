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
                    if router.reject_lease0 and arg["NewLeaseDuration"] == "0":
                        return self._send(500, FAULT.format(code=725))
                    router.mappings[(arg["NewExternalPort"], arg["NewProtocol"])] = arg
                    return self._ok(action, "")
                if action == "GetSpecificPortMappingEntry":
                    m = router.mappings.get((arg["NewExternalPort"], arg["NewProtocol"]))
                    if not m:
                        return self._send(500, FAULT.format(code=714))
                    return self._ok(action, f"<NewInternalClient>{m['NewInternalClient']}</NewInternalClient>")
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
