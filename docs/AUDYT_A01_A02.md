# Weryfikacja A-01 i A-02 — 2026-10-30

SPDX-License-Identifier: GPL-2.0-or-later

## Zakres i decyzja

Właściciel zatwierdził w rozmowie rozpoczęcie A-01 i A-02, na osobnych gałęziach,
z zachowaniem odziedziczonego rdzenia. Nie obejmuje to pozostałych P1, nowych funkcji,
push, PR ani scalenia do main. Gałąź A-02 bazuje na zmianach A-01.

## Dowody przed poprawką

- A-01: `aa76eb8` dodaje test raportu; uruchomienie przez `.venv/bin/python -m pytest
  tests/test_stan.py -q` kończy się brakiem `docs/STAN.md`.
- A-02: `28287cf` dodaje 25 przypadków regresyjnych bez poprawki backendu.
  Wynik: 21 nieudanych, 4 udane. Zamiast `home(3)` dla Z w X/Y1/Y2/Z wysyłane
  jest `home(2)`; Y pomija stan drugiego jointa. Odmowy błędnej konfiguracji nie działają.
- Odtworzenie: osobny checkout tych commitów i wykonanie odpowiednich testów.
  Nie uruchamiać backendu na fizycznej maszynie.

## A-01 — dokumentacja

Usunięto zapewnienie o izolacji wtyczek: `PluginApi.services` i `ctx.services`
dają dostęp do usług, a konwencja nie jest sandboxem. Nie zmieniono API wtyczek.
`tools/stan.py` generuje `docs/STAN.md` z `api/contract.json` oraz kolekcji pytest.
README, API i ARCHITEKTURA odsyłają do tego raportu. Kolekcja testów nie oznacza PASS.

## A-02 — zachowanie

- `AxisMap` wiąże kolejność jointów z `[KINS]KINEMATICS` (trivkins), ich liczbą,
  `[TRAJ]COORDINATES`, typami jointów i `HOME_SEQUENCE`. Obsługuje duplikaty oraz ABC.
- INI pochodzi z `stat.ini_filename` działającej instancji; `axis_mask`, `joints`
  i `kinematics_type` muszą odpowiadać mapie. Brak INI, niepełne flagi lub niespójność
  powodują odmowę. Ponowny odczyt sprawdza konfigurację i stan. Zmiana mapowania/ścieżki
  INI podczas działania wymaga ponownego rozruchu aplikacji.
- Inne kinematyki niż trivkins są odrzucane, bez zgadywania. Gantry wymaga BOTH.
- `homed` osi = wszystkie jointy zbazowane; `limit_hit` = co najmniej jeden limit.
  Pozycje nadal pochodzą z kartezjańskiego indeksu osi.
- Bazowanie osi z jednym jointem używa jego numeru. Gantry wymaga wspólnej sekwencji
  synchronizacji; wysyłane jest jedno polecenie do członka z ujemną `HOME_SEQUENCE`.
  Niesynchronizowana brama oraz grupa obejmująca inną oś przy żądaniu jednej osi są
  odrzucane. `home(None)` pozostawia kolejność LinuxCNC, po walidacji kompletności
  i ciągłości sekwencji. Zmiana trybu musi być potwierdzona przed wysłaniem HOME.
- JOG nadal używa indeksu osi w teleop. Nie dodano JOG w trybie joint. Walidacja
  następuje przed zmianami trybu. Jednostki JOG pozostają zadaniem A-03.
- **Zmiana STOP:** backend LinuxCNC wysyła `abort()` także dla zatrzymania pojedynczej
  osi JOG i prędkości zero. Zatrzymanie obejmuje cały ruch, a nie tylko wskazaną oś.
  Nie zależy od poprawności mapy ani odczytu NML. Jest to żądanie programowe;
  test atrapy nie potwierdza fizycznego zatrzymania.

## Podstawa semantyki LinuxCNC 2.9

- [trivkins](https://linuxcnc.org/docs/2.9/html/man/man9/trivkins.9.html): kolejność
  jointów określa parametr `coordinates`; domyślnie XYZABCUVW, niezależnie od TRAJ.
- [Bazowanie](https://linuxcnc.org/docs/2.9/html/config/ini-homing.html): ujemna
  sekwencja uruchamia grupę synchronizacji; HOME ALL stosuje kolejność sekwencji.
- [API Python](https://linuxcnc.org/docs/2.9/html/config/python-interface.html):
  `ini_filename`, `joints`, `kinematics_type` oraz kartezjańskie pozycje.
- [Źródło modułu 2.9](https://github.com/LinuxCNC/linuxcnc/blob/2.9/src/emc/usr_intf/axis/extensions/emcmodule.cc):
  `Stat_limit` i `Stat_homed` odczytują tablicę jointów (opis `limit` w dokumentacji
  używa słowa „axis”, dlatego sprawdzono również implementację).

## Wykonane sprawdzenia lokalne

Kod poprawki: `1b62dd5`. Wyniki poleceń: [log lokalny](AUDYT_A01_A02_LOCAL.log).

| Sprawdzenie | Wynik |
|---|---|
| `make PYTHON=.venv/bin/python lint` | PASS: ruff i strażnik bez GUI |
| Pierwsze `make PYTHON=.venv/bin/python test` | FAIL: limit 60 s w istniejącym fuzzingu symulacji |
| `PYTEST_ADDOPTS='--timeout=300' make PYTHON=.venv/bin/python test` | PASS: pełny przebieg, kod wyjścia 0 |
| Końcowe regresje mapowania, czytnika, startu i usługi maszyny | PASS: 75 testów |
| `make PYTHON=.venv/bin/python contract` | PASS: brak zmian w kontrakcie |
| `tools/roadmap.py check`, `git diff --check` | PASS |

Pełny przebieg rozpoczął się przed ostatnimi poprawkami wykrywania zmiany INI
oraz odmowy bazowania dodatniego członka grupy obejmującej inną oś. Te poprawki
sprawdzono następnie całym zestawem 75 testów wymienionych w logu. Końcowa kolekcja
jest w `STAN.md`. Nie zmieniano testów symulacji ani domyślnego limitu repozytorium.
Przebieg emituje ostrzeżenie Starlette o wycofywaniu obsługi httpx.

A-01: wdrożenie i sprawdzenia lokalne zakończone, niezależna recenzja pozostaje
otwarta (roadmapa: partial). A-02: poprawka lokalna i regresje zakończone,
odbiór integracyjny oraz niezależna recenzja pozostają otwarte (roadmapa: blocked).

## Otwarty odbiór

**BLOCKED: LinuxCNC 2.9 SIM i niezależna recenzja A-02.** Lokalnie brak programu
`linuxcnc`, `halcmd` i modułu Python `linuxcnc`. Nie instalowano platformy SIM;
wybór środowiska D0 pozostaje otwarty. Nie wykonywano niezależnej recenzji.

Na wybranej platformie wymagane są: X/Y1/Y2/Z i przestawione jointy ABC, HOME ALL,
bazowanie pojedynczego jointa/grupy gantry, niezależne flagi home/limit, odmowy
niezgodnego INI/stanu i niesynchronizowanej bramy, JOG teleop oraz STOP w trybie
teleop/joint i przy awarii odczytu. Wyniki muszą wskazywać wersję LinuxCNC,
konfigurację i SHA badanego kodu. Nie przenosić wyniku atrapy na SIM.

**NIEZWERYFIKOWANE NA SPRZĘCIE.** Sprzętowy E-STOP/STO pozostaje niezależny.
Projekt nadal nie jest gotowy do rzeczywistego sterowania CNC.
