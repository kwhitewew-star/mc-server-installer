import socket

from mcsi.core import ports, schema


def vals(**kw):
    v = schema.defaults()
    v.update(kw)
    return v


def test_low_and_high_ports_are_errors():
    assert ports.problems(vals(**{"server-port": 80}))[0]
    assert ports.problems(vals(**{"server-port": 1023}))[0]
    assert ports.problems(vals(**{"server-port": 70000}))[0]
    assert not ports.problems(vals(**{"server-port": 1024}))[0]


def test_schema_limits():
    assert schema.BY_KEY["server-port"].min == 1024 and schema.BY_KEY["rcon.port"].min == 1024


def test_rcon_clash_but_query_may_share():
    assert ports.problems(vals(**{"enable-rcon": True, "rcon.port": 25565}))[0]
    assert not ports.problems(vals(**{"enable-query": True, "query.port": 25565}))[0]


def test_port_in_use_is_a_warning():
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    s.listen()
    try:
        errs, warns = ports.problems(vals(**{"server-port": s.getsockname()[1]}))
        assert not errs and warns
    finally:
        s.close()
