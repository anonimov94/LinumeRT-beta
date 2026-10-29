"""System wtyczek: rdzeń + moduły doinstalowywane w miarę potrzeb.

SPDX-License-Identifier: GPL-2.0-or-later

Wtyczka to pakiet z funkcją ``register(api)``, który dokłada do kontraktu własną domenę
operacji (np. ``stats.gcode``). REST, WebSocket, socket, CLI i SDK widzą ją od razu — tak
samo jak operacje rdzenia. Rdzeń nie zna wtyczek z nazwy.

Skąd wtyczka się bierze (obie drogi działają naraz):

1. **Katalog** ``<root>/plugins/<nazwa>/`` z ``plugin.yaml`` i modułem (domyślnie
   ``plugin.py``). Instalacja = skopiowanie katalogu (operacja ``plugin.install``).
2. **Pakiet pip** z entry pointem w grupie ``linumert.plugins``; moduł ma ``MANIFEST``
   (słownik jak ``plugin.yaml``) i ``register``.

Zasady:
- wtyczka deklaruje ``domains``; może rejestrować operacje **tylko** w tych domenach,
  a domena nie może należeć do rdzenia ani do innej wtyczki,
- błąd wtyczki (import, manifest, ``register``) nie przewraca aplikacji: wtyczka dostaje
  status ``failed``, jej operacje są wycofywane z kontraktu, reszta działa dalej,
- ``requires`` wymusza kolejność ładowania; brak zależności = ``failed``,
- wtyczka jest zwykłym kodem Pythona uruchamianym w procesie — instaluj tylko zaufane.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import logging
import re
import shutil
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from .contract import Contract, Handler, Operation
from .schema import Model, Ok

log = logging.getLogger("linumert.plugins")

PLUGIN_API_VERSION = 1
ENTRY_POINT_GROUP = "linumert.plugins"
MANIFEST_FILE = "plugin.yaml"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

Status = Literal["loaded", "disabled", "failed"]


class PluginError(Exception):
    """Błąd manifestu, zależności albo instalacji wtyczki."""


@dataclass
class Manifest:
    name: str
    version: str = "0.0.0"
    api: int = PLUGIN_API_VERSION
    description: str = ""
    domains: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    entry: str = "plugin:register"       # moduł:funkcja (katalog) lub pomijane (entry point)
    source: str = "dir"                  # "dir" | "entrypoint"
    path: Path | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any], *, source: str, path: Path | None) -> Manifest:
        if not isinstance(data, dict):
            raise PluginError("manifest musi być obiektem")
        unknown = set(data) - {"name", "version", "api", "description", "domains",
                               "requires", "entry"}
        if unknown:
            raise PluginError(f"nieznane pola manifestu: {sorted(unknown)}")
        name = str(data.get("name", ""))
        if not NAME_RE.match(name):
            raise PluginError(f"nazwa wtyczki '{name}' niepoprawna (a-z, 0-9, _; 2-32 znaki)")
        domains = tuple(str(d) for d in data.get("domains") or ())
        if not domains:
            raise PluginError("manifest musi deklarować przynajmniej jedną domenę (domains)")
        for domain in domains:
            if not NAME_RE.match(domain):
                raise PluginError(f"domena '{domain}' niepoprawna")
        try:
            api = int(data.get("api", PLUGIN_API_VERSION))
        except (TypeError, ValueError):
            raise PluginError("pole api musi być liczbą") from None
        return cls(name=name, version=str(data.get("version", "0.0.0")), api=api,
                   description=str(data.get("description", "")), domains=domains,
                   requires=tuple(str(r) for r in data.get("requires") or ()),
                   entry=str(data.get("entry", "plugin:register")), source=source, path=path)


@dataclass
class PluginRecord:
    manifest: Manifest
    status: Status = "disabled"
    error: str = ""
    operations: list[str] = field(default_factory=list)


class PluginApi:
    """Jedyna powierzchnia, jaką wtyczka widzi: rejestracja operacji, usługi, ścieżki."""

    api_version = PLUGIN_API_VERSION

    def __init__(self, manifest: Manifest, contract: Contract, services: dict[str, Any],
                 publish: Callable[[str, dict[str, Any]], Any], record: PluginRecord):
        self.name = manifest.name
        self.domains = manifest.domains
        self.services = services      # tylko do odczytu z konwencji; własne dane: set_service
        self._contract = contract
        self._publish = publish
        self._record = record

    @property
    def paths(self) -> Any:
        return self.services["paths"]

    def command(self, name: str, *, summary: str, handler: Handler, **kwargs: Any) -> Operation:
        self._check(name)
        op = self._contract.command(name, domain=name.split(".", 1)[0], summary=summary,
                                    handler=handler, **kwargs)
        self._record.operations.append(name)
        return op

    def query(self, name: str, *, summary: str, result: type[Model], handler: Handler,
              **kwargs: Any) -> Operation:
        self._check(name)
        op = self._contract.query(name, domain=name.split(".", 1)[0], summary=summary,
                                  result=result, handler=handler, **kwargs)
        self._record.operations.append(name)
        return op

    def event(self, topic: str, *, summary: str, payload: dict[str, Any] | None = None) -> None:
        self._check_topic(topic)
        self._contract.event(topic, summary=summary, payload=payload)

    def publish(self, topic: str, payload: dict[str, Any]) -> Any:
        """Publikuje temat stanu ``<wtyczka>.<temat>`` (GUI dostaje go przez push)."""
        self._check_topic(topic)
        return self._publish(topic, payload)

    def set_service(self, service: Any) -> None:
        """Udostępnia obiekt innym wtyczkom jako ``services['plugin:<nazwa>']``."""
        self.services[f"plugin:{self.name}"] = service

    def _check(self, op_name: str) -> None:
        domain = op_name.split(".", 1)[0] if "." in op_name else ""
        if domain not in self.domains:
            raise PluginError(f"wtyczka {self.name}: operacja '{op_name}' poza zadeklarowanymi "
                              f"domenami {list(self.domains)}")

    def _check_topic(self, topic: str) -> None:
        if topic.split(".", 1)[0] not in self.domains:
            raise PluginError(f"wtyczka {self.name}: temat '{topic}' musi zaczynać się od "
                              f"jednej z domen {list(self.domains)}")


class PluginManager:
    """Odkrywa, ładuje i opisuje wtyczki; stan włączenia trzyma w ``plugins.json``."""

    def __init__(self, *, plugin_dir: Path, state_file: Path, contract: Contract,
                 services: dict[str, Any], publish: Callable[[str, dict[str, Any]], Any],
                 use_entry_points: bool = True):
        self.plugin_dir = plugin_dir
        self.state_file = state_file
        self.contract = contract
        self.services = services
        self._publish = publish
        self._use_entry_points = use_entry_points
        self._records: dict[str, PluginRecord] = {}
        self._core_domains = set(contract.domains())
        self._lock = threading.RLock()

    # ---- stan włączenia ----------------------------------------------------
    def disabled(self) -> set[str]:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return {str(x) for x in data.get("disabled", [])}
        except (OSError, ValueError):
            return set()

    def _save_disabled(self, names: set[str]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({"disabled": sorted(names)}, indent=2),
                                   encoding="utf-8")

    # ---- odkrywanie --------------------------------------------------------
    def discover(self) -> list[Manifest]:
        found: dict[str, Manifest] = {}
        errors: list[tuple[str, str]] = []
        if self.plugin_dir.is_dir():
            for folder in sorted(self.plugin_dir.iterdir()):
                if not (folder / MANIFEST_FILE).is_file():
                    continue
                try:
                    found.setdefault(*self._dir_manifest(folder))
                except PluginError as exc:
                    errors.append((folder.name, str(exc)))
        if self._use_entry_points:
            for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
                try:
                    module = importlib.import_module(ep.value.split(":")[0])
                    manifest = Manifest.from_mapping(dict(getattr(module, "MANIFEST", {})),
                                                     source="entrypoint", path=None)
                    manifest.entry = ep.value
                    found.setdefault(manifest.name, manifest)
                except Exception as exc:
                    errors.append((ep.name, f"entry point: {exc}"))
        for label, message in errors:
            # Nieczytelny manifest też ma być widoczny na liście, nie tylko w logu.
            name = label if NAME_RE.match(label) else "bad_" + re.sub(r"\W", "_", label.lower())
            stub = Manifest(name=name[:32], domains=("none",))
            self._records[stub.name] = PluginRecord(stub, "failed", message)
            log.warning("wtyczka %s: %s", label, message)
        return list(found.values())

    @staticmethod
    def _dir_manifest(folder: Path) -> tuple[str, Manifest]:
        try:
            data = yaml.safe_load((folder / MANIFEST_FILE).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise PluginError(f"manifest nieczytelny: {exc}") from None
        manifest = Manifest.from_mapping(data, source="dir", path=folder)
        if manifest.name != folder.name:
            raise PluginError(f"nazwa w manifeście '{manifest.name}' ≠ katalog '{folder.name}'")
        return manifest.name, manifest

    # ---- ładowanie ---------------------------------------------------------
    def load_all(self) -> list[PluginRecord]:
        with self._lock:
            manifests = self.discover()
            off = self.disabled()
            for manifest in self._order(manifests):
                if manifest.name in off:
                    self._records[manifest.name] = PluginRecord(manifest, "disabled")
                else:
                    self._load(manifest)
            return self.records()

    def _order(self, manifests: list[Manifest]) -> list[Manifest]:
        by_name = {m.name: m for m in manifests}
        ordered: list[Manifest] = []
        seen: set[str] = set()

        def visit(m: Manifest, stack: tuple[str, ...]) -> None:
            if m.name in seen:
                return
            if m.name in stack:
                return  # cykl: _load zgłosi brak zależności
            for dep in m.requires:
                if dep in by_name:
                    visit(by_name[dep], (*stack, m.name))
            seen.add(m.name)
            ordered.append(m)

        for manifest in sorted(manifests, key=lambda m: m.name):
            visit(manifest, ())
        return ordered

    def _load(self, manifest: Manifest) -> PluginRecord:
        record = PluginRecord(manifest)
        self._records[manifest.name] = record
        try:
            if manifest.api > PLUGIN_API_VERSION:
                raise PluginError(f"wtyczka wymaga API {manifest.api}, rdzeń ma "
                                  f"{PLUGIN_API_VERSION}")
            for domain in manifest.domains:
                owner = self._domain_owner(domain, manifest.name)
                if owner:
                    raise PluginError(f"domena '{domain}' należy już do: {owner}")
            for dep in manifest.requires:
                if self._records.get(dep, PluginRecord(manifest)).status != "loaded":
                    raise PluginError(f"brak załadowanej zależności: {dep}")
            register = self._import_register(manifest)
            api = PluginApi(manifest, self.contract, self.services, self._publish, record)
            register(api)
            record.status = "loaded"
            log.info("wtyczka %s %s: %d operacji", manifest.name, manifest.version,
                     len(record.operations))
        except Exception as exc:
            record.status, record.error = "failed", f"{type(exc).__name__}: {exc}"
            for name in record.operations:
                self.contract.unregister(name)
            record.operations.clear()
            self.services.pop(f"plugin:{manifest.name}", None)
            log.warning("wtyczka %s nie załadowana: %s", manifest.name, record.error)
        return record

    def _domain_owner(self, domain: str, me: str) -> str:
        if domain in self._core_domains:
            return "rdzeń"
        for name, rec in self._records.items():
            if name != me and rec.status == "loaded" and domain in rec.manifest.domains:
                return name
        return ""

    def _import_register(self, manifest: Manifest) -> Callable[[PluginApi], None]:
        module_name, _, func = manifest.entry.partition(":")
        func = func or "register"
        if manifest.source == "entrypoint":
            module = importlib.import_module(module_name)
        else:
            assert manifest.path is not None
            file = manifest.path / f"{module_name}.py"
            if not file.is_file():
                raise PluginError(f"brak pliku modułu: {file.name}")
            alias = f"linumert_plugin_{manifest.name}"
            spec = importlib.util.spec_from_file_location(alias, file)
            if spec is None or spec.loader is None:
                raise PluginError(f"nie można zaimportować {file.name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[alias] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(alias, None)
                raise
        register = getattr(module, func, None)
        if not callable(register):
            raise PluginError(f"brak funkcji {func}(api) w module {module_name}")
        return register

    # ---- zarządzanie -------------------------------------------------------
    def records(self) -> list[PluginRecord]:
        return sorted(self._records.values(), key=lambda r: r.manifest.name)

    def get(self, name: str) -> PluginRecord:
        try:
            return self._records[name]
        except KeyError:
            raise PluginError(f"nieznana wtyczka: {name}") from None

    def set_enabled(self, name: str, enabled: bool) -> None:
        with self._lock:
            self.get(name)
            off = self.disabled()
            off.discard(name) if enabled else off.add(name)
            self._save_disabled(off)

    def install(self, source: Path) -> PluginRecord:
        """Kopiuje katalog wtyczki do ``plugins/`` i ładuje ją bez restartu."""
        with self._lock:
            source = source.resolve()
            name, manifest = self._dir_manifest(source)
            if name in self._records and self._records[name].status == "loaded":
                raise PluginError(f"wtyczka {name} jest już załadowana (najpierw plugin.remove)")
            target = self.plugin_dir / name
            if target.exists():
                raise PluginError(f"katalog {target.name} już istnieje w plugins/")
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
            manifest.path = target
            off = self.disabled()
            if name in off:
                off.discard(name)
                self._save_disabled(off)
            return self._load(manifest)

    def remove(self, name: str) -> None:
        """Usuwa katalog wtyczki i jej operacje z kontraktu."""
        with self._lock:
            record = self.get(name)
            if record.manifest.source != "dir" or record.manifest.path is None:
                raise PluginError("wtyczkę z pakietu pip odinstaluj przez pip")
            for op in record.operations:
                self.contract.unregister(op)
            self.services.pop(f"plugin:{name}", None)
            shutil.rmtree(record.manifest.path, ignore_errors=True)
            sys.modules.pop(f"linumert_plugin_{name}", None)
            del self._records[name]
            off = self.disabled()
            off.discard(name)
            self._save_disabled(off)


# ---- operacje domeny ``plugin`` ----------------------------------------------------


class PluginInfo(Model):
    name: str
    version: str
    description: str
    status: Status
    source: str
    domains: list[str]
    requires: list[str]
    operations: list[str]
    error: str = ""
    enabled: bool = True


class PluginList(Model):
    api_version: int
    plugins: list[PluginInfo]


class PluginName(Model):
    name: str


class PluginSource(Model):
    source: str


class PluginChange(Model):
    ok: bool = True
    message: str = ""
    plugin: PluginInfo | None = None
    restart_required: bool = False


def _info(manager: PluginManager, record: PluginRecord) -> PluginInfo:
    m = record.manifest
    return PluginInfo(name=m.name, version=m.version, description=m.description,
                      status=record.status, source=m.source, domains=list(m.domains),
                      requires=list(m.requires), operations=sorted(record.operations),
                      error=record.error, enabled=m.name not in manager.disabled())


def register_plugin_operations(c: Contract, manager: PluginManager) -> None:
    """Rejestruje ``plugin.*`` — zarządzanie wtyczkami przez ten sam kontrakt."""
    from .errors import InvalidRequest, NotFound

    def guarded(fn: Callable[..., Any]) -> Callable[..., Any]:
        def run(request: Any, _ctx: Any) -> Any:
            try:
                return fn(request)
            except PluginError as exc:
                text = str(exc)
                raise (NotFound if text.startswith("nieznana") else InvalidRequest)(text) from None
        return run

    c.query("plugin.list", domain="plugin", summary="Lista wtyczek i ich status",
            result=PluginList, handler=lambda r, ctx: PluginList(
                api_version=PLUGIN_API_VERSION,
                plugins=[_info(manager, rec) for rec in manager.records()]))
    c.query("plugin.info", domain="plugin", summary="Szczegóły jednej wtyczki",
            request=PluginName, result=PluginInfo,
            handler=guarded(lambda r: _info(manager, manager.get(r.name))))

    def toggle(enabled: bool) -> Handler:
        def run(r: PluginName) -> PluginChange:
            manager.set_enabled(r.name, enabled)
            return PluginChange(message="zmiana zadziała po restarcie aplikacji",
                                plugin=_info(manager, manager.get(r.name)),
                                restart_required=True)
        return guarded(run)

    c.command("plugin.enable", domain="plugin", summary="Włącz wtyczkę (od następnego startu)",
              request=PluginName, result=PluginChange, safety="config", role="serwis",
              idempotent=True, handler=toggle(True))
    c.command("plugin.disable", domain="plugin",
              summary="Wyłącz wtyczkę (od następnego startu)", request=PluginName,
              result=PluginChange, safety="config", role="serwis", idempotent=True,
              handler=toggle(False))

    def install(r: PluginSource) -> PluginChange:
        record = manager.install(Path(r.source))
        ok = record.status == "loaded"
        return PluginChange(ok=ok, message="zainstalowana" if ok else record.error,
                            plugin=_info(manager, record))

    c.command("plugin.install", domain="plugin",
              summary="Zainstaluj wtyczkę z katalogu lokalnego i załaduj od razu",
              request=PluginSource, result=PluginChange, safety="config", role="serwis",
              handler=guarded(install))

    def remove(r: PluginName) -> Ok:
        manager.remove(r.name)
        return Ok(message=f"usunięto wtyczkę {r.name}")

    c.command("plugin.remove", domain="plugin", summary="Usuń wtyczkę i jej operacje",
              request=PluginName, result=Ok, safety="config", role="serwis",
              handler=guarded(remove))


__all__ = ["PLUGIN_API_VERSION", "Manifest", "PluginApi", "PluginError", "PluginManager",
           "PluginRecord", "register_plugin_operations"]
