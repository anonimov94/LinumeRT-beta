"""Transport socket JSON-lines (TCP i Unix).

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import json
import socket
import sys
import time

import pytest

from linumert_headless.transport.socket import SocketClient, SocketServer


@pytest.fixture
def server(app):
    srv = SocketServer(app, port=0).start()
    yield srv
    srv.stop()


def test_wywolanie_operacji_przez_tcp(server) -> None:
    client = SocketClient(*server.address)
    try:
        assert client.hello["type"] == "hello"
        assert client.call("system.info")["gui"] is False
        client.send({"type": "ping"})
        assert client.read() == {"type": "pong"}
    finally:
        client.close()


def test_blad_operacji_ma_kod(server) -> None:
    client = SocketClient(*server.address)
    try:
        with pytest.raises(RuntimeError, match="not_found"):
            client.call("nie.ma")
        client.send({"id": 7, "command": "machine.jog", "params": []})
        assert client.read()["error"]["code"] == "invalid_request"
    finally:
        client.close()


def test_niepoprawny_json_nie_zrywa_polaczenia(server) -> None:
    sock = socket.create_connection(server.address, timeout=3)
    f = sock.makefile("rwb")
    f.readline()
    f.write(b"to nie json\n[1]\n")
    f.flush()
    assert json.loads(f.readline())["ok"] is False
    assert json.loads(f.readline())["ok"] is False
    f.write(b'{"type":"ping"}\n')
    f.flush()
    assert json.loads(f.readline()) == {"type": "pong"}
    sock.close()


def test_token_jest_wymagany(app) -> None:
    srv = SocketServer(app, port=0, token="sekret").start()
    try:
        client = SocketClient(*srv.address)
        assert client.hello["auth_required"] is True
        with pytest.raises(RuntimeError, match="unauthorized"):
            client.call("system.info")
        client.close()
        ok = SocketClient(*srv.address, token="sekret")
        assert ok.call("system.info")["gui"] is False
        ok.close()
        bad = SocketClient(*srv.address)
        bad.send({"type": "auth", "token": "zly"})
        assert bad.read()["error"]["code"] == "unauthorized"
        bad.close()
    finally:
        srv.stop()


def test_tcp_poza_localhost_bez_tokenu_odmowa(app) -> None:
    with pytest.raises(ValueError):
        SocketServer(app, host="0.0.0.0", port=0)


@pytest.mark.skipif(sys.platform == "win32", reason="gniazda Unix")
def test_gniazdo_unix(app, tmp_path) -> None:
    path = tmp_path / "lrt.sock"
    srv = SocketServer(app, unix=path).start()
    try:
        assert oct(path.stat().st_mode & 0o777) == "0o600"
        client = SocketClient(unix=str(path))
        assert client.call("system.health")["ok"] is True
        client.close()
    finally:
        srv.stop()
    assert not path.exists()


def test_push_stanu_po_subskrypcji(app, server) -> None:
    client = SocketClient(*server.address)
    try:
        client.send({"type": "subscribe", "topics": ["machine"]})
        assert client.read()["type"] == "subscribed"
        app.hub.publish("machine", {"marker": time.time()})
        message = client.read()
        assert message["type"] == "state" and "machine" in message["topics"]
    finally:
        client.close()


def test_rozlaczenie_zatrzymuje_jog(app, server, ready_machine) -> None:
    client = SocketClient(*server.address)
    client.call("machine.jog", axis="X", speed=10)
    assert app.sessions.active_jog()
    client.close()
    for _ in range(50):
        if not app.sessions.active_jog():
            break
        time.sleep(0.05)
    assert not app.sessions.active_jog()
