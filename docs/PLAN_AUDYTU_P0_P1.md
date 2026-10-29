# Plan działania po audycie P0/P1 (CODEX_STOP_READ.md)

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Claude · 2026-10-29 · stan: **PROPOZYCJA do decyzji właściciela** (nic z tego planu nie jest wdrożone)

Punkt odniesienia: `main` @ `57bc2c1`. Źródło zarzutów: [CODEX_STOP_READ.md](../CODEX_STOP_READ.md) (niezależny
przegląd; zalecenia, nie raport Codexa). Zasady: [AGENTS.md](../AGENTS.md), [SAFETY.md](../SAFETY.md).
Werdykt audytu pozostaje w mocy: **NIEGOTOWE DO RZECZYWISTEGO STEROWANIA CNC**.

## 1. Zasady wykonania

- **Wstrzymane do decyzji właściciela:** nowe funkcje, GUI, wtyczki 063/064, kolejne optymalizacje (B-xx).
- **Osobna gałąź na etap** (`audit/pN-…`), małe commity, **PR bez automatycznego merge**; `main` zmienia tylko
  właściciel albo za jego zgodą.
- **Test negatywny najpierw:** pierwszy commit etapu dodaje test, który *failuje na obecnym kodzie* i dowodzi błędu;
  dopiero kolejny commit go naprawia. Testów nie usuwamy ani nie osłabiamy, żeby uzyskać PASS.
- **Status etapu: PASS / FAIL / BLOCKED** z listą tego, czego nie dało się sprawdzić. Wynik na `fake`/Plant **nie jest**
  odbiorem LinuxCNC ani sprzętu (`NIEZWERYFIKOWANE NA SPRZĘCIE`).
- Nie osłabiamy E-STOP, limitów ani deadmana. Niczego nie nazywamy „zabezpieczeniem sprzętowym”, jeśli jest w programie.
- Po ukończeniu etapu: `tools/roadmap.py done A-0N --evidence …` (roadmapa jest jedynym rejestrem statusów).

## 2. Ograniczenie środowiska (ważne dla odbioru)

Na tym laptopie **nie ma LinuxCNC** (`linuxcnc`, `halcmd` ani modułu Python `linuxcnc`). Zachowany raport
`docs/LINUXCNC_LOCAL.json` (PASS) obejmuje zwykłą maszynę **XYZ**, w której indeks osi = indeks jointa, więc
**nie mógł wykryć błędu P0** (gantry z dwoma jointami Y). Konsekwencje:

| Można zrobić lokalnie | Wymaga LinuxCNC 2.9 SIM (BLOCKED, dopóki go nie ma) |
|---|---|
| testy jednostkowe na atrapie `stat` / `fake` | integracja joint↔oś, bazowanie gantry |
| zmiany kontraktu, autoryzacji, wtyczek | pomiar kroku JOG (błąd < 0,001 mm) w różnych jednostkach INI |
| testy transportów, ról, sesji | testy HAL: watchdog, `SIGSTOP`, utrata procesu |

**Decyzja D0:** skąd bierzemy LinuxCNC 2.9 SIM (VM Debian 12 + obraz LinuxCNC, kontener, osobna maszyna)? Bez tego
etapy 1, 2 i 5 mogą osiągnąć najwyżej status **BLOCKED na części integracyjnej**.

## 3. Stan zarzutów (co potwierdzono statycznie, 2026-10-29)

| ID | Zarzut | Dowód w kodzie | Status |
|---|---|---|---|
| P0 | `index(oś) == joint` | `backends/linuxcnc.py:193–199` (`_joint` = `names.index`); `cnc/linuxcnc_reader.py:131,134` (`homed`/`limit` per joint); `config/machines/router_gantry_steppers.yaml` (Y: `drives: [drv_y1, drv_y2]`) | **potwierdzone kodem**, brak testu na SIM |
| P1 | jednostki JOG | `linuxcnc.py:166,174` (prędkość/dystans bez konwersji; kontrakt „mm/s”, „mm”) | **hipoteza** — zależy od jednostek INI i trybu joint/teleop |
| P1 | role / dostęp lokalny | `contract.py:202` (brak `enforced` = brak kontroli), `access/__init__.py:155`, `transport/rest.py:55,73` (pusty token) | **potwierdzone**; część to świadomy tryb dev |
| P1 | wtyczki a usługi | `plugins.py:116` (`api.services` = cały słownik, w tym `machine`); handler dostaje `ctx.services` | **potwierdzone**; zdanie w `AGENTS.md:77` i docs jest **nieprawdziwe** |
| P1 | watchdog / fail-safe | `session.py:11` (sam kod mówi, że deadman ≠ funkcja bezpieczeństwa); brak powiązania z HAL | **potwierdzone jako luka** |
| P2 | brak CI | brak `.github/` | **potwierdzone** |
| P2 | niespójne liczby | `ARCHITEKTURA.md:45`, `API.md:38`, `README.md:23` mówią 86/85; kontrakt ma 92 | **potwierdzone** |
| P2 | log E-STOP vs PASS | `docs/LINUXCNC_ESTOP_FAIL.log` vs `LINUXCNC_LOCAL.json` | **niewyjaśnione** (nie dowodzi usterki) |

