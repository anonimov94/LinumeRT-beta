"""Transport socket (JSON-lines): TCP albo gniazdo Unix, bez FastAPI i bez asyncio.

SPDX-License-Identifier: GPL-2.0-or-later

Najprostszy sposób, żeby cokolwiek (skrypt, mały model językowy, GUI w C++/Rust, ``nc``)
rozmawiało z aplikacją: **jedna linia = jeden obiekt JSON**, zakończona ``\\n``.

Protokół jest tym samym, co w WebSocket (``transport/ws.py``) — te same wiadomości:

- klient → serwer ``{"id", "command", "params"}``  → ``{"id", "ok", "result"|"error"}``
- ``{"id", "method": "state.get"}``                → pełna migawka stanu
- ``{"type": "ping"}``                             → ``{"type": "pong"}``
- ``{"type": "hello", "topics": [..]}``            → wybór tematów push (None = wszystkie)
- ``{"type": "subscribe"}`` / ``{"type": "unsubscribe"}`` — włącza/wyłącza push stanu;
  push to ``{"type": "state", "version", "topics"}`` (domyślnie wyłączony: odpowiedzi
  nie mieszają się z asynchronicznym ruchem).

Uwierzytelnienie: gdy serwer ma token, pierwsza wiadomość musi zawierać ``"token"``
(``{"type": "auth", "token": "..."}``) albo każde polecenie niesie ``"token"``. Gniazdo
Unix dziedziczy uprawnienia pliku (0600) i token nie jest wymagany.

Rozłączenie klienta zatrzymuje jego jogi (deadman), tak samo jak w WebSocket.
"""

from __future__ import annotations

import contextlib
import hmac
import json
import logging
import os
import queue
import socket
import socketserver
import threading
from pathlib import Path
from typing import Any

from ..app import Application
from ..errors import ApiError
from ..schema import SCHEMA_VERSION

log = logging.getLogger("linumert.transport.socket")

MAX_LINE = 1 << 20          # 1 MiB na wiadomość — chroni przed zalaniem pamięci
PUSH_HZ = 20.0
JOG_COMMANDS = {"machine.jog", "machine.jog_increment", "machine.jog_keepalive"}


class _Handler(socketserver.StreamRequestHandler):
    server: SocketServer

    def handle(self) -> None:  # pragma: no cover - ścieżka pokryta testami integracyjnymi
        self.server.serve_connection(self.rfile, self.wfile)


