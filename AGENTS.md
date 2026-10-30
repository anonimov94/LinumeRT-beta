# AGENTS.md — instrukcja dla modeli pracujących na linumeRT headless (beta)

> **⛔ STOP — OBOWIĄZKOWY AUDYT CODEX / CLAUDE / KAŻDEGO AGENTA (2026-10-29)**
>
> **ZANIM rozpoczniesz nowe zadanie, wykonasz zmianę w kodzie, podejmiesz kolejny punkt roadmapy lub uznasz backend za gotowy — otwórz i przeczytaj CAŁY [CODEX_STOP_READ.md](CODEX_STOP_READ.md).**
> Zgłoszono problem P0 mapowania osi/jointów oraz krytyczne zagadnienia P1: jednostki JOG, role/uprawnienia, wtyczki, watchdog HAL. Podaj właścicielowi zwięzłe potwierdzenie lektury, aktualne dowody i plan weryfikacji; rozróżniaj potwierdzone błędy od ryzyk.
> **Wstrzymaj nowe funkcje / GUI / optymalizacje niezwiązane z audytem do decyzji właściciela.** W żadnym razie nie uznawaj testów fake/Plant za odbiór prawdziwego sprzętu. **Nie scalaj do main bez zgody.**
>

Czytaj TYLKO ten plik na start (≈2 min), potem tylko pliki ze swojego zadania.
Dokumenty tematyczne: `docs/PLUGINS.md` (wtyczki), `docs/SOCKET.md` (protokół socket), `docs/NATIVE.md` (rdzeń C),
`SAFETY.md` (bezpieczeństwo), `ROADMAP.md` (stan prac, generowany).

## Zasady (obowiązują zawsze)
1. **Bez GUI** w rdzeniu (strażnik: `tools/check_no_gui.py`). GUI powstaje na końcu jako klient kontraktu.
2. **Push i PR tylko na wyraźne polecenie właściciela;** testy lokalne (`make test`).
3. **Roadmapa po każdej ukończonej funkcji:**
   `python3 tools/roadmap.py done ID --evidence ŚCIEŻKA_KODU ŚCIEŻKA_TESTU`
   (sprawdź `python3 tools/roadmap.py next` — co dalej). Nie edytuj `ROADMAP.md` ręcznie.
4. `SAFETY.md` obowiązuje: nie osłabiaj ostrzeżeń, nie sugeruj, że ekran/oprogramowanie zastępuje sprzętowy E-STOP.
5. Sprzęt: wszystko, czego nie da się sprawdzić na atrapie/Plant, oznacz `NIEZWERYFIKOWANE NA SPRZĘCIE`.
6. Nowa funkcja = **wtyczka**, chyba że dotyka bezpieczeństwa/rdzenia (wtedy rdzeń + test).
7. Nowe pliki ≤ ~400 linii (istniejące duże: `schema.py`, `app.py`, jądra C — dziel przy okazji ich zmian, nie
   osobno); komentarze i komunikaty po polsku; nagłówek `SPDX-License-Identifier: GPL-2.0-or-later`.
8. **Gorąca pętla numeryczna → C** w `native/` (C11, bez zależności, `-ffp-contract=off`), Python zostaje cienkim
   wiązaniem + wersją zapasową i wzorcem; dodaj test parytetu z wersją Python (korpus + fuzzing, `LRT_NATIVE=0/1`)
   i pomiar (`tools/bench_*.py`). Opis, pomiary i „czego nie przenosić”: `docs/NATIVE.md`.
   **Reguły K-3xx istnieją w dwóch miejscach** (`engine.py` — tryb na żywo i wzorzec, `native/lrt_sim.c` —
   symulacja offline): zmiana reguły musi trafić w oba, inaczej padnie `tests/test_native_sim.py`.
9. Po zmianie operacji: `make contract` (regeneruje `api/contract.json`), potem `make lint test`.

## Architektura w 10 linijkach
```
transport (REST · WebSocket · SOCKET JSON-lines · CLI · SDK)   src/linumert_headless/transport/
kontrakt: rejestr operacji domena.akcja                         src/linumert_headless/contract.py
usługi domen (machine program tool cam offset sim plant ...)    src/linumert_headless/services/
wtyczki (domeny doinstalowywane: stats, ...)                    src/linumert_headless/plugins.py, plugins/
porty/backendy: fake | linuxcnc | Plant                         src/linumert_headless/backends/
rdzeń bez zależności od transportu                              src/linumert/ (CAM, narzędzia, programy, config)
symulacja materiału/kolizji (Python = wzorzec)                  src/linumert_sim/
szybkie jądra C: materiał, interpreter G-code, pętla symulacji  native/ (+ wiązanie linumert_sim/native*.py)
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
| Szybkie jądra w C (hot path) | `docs/NATIVE.md`, `native/` (`make native`), wiązania `src/linumert_sim/native.py`, `native_sim.py`; wzorzec `zmap.py::_cut_native` |
| Reguła kolizji/przeciążenia K-3xx | `src/linumert_sim/engine.py` **i** `native/lrt_sim.c` (parytet: `tests/test_native_sim.py`) |
| Wirtualna maszyna / napędy | `src/linumert_plant/`, `plant_core/` |
| Co zostało do zrobienia | `python3 tools/roadmap.py next`, `list --status partial` |

## Komendy
```
make install        # venv + zależności (pip install -e ".[dev]")
make test           # pełne testy lokalne (bez LinuxCNC, Qt, X)
make native         # kompiluje i testuje rdzeń C (native/); make bench = Python vs C (materiał, G-code, symulacja)
make test-c         # rdzeń dynamiki Plant (plant_core/, C11)
make lint           # ruff + strażnik "bez GUI"
make serve          # REST+WS na 127.0.0.1:8080
make serve-socket   # tylko socket JSON-lines na 8765, bez FastAPI (= linumertd serve --no-http --socket-port 8765)
.venv/bin/linumertctl operations --json                    # lista operacji
python3 tools/roadmap.py check                             # spójność roadmapy
```

## Protokół pracy nad jedną funkcją
1. `roadmap.py show ID` → zakres (`remaining`).
2. Napisz test (`tests/test_<temat>.py`), potem kod. Jedna funkcja = jeden mały przyrost.
3. `make lint test` zielone → `roadmap.py done ID --evidence …` → koniec.
Bezpieczeństwo (E-STOP, jog deadman, role) jest w rdzeniu i nie wolno go osłabiać wtyczką —
Docelowo wtyczki powinny sterować przez kontrakt. Obecnie `PluginApi.services` i `ctx.services`
udostępniają usługi rdzenia: ograniczenie jest konwencją, nie izolacją. Instaluj tylko zaufane
wtyczki; usunięcie bezpośredniego dostępu pozostaje zakresem audytu A-05.
