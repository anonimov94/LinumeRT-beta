# Wtyczki (core + plugins)

SPDX-License-Identifier: GPL-2.0-or-later

Rdzeń jest stabilny; funkcje dokładasz jako wtyczki. Wtyczka = katalog z `plugin.yaml` + `plugin.py`.

```
plugins/moja/
  plugin.yaml
  plugin.py
```
`plugin.yaml`:
```yaml
name: moja              # a-z 0-9 _, 2-32 znaki, = nazwa katalogu
version: 0.1.0
api: 1                  # wersja API wtyczek (rdzeń: PLUGIN_API_VERSION)
description: co robi
domains: [moja]         # domeny operacji, które wtyczka zajmuje (nie mogą być domenami rdzenia)
requires: []            # inne wtyczki, ładowane wcześniej
entry: plugin:register  # opcjonalne: moduł:funkcja
```
`plugin.py`:
```python
from linumert_headless.schema import Model, Ok

def register(api):
    api.command("moja.ping", summary="ping", handler=lambda req, ctx: Ok(message="pong"))
    # api.query("moja.dane", summary=..., request=Model, result=Model, handler=...)
    # ctx.services["program"], ["tools"], ["machine"] ... — usługi rdzenia
```
Reguły: operacje tylko w zadeklarowanych domenach; tematy stanu `api.publish("moja.temat", {...})`;
własna usługa dla innych wtyczek: `api.set_service(obj)` → `services["plugin:moja"]`.
Wzorzec: `plugins_examples/stats/`.

## Instalacja
- ręcznie: skopiuj katalog do `<root>/plugins/` i zrestartuj, albo
- `linumertctl plugin install --source /ścieżka/do/wtyczki` (rola `serwis`, ładuje od razu),
- paczka pip: entry point grupy `linumert.plugins`, moduł z `MANIFEST = {...}` i `register`.
Zarządzanie: `plugin.list`, `plugin.info`, `plugin.enable`/`plugin.disable` (od następnego startu),
`plugin.remove`. Stan włączenia: `state/plugins.json`.

## Bezpieczeństwo i błędy
Wtyczka to kod uruchamiany w procesie — instaluj tylko zaufane. Błąd wtyczki (import, manifest,
`register`) nie przewraca aplikacji: status `failed` + opis w `plugin.list`, jej operacje są
wycofywane. Wtyczka nie omija ról, limitera ani deadmana: wszystko idzie przez kontrakt.
Operacje ruchowe wtyczki muszą mieć `safety="motion"` i wołać tylko usługę `machine`.