class SocketServer:
    """Serwer JSON-lines; ``port=0`` wybiera wolny port, ``unix`` uruchamia gniazdo Unix."""

    def __init__(self, app: Application, *, host: str = "127.0.0.1", port: int = 0,
                 unix: Path | None = None, token: str = "", push_hz: float = PUSH_HZ):
        self.app = app
        self.token = token
        self.push_hz = push_hz
        self.unix = unix
        if unix is not None:
            with contextlib.suppress(FileNotFoundError):
                unix.unlink()
            unix.parent.mkdir(parents=True, exist_ok=True)
            self._srv: socketserver.BaseServer = _ThreadingUnix(str(unix), _Handler)
            os.chmod(unix, 0o600)
        else:
            if host not in {"127.0.0.1", "localhost", "::1"} and not token:
                raise ValueError("socket TCP poza localhost wymaga tokenu")
            self._srv = _ThreadingTcp((host, port), _Handler)
        self._srv.serve_connection = self.serve_connection  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> Any:
        return self._srv.server_address

    def start(self) -> SocketServer:
        self._thread = threading.Thread(target=self._srv.serve_forever, name="lrt-socket",
                                        kwargs={"poll_interval": 0.1}, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.unix is not None:
            with contextlib.suppress(OSError):
                self.unix.unlink()

    # ---- jedno połączenie ----------------------------------------------------
    def serve_connection(self, rfile: Any, wfile: Any) -> None:
        session = self.app.sessions.open()
        lock = threading.Lock()
        outbox: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=256)
        state = {"token": "", "authed": not self.token or self.unix is not None,
                 "push": False, "wanted": None}
        stop = threading.Event()

        def send(obj: dict[str, Any]) -> None:
            data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            with lock:
                wfile.write(data)
                wfile.flush()

        def on_change(topic: str, payload: dict[str, Any], version: int) -> None:
            wanted = state["wanted"]
            if not state["push"] or (wanted is not None and topic not in wanted):
                return
            with contextlib.suppress(queue.Full):
                outbox.put_nowait({"type": "state", "version": version,
                                   "topics": {topic: payload}})

        def pusher() -> None:
            period = 1.0 / self.push_hz
            while not stop.wait(period):
                try:
                    message = outbox.get_nowait()
                except queue.Empty:
                    continue
                topics = dict(message["topics"])
                version = message["version"]
                while True:
                    try:
                        extra = outbox.get_nowait()
                    except queue.Empty:
                        break
                    topics.update(extra["topics"])
                    version = max(version, extra["version"])
                try:
                    send({"type": "state", "version": version, "topics": topics})
                except OSError:
                    return

        unsubscribe = self.app.hub.subscribe(on_change)
        threading.Thread(target=pusher, name="lrt-socket-push", daemon=True).start()
        try:
            send({"type": "hello", "session": session, "schema": SCHEMA_VERSION,
                  "version": self.app.hub.version, "auth_required": not state["authed"]})
            while True:
                raw = rfile.readline(MAX_LINE + 1)
                if not raw:
                    break
                if len(raw) > MAX_LINE:
                    send(_bad(None, "wiadomość dłuższa niż 1 MiB"))
                    break
                line = raw.strip()
                if not line:
                    continue
                send(self._dispatch(line, session, state))
        except (OSError, ValueError):
            pass
        except Exception:
            log.exception("połączenie socket zakończone błędem")
        finally:
            stop.set()
            unsubscribe()
            for axis in self.app.sessions.close(session):
                try:
                    self.app.call("machine.jog_stop", {"axis": axis}, channel="socket")
                except Exception:
                    log.warning("stop jogu po rozłączeniu %s nie powiódł się", axis,
                                exc_info=True)

    def _dispatch(self, line: bytes, session: str, state: dict[str, Any]) -> dict[str, Any]:
        try:
            message = json.loads(line)
        except ValueError:
            return _bad(None, "wiadomość nie jest JSON")
        if not isinstance(message, dict):
            return _bad(None, "oczekiwano obiektu JSON")
        msg_id = message.get("id", 0)
        if not isinstance(msg_id, (str, int)):
            return _bad(None, "id musi być liczbą całkowitą lub tekstem")
        kind = str(message.get("type", ""))
        self.app.sessions.touch(session)

        if kind == "auth" or "token" in message:
            given = str(message.get("token", ""))
            if self.token and not hmac.compare_digest(given, self.token):
                return _bad(msg_id, "zły token", code="unauthorized")
            state["authed"], state["token"] = True, given
            if kind == "auth":
                return {"type": "auth", "ok": True}
        if not state["authed"]:
            return _bad(msg_id, "wymagany token: {\"type\":\"auth\",\"token\":\"...\"}",
                        code="unauthorized")
        if kind == "ping":
            return {"type": "pong"}
        if kind in {"subscribe", "hello"}:
            topics = message.get("topics")
            state["wanted"] = {str(t) for t in topics} if isinstance(topics, list) else None
            state["push"] = True
            return {"type": "subscribed", "topics": sorted(state["wanted"] or []),
                    "version": self.app.hub.version}
        if kind == "unsubscribe":
            state["push"] = False
            return {"type": "unsubscribed"}
        if message.get("method") == "state.get":
            return self.app.handle_message(message, channel="socket",
                                           token=state["token"]).model_dump(mode="json")

        command = message.get("command")
        if not isinstance(command, str) or not command.strip():
            return _bad(msg_id, "oczekiwano 'command' (operacja z kontraktu), "
                                "'method':'state.get' albo 'type':'ping'|'auth'|'subscribe'")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _bad(msg_id, "params musi być obiektem")
        params = dict(params)
        if command in JOG_COMMANDS:
            params["session"] = session
        try:
            response = self.app.handle_message({"id": msg_id, "command": command,
                                                "params": params}, channel="socket",
                                               token=state["token"])
        except ApiError as exc:  # np. limiter poza handle_message
            return {"id": msg_id, "ok": False, "result": None, "error": exc.to_dict()}
        out = response.model_dump(mode="json")
        if response.ok and command == "access.login":
            state["token"] = response.result["token"]
        elif response.ok and command == "access.logout":
            state["token"] = ""
        return out


def _bad(msg_id: Any, text: str, code: str = "invalid_request") -> dict[str, Any]:
    return {"id": msg_id if msg_id is not None else 0, "ok": False, "result": None,
            "error": {"code": code, "message": text, "details": {}}}


class _ThreadingTcp(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


class _ThreadingUnix(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class SocketClient:
    """Minimalny klient JSON-lines (testy, skrypty, przykład dla innych języków)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, unix: str | None = None,
                 token: str = "", timeout: float = 5.0):
        if unix:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.settimeout(timeout)
            self._sock.connect(unix)
        else:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        self._file = self._sock.makefile("rwb")
        self.hello = self.read()
        self._next = 1
        if token:
            self.send({"type": "auth", "token": token})
            self.read()

    def send(self, obj: dict[str, Any]) -> None:
        self._file.write((json.dumps(obj) + "\n").encode())
        self._file.flush()

    def read(self) -> dict[str, Any]:
        line = self._file.readline()
        if not line:
            raise ConnectionError("serwer zamknął połączenie")
        return json.loads(line)

    def call(self, command: str, **params: Any) -> dict[str, Any]:
        """Wywołuje operację i zwraca ``result``; błąd serwera → ``RuntimeError``."""
        call_id, self._next = self._next, self._next + 1
        self.send({"id": call_id, "command": command, "params": params})
        while True:
            reply = self.read()
            if reply.get("id") == call_id and "ok" in reply:
                if not reply["ok"]:
                    raise RuntimeError(f"{reply['error']['code']}: {reply['error']['message']}")
                return reply["result"]

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._file.close()
            self._sock.close()


__all__ = ["SocketClient", "SocketServer"]
