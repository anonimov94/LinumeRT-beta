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

## Przekazanie między sesjami — aktualizacja 2026-10-30

**Zacznij od sprawdzenia gałęzi i SHA, nie od ponownego wdrażania A-01/A-02.**
Właściciel zatwierdził A-01/A-02 z zachowaniem odziedziczonego rdzenia, a następnie
polecił wypchnąć zmiany i uzupełnić ten plik. Zgoda dotyczy publikacji gałęzi audytu;
nie jest zgodą na merge do `main`, uruchomienie sprzętu ani automatyczny odbiór P0/P1.

### Co wykonano i gdzie szukać dowodów

- Gałęzie do publikacji: `audit/a01-documentation` oraz oparta na niej
  `audit/a02-joint-map` (bieżąca, zawiera całość zmian i aktualne przekazanie).
  Sprawdź ich faktyczną dostępność przez `git ls-remote origin`; nie zakładaj,
  że `main` zawiera te zmiany. Ostatnio sprawdzony `main`: `57bc2c1`.
- **A-01 — partial:** poprawiony opis zaufania do wtyczek, generator `tools/stan.py`,
  raport `docs/STAN.md` i test zgodności z kontraktem. Implementacja gotowa lokalnie;
  do zamknięcia pozostaje niezależna recenzja. Commity: `aa76eb8`, `105e36f`.
- **A-02 — blocked na odbiorze:** regresja przed poprawką `28287cf` (21 nieudanych,
  4 udane przypadki), poprawka `1b62dd5`: `src/linumert/cnc/axis_map.py`, czytnik
  LinuxCNC i backend. Mapowanie z INI/NML, gantry, ABC, agregacja home/limit,
  odmowa niespójności i niejednoznacznego bazowania. Testy: `tests/test_linuxcnc_axis_map.py`.
- Ograniczenia: obsługiwane tylko `trivkins`; gantry wymaga synchronizacji;
  zmiana mapowania INI podczas działania wymaga ponownego rozruchu aplikacji.
  **STOP JOG wysyła ABORT dla całego ruchu**, także dla pojedynczej osi/prędkości zero.
  Opis `JogRequest.speed` w kontrakcie nadal mówi o zatrzymaniu osi — ujednolicić w A-03.
- Dowody: [raport audytu](docs/AUDYT_A01_A02.md) i [log](docs/AUDYT_A01_A02_LOCAL.log).
  Lint PASS; pełny przebieg z limitem 300 s PASS; po końcowych poprawkach 75 testów PASS.
  Pełny przebieg rozpoczęto przed ostatnimi poprawkami; dokładny zakres jest w raporcie.
  Domyślny limit 60 s wcześniej przerwał istniejący fuzzing symulacji; testów nie osłabiano.
  Te wyniki nie stanowią odbioru SIM ani sprzętu.

### Kolejność dalszych prac

1. **Niezależna recenzja A-01/A-02**, zwłaszcza grup HOME_SEQUENCE, zmiany INI,
   odmów przed poleceniami i zakresu ABORT. Nie oznaczaj etapów `done` bez wymaganego odbioru.
2. **D0 / LinuxCNC 2.9 SIM:** ustalić platformę testową; lokalnie brak LinuxCNC/HAL.
   Wykonać macierz z raportu: X/Y1/Y2/Z, przestawione jointy ABC, HOME ALL i grupy,
   home/limit, błędne INI/NML, JOG teleop oraz STOP w teleop/joint i przy awarii odczytu.
   Zachować wersję LinuxCNC, konfigurację i SHA. **NIEZWERYFIKOWANE NA SPRZĘCIE.**
3. **A-03 / jednostki JOG:** mm i mm/s kontra stopnie i stopnie/s, konwersja jednostek
   INI, G20/G21, continuous/incremental, deadman/STOP i zgodny opis kontraktu.
4. **A-04 / role:** bezpieczne domyślne ustawienia LinuxCNC, brak PIN/sekretu,
   wszystkie transporty, restart i wygaśnięcie sesji; ustalić inicjalizację poświadczeń D3.
5. **A-05 / wtyczki:** decyzja D4 o zaufanych wtyczkach z ograniczonym API lub izolacji
   procesu. Dostęp do usług nadal istnieje; A-01 poprawił dokumentację, nie izolację.
6. **A-06 / watchdog HAL:** utrata łączności/procesu, SIGSTOP, błędy STOP, restart;
   osobny odbiór HAL, bez zastępowania sprzętowego E-STOP/STO programem.
7. **A-07 / CI i raporty:** lint, testy Python/C, sanitizery, kontrakt, roadmapa;
   wyjaśnić stare logi E-STOP. Kolejność wcześniejszego CI wymaga decyzji D5.
   **A-08:** utrwalić pochodzenie rdzenia i decyzję o jego zachowaniu; nie przepisywać od zera.

Szczegóły kolejnych zakresów i decyzji: `docs/PLAN_AUDYTU_P0_P1.md`.
Przed zmianami bezpieczeństwa poza A-01/A-02 sprawdź, czy właściciel zatwierdził konkretny
zakres w bieżącej lub wcześniejszej sesji. Nowe funkcje/GUI/niezwiązane optymalizacje są wstrzymane.
Statusy utrzymuj narzędziem roadmapy; ten skrót jest przekazaniem, nie drugim rejestrem statusów.
Do lokalnych sprawdzeń używaj `.venv/bin/python` (systemowy Python nie ma pytest):
`make PYTHON=.venv/bin/python lint`, a pełny przebieg w tym środowisku:
`PYTEST_ADDOPTS='--timeout=300' make PYTHON=.venv/bin/python test`.
Nie przepisuj historycznego PASS jako wyniku nowej sesji.

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
