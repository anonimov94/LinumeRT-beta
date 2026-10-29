"""Punkt wejścia aplikacji headless: ``linumertd`` / ``python -m linumert_headless``.

SPDX-License-Identifier: GPL-2.0-or-later

Polecenia::

    linumertd serve --backend fake --host 127.0.0.1 --port 8080
    linumertd contract --out api/contract.json
    linumertd info
    linumertd doctor

``serve`` startuje pętlę stanu (50 Hz), REST i WebSocket. Aplikacja nie ma GUI: żeby
zobaczyć stan, użyj ``linumertctl`` albo dowolnego klienta SDK/GUI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .app import build_application
from .config import DEFAULT_HOST, DEFAULT_PORT, AppConfig
from .errors import ApiError, BackendUnavailable


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linumertd",
        description="linumeRT headless — serwer API aplikacji CNC bez GUI "
                    "(bez Qt, OpenGL i panelu web).")
    parser.add_argument("--version", action="version", version=f"linumertd {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="uruchom serwer REST + WebSocket")
    serve.add_argument("--backend", default="fake", choices=("fake", "linuxcnc"))
    serve.add_argument("--ini", "-ini", type=Path, help="INI działającej instancji LinuxCNC")
    serve.add_argument("--root", type=Path, help="katalog danych beta")
    serve.add_argument("--state-dir", type=Path, help="katalog stanu aplikacji")
    serve.add_argument("--axes", default="XYZ", help="osie backendu fake (domyślnie XYZ)")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument("--token", default="", help="token API (albo LRT_TOKEN)")
    serve.add_argument("--poll-hz", type=float, default=50.0)
    serve.add_argument("--allow-origin", action="append", default=[],
                       help="dozwolony Origin dla GUI z przeglądarki (powtarzalne)")
    serve.add_argument("--allow-any-host", action="store_true",
                       help="akceptuj dowolny nagłówek Host (podgląd przez proxy; "
                            "wyłącza ochronę przed DNS-rebinding — tylko demo)")
    serve.add_argument("--socket-port", type=int, default=None,
                       help="dodatkowo: TCP JSON-lines na tym porcie (0 = wolny port)")
    serve.add_argument("--socket-unix", type=Path, default=None,
                       help="dodatkowo: gniazdo Unix JSON-lines (uprawnienia 0600)")
    serve.add_argument("--no-http", action="store_true",
                       help="bez REST/WebSocket (nie wymaga fastapi/uvicorn) — tylko socket")
    serve.add_argument("--plugin-dir", type=Path, default=None,
                       help="katalog wtyczek (domyślnie <root>/plugins)")
    serve.add_argument("--no-plugins", action="store_true", help="nie ładuj wtyczek")
    serve.add_argument("--log-level", default="INFO")
    serve.add_argument("--print-contract", action="store_true",
                       help="przed startem wypisz liczbę operacji i domeny")

    contract = sub.add_parser("contract", help="wypisz albo zapisz kontrakt JSON")
    contract.add_argument("--out", default="", help="plik docelowy (domyślnie stdout)")

    for name, help_text in (("info", "informacje o aplikacji"),
                            ("doctor", "inwentaryzacja środowiska"),
                            ("operations", "lista operacji kontraktu")):
        item = sub.add_parser(name, help=help_text)
        item.add_argument("--backend", default="fake", choices=("fake", "linuxcnc"))
    return parser


def _config(args: argparse.Namespace) -> AppConfig:
    ini = getattr(args, "ini", None)
    if ini is not None and not ini.is_file():
        raise ValueError(f"nie znaleziono INI: {ini}")
    return AppConfig(
        root=getattr(args, "root", None) or AppConfig().root,
        ini=ini.resolve() if ini else None,
        state_dir=getattr(args, "state_dir", None),
        backend=getattr(args, "backend", "fake"),
        axes=tuple(a.upper() for a in getattr(args, "axes", "XYZ")),
        listen=getattr(args, "host", DEFAULT_HOST),
        port=getattr(args, "port", DEFAULT_PORT),
        token=getattr(args, "token", ""),
        poll_hz=getattr(args, "poll_hz", 50.0),
        log_level=getattr(args, "log_level", "INFO"),
        allow_origins=tuple(getattr(args, "allow_origin", []) or ()),
        allow_any_host=bool(getattr(args, "allow_any_host", False)),
        plugins=not getattr(args, "no_plugins", False),
        plugin_dir=getattr(args, "plugin_dir", None),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(level=getattr(args, "log_level", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.command == "contract":
        app = build_application(AppConfig())
        payload = app.contract.export(application="linumeRT headless", version=__version__)
        app.stop()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            target = Path(args.out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"kontrakt: {target} ({len(payload['operations'])} operacji, "
                  f"{len(payload['domains'])} domen)")
        else:
            print(text)
        return 0

    try:
        config = _config(args)
        app = build_application(config)
    except (BackendUnavailable, ValueError) as exc:
        print(f"linumertd nie wystartował: {exc}", file=sys.stderr)
        return 1

    if args.command == "info":
        print(json.dumps(app.call_json("system.info"), ensure_ascii=False, indent=2))
        app.stop()
        return 0
    if args.command == "doctor":
        report = app.call_json("diag.doctor")
        print(report["report"] or json.dumps(report["entries"], ensure_ascii=False, indent=2))
        app.stop()
        return 0
    if args.command == "operations":
        for operation in app.contract.operations():
            print(f"{operation.name:<28} {operation.kind:<8} {operation.status:<12} "
                  f"{operation.summary}")
        app.stop()
        return 0

    # ---- serve -------------------------------------------------------------
    try:
        config.require_token_for_network()
    except ValueError as exc:
        print(f"linumertd nie wystartował: {exc}", file=sys.stderr)
        app.stop()
        return 1

    token = config.resolved_token()
    if args.print_contract:
        print(f"kontrakt: {len(app.contract.operations())} operacji, "
              f"domeny: {', '.join(app.contract.domains())}", flush=True)
    app.start()

    sockets = []
    if args.socket_port is not None or args.socket_unix is not None or args.no_http:
        from .transport.socket import SocketServer

        try:
            if args.socket_unix is not None:
                sockets.append(SocketServer(app, unix=args.socket_unix).start())
            if args.socket_port is not None or args.socket_unix is None:
                sockets.append(SocketServer(
                    app, host=config.listen, port=args.socket_port or 0, token=token).start())
        except (OSError, ValueError) as exc:
            print(f"linumertd nie wystartował: {exc}", file=sys.stderr)
            app.stop()
            return 1
        for server in sockets:
            print(f"socket JSON-lines: {server.address}", flush=True)

    print(f"linumeRT headless {__version__}: backend {config.backend} (bez GUI)", flush=True)
    if token:
        print("token API ustawiony — przekaż go w nagłówku X-LRT-Token / wiadomości auth",
              flush=True)
    try:
        if args.no_http:
            import threading

            threading.Event().wait()
        else:
            import uvicorn

            from .transport.rest import create_app

            fastapi_app = create_app(app, token=token, extra_hosts=(f"{config.listen}",),
                                     allow_origins=config.allow_origins,
                                     allow_any_host=config.allow_any_host)
            print(f"API http://{config.listen}:{config.port}/api/v1", flush=True)
            uvicorn.run(fastapi_app, host=config.listen, port=config.port, log_level="warning")
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"linumertd nie wystartował: {exc}", file=sys.stderr)
        return 1
    finally:
        for server in sockets:
            server.stop()
        app.stop()
    return 0


def _fail(exc: ApiError) -> int:  # pragma: no cover - pomocnicze
    print(f"błąd {exc.code}: {exc.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())


def linuxcnc_display() -> int:
    """Punkt DISPLAY: LinuxCNC uruchamia go z argumentem -ini."""
    return main(["serve", "--backend", "linuxcnc", *sys.argv[1:]])