## 4. Etapy (kolejność wg audytu)

Rozmiar: S ≤ 1 dzień, M ≈ kilka dni, L ≈ tydzień+. To szacunki robocze, nie zobowiązania.

### A-01 · Uczciwość dokumentacji (S) — bez zmiany zachowania
- Poprawić fałszywe zdanie o wtyczkach (`AGENTS.md:77`, `docs/PLUGINS.md`, komentarze) na prawdziwe: *„wtyczka to kod w
  procesie aplikacji; dostęp do usług jest ograniczony konwencją, nie izolacją”* — do czasu etapu A-04.
- Liczby operacji/testów **generować narzędziem** (`tools/stan.py` → `docs/STAN.md`), a w README/ARCHITEKTURA/API
  odsyłać do niego zamiast wpisywać ręcznie. Test pilnuje zgodności z `api/contract.json`.
- Odbiór: `make lint test` + test spójności liczb. Status docelowy: PASS.

### A-02 · P0 — jawny model joint↔oś (M–L)
- **Model:** `AxisMap` budowany z `[TRAJ]COORDINATES`, `[KINS]` i `stat` (nie z kolejności liter): `axis → [joint…]`,
  `joint → axis`, rodzaj osi (liniowa/obrotowa), duplikaty (gantry). Brak lub niespójność konfiguracji ⇒ **bezpieczna
  odmowa** (`SafetyRefused`), a nie zgadywanie.
- **Użycie:** `home(oś)` → wszystkie jointy osi (kolejność wg HOME_SEQUENCE); `homed(oś)` = wszystkie jointy
  zbazowane; `limit(oś)` = którykolwiek joint na limicie; JOG w teleop po indeksie *osi*, w trybie joint po *jointcie*.
- **Test negatywny przed poprawką (atrapa `stat`):** X/Y1/Y2/Z (Z = joint 3 ≠ 2), A/B/C, niezależne flagi
  home/limit, konfiguracja sprzeczna ⇒ odmowa.
- **Odbiór:** testy jednostkowe PASS lokalnie; **integracja LinuxCNC 2.9 SIM na gantry = BLOCKED do rozstrzygnięcia D0**.
- Ryzyko: semantyka `command.home` dla pary gantry (jeden komunikat czy po jointcie) — **do potwierdzenia na SIM**,
  nie zakładam odpowiedzi.

### A-03 · P1 — jednostki i poprawność JOG (M)
- **Kontrakt:** osie liniowe w mm i mm/s, obrotowe w stopniach i °/s (osobne pola lub jawne `unit`), dystans dodatni,
  znak z prędkości.
- **Konwersja do jednostek maszyny** z INI (`LINEAR_UNITS`, `ANGULAR_UNITS`), niezależnie od G20/G21 (które dotyczą
  programu, nie JOG) — **hipoteza do potwierdzenia na SIM**.
- **Testy:** INI mm/inch, osie XYZ i ABC, continuous/incremental, deadman, STOP, dystans ujemny/zero, NaN.
  Na atrapie sprawdzamy konwersję i walidację; **krok < 0,001 mm i jednostki kątowe — tylko na SIM (BLOCKED bez D0)**.

### A-04 · P1 — autoryzacja (M)
- **Bezpieczne domyślne dla backendu `linuxcnc`:** brak PIN-ów/sekretu ⇒ operacje ruchu, konfiguracji i serwisowe
  **odmawiane** (nie „rola serwisowa”); tryb deweloperski tylko jawnie (`--insecure-local`) i tylko dla `fake`.
- Rozdzielić odczyt / sterowanie / serwis; pusty token nie uprawnia do ruchu na rzeczywistym backendzie.
- **Testy:** każdy transport (REST, WebSocket, socket TCP, socket Unix, CLI) × {brak tokenu, zła rola, poprawna rola} ×
  {odczyt, ruch, serwis}; wygaśnięcie i restart sesji.
