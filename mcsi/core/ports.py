"""Port checks shared by the setup pages and the summary."""

from __future__ import annotations

import socket

from ..i18n import _

MIN_PORT = 1024        # 0-1023 are reserved for system services (web, file sharing, remote desktop...)


def in_use(port: int) -> bool:
    """True when something on this PC already listens on the TCP port (e.g. another server)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def problems(values: dict) -> tuple[list[str], list[str]]:
    """(errors that block the install, warnings) for the port settings."""
    errors, warns = [], []
    port = int(values.get("server-port", 25565))
    named = [(_("Server port"), port)]
    if values.get("enable-rcon"):
        named.append((_("RCON port"), int(values.get("rcon.port", 25575))))
    if values.get("enable-query"):
        named.append((_("Query port"), int(values.get("query.port", 25565))))
    mgmt = int(values.get("management-server-port", 0) or 0)
    if mgmt:
        named.append((_("Management API port"), mgmt))
    for name, p in named:
        if not MIN_PORT <= p <= 65535:
            errors.append(_("{0} {1} is not allowed: use a number from {2} to 65535 (lower ports are reserved "
                            "for system services).").format(name, p, MIN_PORT))
    tcp = [(n, p) for n, p in named if n != _("Query port")]       # query is UDP, it may share the game port
    seen: dict[int, str] = {}
    for n, p in tcp:
        if p in seen:
            errors.append(_("{0} and {1} both use port {2}. Pick different numbers.").format(seen[p], n, p))
        seen[p] = n
    if MIN_PORT <= port <= 65535 and in_use(port):
        warns.append(_("Port {0} is already in use on this PC (another server still running?). The server "
                       "will not start until it is free.").format(port))
    return errors, warns
