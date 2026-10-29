# AGENTS.md — instrukcja dla modeli pracujących na linumeRT headless (beta)

Czytaj TYLKO ten plik na start (≈2 min), potem tylko pliki ze swojego zadania.

## Zasady (obowiązują zawsze)
1. **Bez GUI** w rdzeniu (strażnik: `tools/check_no_gui.py`). GUI powstaje na końcu jako klient kontraktu.
2. **Push i PR tylko na wyraźne polecenie właściciela;** testy lokalne (`make test`).
3. **Roadmapa po każdej ukończonej funkcji:**
   `python3 tools/roadmap.py done ID --evidence ŚCIEŻKA_KODU ŚCIEŻKA_TESTU`
   (sprawdź `python3 tools/roadmap.py next` — co dalej). Nie edytuj `ROADMAP.md` ręcznie.
4. `SAFETY.md` obowiązuje: nie osłabiaj ostrzeżeń, nie sugeruj, że ekran/oprogramowanie zastępuje sprzętowy E-STOP.
5. Sprzęt: wszystko, czego nie da się sprawdzić na atrapie/Plant, oznacz `NIEZWERYFIKOWANE NA SPRZĘCIE`.
6. Nowa funkcja = **wtyczka**, chyba że dotyka bezpieczeństwa/rdzenia (wtedy rdzeń + test).
7. Pliki ≤ ~400 linii; komentarze i komunikaty po polsku; nagłówek `SPDX-License-Identifier: GPL-2.0-or-later`.
8. **Gorąca pętla numeryczna → C** w `native/` (C11, bez zależności, `-ffp-contract=off`), Python zostaje cienkim wiązaniem + wersją zapasową; dodaj test parytetu z numpy i pomiar (`tools/bench_*.py`).
9. Po zmianie operacji: `make contract` (regeneruje `api/contract.json`), potem `make lint test`.

## Architektura w 10 linijkach
```
transport (REST · WebSocket · SOCKET JSON-lines · CLI · SDK)   src/linumert_headless/transport/
kontrakt: rejestr operacji domena.akcja                         src/linumert_headless/contract.py
usługi domen (machine program tool cam offset sim plant ...)    src/linumert_headless/services/
wtyczki (domeny doinstalowywane: stats, ...)                    src/linumert_headless/plugins.py, plugins/
porty/backendy: fake | linuxcnc | Plant                         src/linumert_headless/backends/
rdzeń bez zależności od transportu                              src/linumert/ (CAM, narzędzia, programy, config)
symulacja materiału/kolizji                                     src/linumert_sim/
wirtualna obrabiarka (C11 + Python)                             src/linumert_plant/, plant_core/
```
Złożenie aplikacji: `build_application()` w `src/linumert_headless/app.py`.

## Gdzie coś zmienić (czytaj tylko to)
| Zadanie | Pliki |
|---|---|
| Nowa funkcja jako wtyczka | `docs/PLUGINS.md`, wzorzec `plugins_examples/stats/` |
| Nowa operacja w rdzeniu | `app.py::register_operations`, model w `schema.py`, usługa w `services/` |
| Klient w innym języku / skrypt | `docs/SOCKET.md` (JSON-lines, bez zależności) |
| Generator G-code | `src/linumert/generators/` + `tests/test_gen_*.py` |
| Generator konfiguracji LinuxCNC | `src/linumert/machine/configgen*.py` |
| Szybkie jądra w C (hot path) | `native/` (`make native`), wiązanie `src/linumert_sim/native.py`, wzorzec `zmap.py::_cut_native` |
| Wirtualna maszyna / napędy | `src/linumert_plant/`, `plant_core/` |
| Co zostało do zrobienia | `python3 tools/roadmap.py next`, `list --status partial` |

## Komendy
```
make install        # venv + zależności (pip install -e ".[dev]")
make test           # pełne testy lokalne (bez LinuxCNC, Qt, X)
make native         # kompiluje i testuje rdzeń C (native/); make bench = numpy vs C
make lint           # ruff + strażnik "bez GUI"
make serve          # REST+WS na 127.0.0.1:8080
.venv/bin/linumertd serve --no-http --socket-port 8765    # tylko socket, bez FastAPI
.venv/bin/linumertctl operations --json                    # lista operacji
python3 tools/roadmap.py check                             # spójność roadmapy
```

## Protokół pracy nad jedną funkcją
1. `roadmap.py show ID` → zakres (`remaining`).
2. Napisz test (`tests/test_<temat>.py`), potem kod. Jedna funkcja = jeden mały przyrost.
3. `make lint test` zielone → `roadmap.py done ID --evidence …` → koniec.
Bezpieczeństwo (E-STOP, jog deadman, role) jest w rdzeniu i nie wolno go osłabiać wtyczką —
wtyczka nie dostaje dostępu do backendu maszyny inaczej niż przez operacje kontraktu.