- **Decyzja D3:** jak inicjalizować PIN-y na świeżej instalacji (komenda offline `linumertctl access init`?).

### A-05 · P1 — wtyczki (M)
- **Decyzja D4 (rekomendacja: A, potem B tylko jeśli potrzebne):**
  **A.** zaufane wtyczki + *fasada*: `PluginApi`/`ctx` bez słownika usług; wtyczka dostaje tylko widoki tylko-do-odczytu
  (`program.read`, `tools.read`, ścieżki) i `call(operacja)` przez kontrakt (role, limiter, `safety`, deadman).
  Model zagrożeń opisany jawnie: **to nie jest sandbox** (Python w jednym procesie można obejść refleksją).
  **B.** izolacja procesu (wtyczka jako osobny proces, JSON-lines po sockecie) — większy koszt, tylko dla wtyczek
  niezaufanych.
- **Testy:** wtyczka nie może uzyskać `machine` przez `api` ani `ctx`; próba wywołania operacji ruchu bez uprawnień =
  odmowa; dokumentacja granic zaufania.

### A-06 · P1 — watchdog, utrata procesu i ścieżka zatrzymania (L)
- Projekt fail-safe odrębny od HMI/API: heartbeat aplikacji → `watchdog` w HAL → łańcuch E-STOP; sprzętowy E-STOP/STO
  niezależny od wszystkiego powyżej. **Software nie jest zabezpieczeniem** (zob. SAFETY.md).
- **Testy lokalne (atrapa):** utrata WebSocket/socketu, błąd `jog_stop` (ponowienia → eskalacja do E-STOP), zamknięcie
  procesu, przerwanie wątku pętli stanu, fałszywe potwierdzenie zatrzymania.
- **BLOCKED bez LinuxCNC/HAL:** `SIGSTOP` procesu, zachowanie watchdoga HAL, restart. Testy na prawdziwym sprzęcie —
  dopiero po osobnej ocenie ryzyka i zatwierdzeniu.

### A-07 · P2 — CI i powtarzalne raporty (M)
- `.github/workflows/`: `make lint`, `make test`, `make test-c`, `make native`, sanitizery C (ASan/UBSan dla `native/`
  i `plant_core/`), zgodność `api/contract.json`, `tools/roadmap.py check`. Raporty PASS **generowane**, nie przepisywane.
- Wyjaśnić `LINUXCNC_ESTOP_FAIL.log` jednym jednoznacznym testem z identyfikacją próby i commita.
- **Propozycja zmiany kolejności:** CI (bez sanitizerów) warto zrobić **zaraz po A-01**, bo daje dowód dla wszystkich
  kolejnych etapów — to decyzja właściciela (D5), audyt stawia je na końcu.

### A-08 · Kierunek: odziedziczony rdzeń vs nowe wdrożenie (decyzja, nie kod)
- Opisać w `PROVENANCE.md` i `docs/DECYZJE.md`, co jest odziedziczone z linumeRT, co nowe, i co z tego wynika dla
  audytu i licencji. **Nie przepisuję rdzenia samowolnie.**

## 5. Decyzje wymagane od właściciela

| ID | Pytanie | Rekomendacja |
|---|---|---|
| D0 | Skąd LinuxCNC 2.9 SIM do testów integracyjnych? | VM Debian 12 + obraz LinuxCNC 2.9 (lub kontener); bez tego A-02/03/06 zostają BLOCKED |
| D1 | Zatwierdzasz zakres i kolejność A-01…A-08? | tak, z wyjątkiem D5 |
| D2 | Zakres A-01: tylko poprawa dokumentacji przed jakimkolwiek kodem? | tak — najtańszy sposób usunięcia fałszywego twierdzenia |
| D3 | Jak inicjalizować PIN-y/sekret na świeżej instalacji? | komenda offline, bez domyślnych haseł |
| D4 | Wtyczki: zaufane + fasada (A) czy izolacja procesu (B)? | A teraz, B odłożyć |
| D5 | CI wcześniej niż na końcu? | tak, po A-01 |
| D6 | Kierunek: odziedziczony rdzeń czy od zera (A-08)? | decyzja właściciela; nie zgaduję |

## 6. Czego ten plan nie robi

Nie zmienia kodu sterowania, nie uruchamia niczego na maszynie, nie scala do `main`, nie wznawia nowych funkcji
(063/064, B-xx, GUI) i nie twierdzi, że cokolwiek jest bezpieczne. Statusy etapów zmieniamy dopiero z dowodami.
