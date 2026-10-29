"""Wtyczki: odkrywanie, ładowanie, izolacja błędów, instalacja.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from linumert_headless.app import build_application
from linumert_headless.config import AppConfig
from linumert_headless.errors import ApiError

BETA = Path(__file__).resolve().parent.parent
EXAMPLE = BETA / "plugins_examples" / "stats"


def make_plugin(root: Path, name: str, body: str, *, domains=None, requires=()) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    domains = domains or [name]
    (folder / "plugin.yaml").write_text(
        f"name: {name}\nversion: 1.0.0\ndescription: test\ndomains: {domains}\n"
        f"requires: {list(requires)}\n", encoding="utf-8")
    (folder / "plugin.py").write_text(body, encoding="utf-8")
    return folder


OK_BODY = '''
from linumert_headless.schema import Ok
def register(api):
    api.command("{d}.ping", summary="ping", handler=lambda r, ctx: Ok(message="pong"))
'''


@pytest.fixture
def build(workdir):
    apps = []

    def _build():
        application = build_application(AppConfig(
            root=workdir, backend="fake", autostart=False, plugin_entry_points=False))
        apps.append(application)
        return application

    yield _build
    for application in apps:
        application.stop()


def test_bez_wtyczek_kontrakt_ma_tylko_domene_plugin(build) -> None:
    app = build()
    assert app.call_json("plugin.list")["plugins"] == []
    assert "plugin" in app.contract.domains()


def test_wtyczka_z_katalogu_dokleja_operacje(workdir, build) -> None:
    make_plugin(workdir / "plugins", "alfa", OK_BODY.format(d="alfa"))
    app = build()
    assert app.call_json("alfa.ping")["message"] == "pong"
    info = app.call_json("plugin.info", {"name": "alfa"})
    assert info["status"] == "loaded" and info["operations"] == ["alfa.ping"]


def test_blad_wtyczki_nie_przewraca_aplikacji(workdir, build) -> None:
    make_plugin(workdir / "plugins", "zla", "raise RuntimeError('boom')")
    make_plugin(workdir / "plugins", "dobra", OK_BODY.format(d="dobra"))
    app = build()
    bad = app.call_json("plugin.info", {"name": "zla"})
    assert bad["status"] == "failed" and "boom" in bad["error"]
    assert app.call_json("dobra.ping")["ok"] is True
    assert app.call_json("machine.state")["task_state"]


def test_czesciowa_rejestracja_jest_wycofana(workdir, build) -> None:
    body = OK_BODY.format(d="polowa") + "\n    raise RuntimeError('po rejestracji')\n"
    make_plugin(workdir / "plugins", "polowa", body)
    app = build()
    assert app.call_json("plugin.info", {"name": "polowa"})["status"] == "failed"
    with pytest.raises(ApiError):
        app.call("polowa.ping")


def test_domena_rdzenia_jest_zabroniona(workdir, build) -> None:
    make_plugin(workdir / "plugins", "intruz", OK_BODY.format(d="machine"), domains=["machine"])
    app = build()
    info = app.call_json("plugin.info", {"name": "intruz"})
    assert info["status"] == "failed" and "rdzeń" in info["error"]


def test_operacja_poza_zadeklarowana_domena_jest_odrzucona(workdir, build) -> None:
    make_plugin(workdir / "plugins", "sprytna", OK_BODY.format(d="machine"))
    app = build()
    info = app.call_json("plugin.info", {"name": "sprytna"})
    assert info["status"] == "failed" and "poza zadeklarowanymi" in info["error"]


def test_zaleznosci_wymuszaja_kolejnosc_i_obecnosc(workdir, build) -> None:
    make_plugin(workdir / "plugins", "a_dziecko", OK_BODY.format(d="a_dziecko"),
                requires=["z_rodzic"])
    make_plugin(workdir / "plugins", "z_rodzic", OK_BODY.format(d="z_rodzic"))
    make_plugin(workdir / "plugins", "sierota", OK_BODY.format(d="sierota"), requires=["nie_ma"])
    app = build()
    assert app.call_json("a_dziecko.ping")["ok"] is True
    assert app.call_json("plugin.info", {"name": "sierota"})["status"] == "failed"


def test_instalacja_wylaczenie_i_usuniecie(workdir, build) -> None:
    app = build()
    assert app.call_json("plugin.install", {"source": str(EXAMPLE)})["ok"] is True
    assert (workdir / "plugins" / "stats" / "plugin.yaml").is_file()
    app.call_json("program.write", {"name": "t.ngc", "text": "G0 X0\nG1 X5 F100\nM6 T1\n"})
    stats = app.call_json("stats.gcode", {"name": "t.ngc"})
    assert (stats["rapid"], stats["linear"], stats["tool_changes"]) == (1, 1, 1)

    change = app.call_json("plugin.disable", {"name": "stats"})
    assert change["restart_required"] is True
    app2 = build()
    assert app2.call_json("plugin.info", {"name": "stats"})["status"] == "disabled"
    with pytest.raises(ApiError):
        app2.call("stats.gcode", {"name": "t.ngc"})

    app.call_json("plugin.remove", {"name": "stats"})
    assert not (workdir / "plugins" / "stats").exists()
    with pytest.raises(ApiError):
        app.call("stats.gcode", {"name": "t.ngc"})


def test_instalacja_nie_nadpisuje_istniejacej(workdir, build) -> None:
    shutil.copytree(EXAMPLE, workdir / "plugins" / "stats")
    app = build()
    with pytest.raises(ApiError):
        app.call("plugin.install", {"source": str(EXAMPLE)})


def test_zly_manifest_widoczny_na_liscie(workdir, build) -> None:
    folder = workdir / "plugins" / "krzywa"
    folder.mkdir(parents=True)
    (folder / "plugin.yaml").write_text("name: KRZYWA\ndomains: [x]\n", encoding="utf-8")
    app = build()
    failed = [p for p in app.call_json("plugin.list")["plugins"] if p["status"] == "failed"]
    assert failed and "niepoprawna" in failed[0]["error"]


def test_zarzadzanie_wtyczkami_wymaga_roli_serwisu(app) -> None:
    for name in ("plugin.install", "plugin.remove", "plugin.enable", "plugin.disable"):
        assert app.contract.get(name).role == "serwis"
