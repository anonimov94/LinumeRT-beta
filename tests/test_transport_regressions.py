"""Regresje lokalnego odbioru transportów. SPDX-License-Identifier: GPL-2.0-or-later"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from linumert_headless.transport.rest import create_app


@pytest.mark.parametrize("headers", [{"host": "evil.example"}, {"origin": "https://evil.example"}])
def test_ws_checks_host_and_origin(app, headers):
    with TestClient(create_app(app), base_url="http://localhost") as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("ws://localhost/ws", headers=headers):
                pass
        assert error.value.code == 4403


def test_ipv6_host_with_port_and_explicit_origin(app):
    with TestClient(create_app(app, allow_origins=("http://localhost:9000",)),
                    base_url="http://localhost") as client:
        assert client.get("/api/v1/health", headers={"host": "[::1]:8080"}).status_code == 200
        assert client.get("/api/v1/health", headers={"origin": "https://evil"}).status_code == 403
        with client.websocket_connect(
                "ws://localhost/ws", headers={"origin": "http://localhost:9000"}) as ws:
            assert ws.receive_json()["type"] == "hello"


@pytest.mark.parametrize("message", [
    {"command": "machine.state", "params": [1]},
    {"command": "machine.state", "params": "wrong"},
    {"hello": True},
    {"id": {}, "command": "machine.state"},
])
def test_bad_ws_message_keeps_connection_alive(app, message):
    with TestClient(create_app(app), base_url="http://localhost") as client:
        with client.websocket_connect("ws://localhost/ws") as ws:
            ws.receive_json()
            ws.send_json(message)
            assert ws.receive_json()["error"]["code"] == "invalid_request"
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"


def test_ws_cannot_replace_motion_session(app, ready_machine):
    with TestClient(create_app(app), base_url="http://localhost") as client:
        with client.websocket_connect("ws://localhost/ws") as ws:
            session = ws.receive_json()["session"]
            ws.send_json({"command": "machine.jog", "params": {
                "axis": "X", "speed": 1, "session": "other"}})
            assert ws.receive_json()["ok"]
            assert app.sessions.active_jog() == {"X": session}
        assert not app.backend.machine._jog


def test_application_stop_closes_backend_and_stops_motion(app, ready_machine):
    app.backend.start()
    worker = app.backend._thread
    ready_machine("machine.jog", {"axis": "X", "speed": 1})
    app.stop()
    assert not worker.is_alive()
    assert not app.backend.machine._jog
    app.stop()  # cleanup is idempotent


def test_login_uses_separate_random_session_and_enforces_contract_roles(app):
    with TestClient(create_app(app, token="api", extra_hosts=("testserver",)),
                    headers={"X-LRT-Token": "api"}) as client:
        def call(command, params=None, **kwargs):
            return client.post("/api/v1/call", json={"command": command, "params": params or {}},
                               **kwargs)
        assert call("access.set_pin", {"role": "serwis", "pin": "1234"}).status_code == 200
        assert call("machine.estop_reset").status_code == 403
        first = call("access.login", {"role": "serwis", "pin": "1234"}).json()["result"]
        second = call("access.login", {"role": "serwis", "pin": "1234"}).json()["result"]
        assert first["token"] != second["token"]
        assert len(first["token"]) >= 32
        headers = {"X-LRT-Session": first["token"]}
        assert call("machine.estop_reset", headers=headers).status_code == 200
        assert call("access.logout", headers=headers).status_code == 200
        assert call("machine.estop_reset", headers=headers).status_code == 403
        assert call("machine.estop").status_code == 200


def test_repeated_bad_logins_are_locked(app):
    from linumert_headless.errors import ApiError, PermissionDenied
    app.call("access.set_pin", {"role": "serwis", "pin": "1234"})
    for _ in range(5):
        with pytest.raises(ApiError):
            app.call("access.login", {"role": "serwis", "pin": "wrong"})
    with pytest.raises(PermissionDenied, match="zablokowane"):
        app.call("access.login", {"role": "serwis", "pin": "1234"})


def test_validator_error_is_json_serializable(app):
    with TestClient(create_app(app, extra_hosts=("testserver",))) as client:
        response = client.post("/api/v1/call", json={"command": "machine.jog",
                                                    "params": {"axis": "X", "speed": 100}})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"


def test_contract_schema_references_resolve(app):
    for operation in app.contract.export()["operations"]:
        for kind in ("request", "result"):
            schema = operation[kind]
            def check(node, schema=schema):
                if isinstance(node, dict):
                    if "$ref" in node:
                        target = schema
                        for part in node["$ref"].removeprefix("#/").split("/"):
                            target = target[part]
                    for value in node.values():
                        check(value)
                elif isinstance(node, list):
                    for value in node:
                        check(value)
            check(schema)


def test_browser_preflight_and_authenticated_role_request(app):
    with TestClient(create_app(app, token="api", extra_hosts=("testserver",),
                               allow_origins=("http://localhost:9000",))) as client:
        response = client.options("/api/v1/call", headers={
            "Origin": "http://localhost:9000", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-LRT-Token,X-LRT-Session,Content-Type"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:9000"
        response = client.post("/api/v1/call", headers={"Origin": "http://localhost:9000",
                               "X-LRT-Token": "api"}, json={"command": "machine.state"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:9000"


def test_rate_limited_get_returns_api_error(app):
    with TestClient(create_app(app, extra_hosts=("testserver",))) as client:
        app.sessions._limiter.rate = 0
        app.sessions._limiter._tokens = 0
        response = client.get("/api/v1/health")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"


def test_incremental_jog_stops_on_websocket_disconnect(app, ready_machine):
    with TestClient(create_app(app, extra_hosts=("testserver",))) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"command": "machine.jog_increment", "params": {
                "axis": "X", "speed": -1, "distance": 10}})
            assert ws.receive_json()["ok"]
            app.backend.advance(0.1)
            assert app.backend.snapshot().axis("X").position < 0
        assert not app.backend.machine._jog


def test_keepalive_does_not_repeat_increment(app, ready_machine):
    ready_machine("machine.jog_increment", {"axis": "X", "speed": 1, "distance": 0.1})
    app.backend.advance(0.1)
    ready_machine("machine.jog_keepalive")
    app.backend.advance(0.1)
    assert app.backend.snapshot().axis("X").position == pytest.approx(0.1)
