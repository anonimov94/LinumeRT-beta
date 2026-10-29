# ROADMAP — linumeRT headless (beta)

> Plik GENEROWANY z `roadmap/plan.json` przez `python3 tools/roadmap.py render`. Nie edytuj ręcznie.

Aktualizacja: 2026-10-29 · planowane: 19 · częściowe: 64 · ukończone: 10 · GUI (na końcu): 5 · zablokowane: 1

- Po ukończeniu funkcji: python3 tools/roadmap.py done ID --evidence ŚCIEŻKA [...]. Narzędzie samo przepisuje ROADMAP.md.
- Wszystko dotyczące prawdziwego sprzętu: NIEZWERYFIKOWANE NA SPRZĘCIE.
- Pozycje numerowane 001–084 pochodzą z rejestru linumeRT (stan 2026-10-25); status 'origin.status' to stan tam, nie dowód w beta (verified_in_beta=false do czasu sprawdzenia).

| ID | Obszar | Status | Zakres |
|---|---|---|---|
| A-00 | audit | ukończone | Audyt: plan działania P0/P1 zapisany w git (docs/PLAN_AUDYTU_P0_P1.md), wstrzymanie nowych funkcji do decyzji |
| A-01 | audit | planowane | Audyt: uczciwość dokumentacji (fałszywe zdanie o wtyczkach, liczby generowane narzędziem) |
| A-02 | audit | zablokowane | Audyt P0: jawny model joint↔oś (gantry X/Y1/Y2/Z, osie obrotowe), bezpieczna odmowa |
| A-03 | audit | planowane | Audyt P1: jednostki i poprawność JOG (liniowe mm, obrotowe stopnie, jednostki INI) |
| A-04 | audit | planowane | Audyt P1: autoryzacja — bezpieczne domyślne dla backendu linuxcnc, rozdział odczyt/sterowanie/serwis |
| A-05 | audit | planowane | Audyt P1: wtyczki — fasada bez dostępu do usług sterowania, model zagrożeń |
| A-06 | audit | planowane | Audyt P1: watchdog HAL, utrata procesu i ścieżka zatrzymania (fail-safe) |
| A-07 | audit | planowane | Audyt P2: CI (lint, testy, C, sanitizery) i powtarzalne raporty |
| A-08 | audit | planowane | Audyt P2: decyzja o kierunku — odziedziczony rdzeń vs nowe wdrożenie (PROVENANCE/DECYZJE) |
| B-01 | core | ukończone | System wtyczek (plugins.py): katalog plugins/ + entry points, manifest, izolacja błędów |
| B-02 | transport | ukończone | Transport socket JSON-lines (TCP + Unix), tryb --no-http |
| B-03 | tooling | ukończone | Roadmapa beta + tools/roadmap.py (list/next/done/render/check) |
| B-04 | docs | ukończone | AGENTS.md i mapa repo dla modeli o małym kontekście |
| B-05 | core | planowane | Rdzeń jako pakiet bez GUI: wydzielenie funkcji domen do wtyczek (kolejne domeny) |
| B-06 | docs | ukończone | LICENSE (GPL-2.0) i SAFETY.md (brak funkcji bezpieczeństwa, wyłączenie odpowiedzialności) |
| B-07 | core | ukończone | Rdzeń natywny C (native/): usuwanie materiału 2.5D 30x szybciej niż numpy, test parytetu |
| B-08 | core | ukończone | Ocena gorących ścieżek pomiarem: kolizje, leksyka i estimate_canon świadomie w Pythonie (docs/NATIVE.md) |
| B-09 | core | ukończone | Interpreter podzbioru G-code w C (native/lrt_gcode.c): 24x szybciej, parytet z Pythonem na 3000 losowych programów |
| B-10 | core | ukończone | Pętla symulacji offline w C (native/lrt_sim.c): 52–57x szybciej, parytet zdarzeń K-3xx z Pythonem; dystanse z math.dist |
| 001 | M0 | częściowe | Szkielet repozytorium, CI i licencja |
| 002 | M0 | częściowe | Wytyczne IP i rejestr pochodzenia |
| 003 | M0 | częściowe | Spike: LinuxCNC 2.9 w środowisku agenta |
| 004 | M0 | częściowe | Konfiguracja sim 3 osie z QtDragon |
| 005 | M0 | częściowe | Kopia bazowa ekranu QtDragon |
| 006 | M0 | częściowe | Rdzeń: model stanu maszyny i atrapa |
| 007 | M0 | częściowe | Katalog alarmów i tłumaczenia |
| 008 | M0 | częściowe | Bufor i bramka G0 |
| 009 | M1 | częściowe | Specyfikacja wirtualnej maszyny Plant |
| 010 | M1 | częściowe | Model obrabiarki machine.yaml (jedno źródło prawdy) |
| 011 | M1 | częściowe | Plant: rdzeń dynamiki osi (C) |
| 012 | M1 | częściowe | Plant: emulacja napędów CiA 402 i krokowców |
| 013 | M1 | częściowe | Biblioteka napędów wirtualnych: szablony, kopiowanie, parametryzacja |
| 014 | M1 | częściowe | Plant: łańcuch kinematyczny, przejazdy, zderzaki, krańcówki, I/O |
| 015 | M1 | częściowe | Bazowanie po rozruchu: krańcówka, indeks, twardy zderzak, absolut, napęd |
| 016 | M1 | częściowe | Plant: serwer LRT-NET |
| 017 | M1 | częściowe | Komponent HAL lrt_net |
| 018 | M1 | częściowe | Konfiguracja LinuxCNC dla Plant (3 osie) |
| 019 | M1 | częściowe | Ograniczenia programowe, strefy zakazane i wyrocznia testowa |
| 020 | M1 | częściowe | Magazyn narzędzi, pozycje wymiany i kolizje w Plant |
| 021 | M1 | częściowe | Plant: wrzeciono VFD przez Modbus |
| 022 | M1 | częściowe | Plant: panel sterowania i pulpit MPG |
| 023 | M1 | częściowe | Edytor wirtualnej obrabiarki w panelu Plant |
| 024 | M1 | częściowe | Plant: scenariusze i raport prototypu |
| 025 | M1 | częściowe | Skrypty maszyn wirtualnych (VirtualBox) |
| 026 | M1 | częściowe | Bufor i bramka G1 (prototyp P0) |
| 027 | M2 | częściowe | Własny system projektowy ekranu |
| 028 | gui_later | GUI (na końcu) | Kompozycja ekranu głównego |
| 029 | gui_later | GUI (na końcu) | Tryby, JOG i pulpit MPG |
| 030 | gui_later | GUI (na końcu) | MDI i klawiatura ekranowa |
| 031 | M2 | częściowe | AUTO i wznowienie od linii |
| 032 | M2 | częściowe | Baza narzędzi z typami |
| 033 | M2 | częściowe | Zerowanie detalu i sonda |
| 034 | M2 | częściowe | Ręczna zmiana narzędzia |
| 035 | M2 | częściowe | Alarmy na ekranie |
| 036 | M2 | częściowe | Poziomy dostępu |
| 037 | gui_later | GUI (na końcu) | Język polski i angielski |
| 039 | M3 | częściowe | Format .lnx i BaseMacroGenerator |
| 040 | M3 | częściowe | Generatory: nagłówek, koniec, narzędzie, planowanie |
| 041 | M3 | częściowe | Generatory: kieszenie |
| 042 | M3 | częściowe | Generatory: wiercenie i gwintowanie |
| 043 | M3 | częściowe | Generatory: rowki, czopy, kontur |
| 044 | M3 | częściowe | Lekser G-code i walidacja w edytorze |
| 045 | M3 | częściowe | Panel programu dialogowego |
| 046 | M3 | częściowe | Podglądy 2D w formularzach |
| 047 | M3 | częściowe | Menedżer programów i pliki .lnx |
| 048 | M3 | częściowe | Biblioteka podprogramów o-word |
| 049 | M3 | częściowe | Test technologiczny na Plant |
| 051 | M4 | częściowe | Ścieżka z programu |
| 052 | M4 | częściowe | Proces symulacji |
| 053 | M4 | częściowe | Czas obróbki i porównanie z Plant |
| 054 | M4 | częściowe | Przygotówka |
| 055 | M4 | częściowe | Materiał 2.5D |
| 056 | M4 | częściowe | Reguły kolizji lite |
| 057 | gui_later | GUI (na końcu) | Widok 3D symulacji |
| 058 | M4 | częściowe | Typy narzędzi w symulacji |
| 059 | M4 | częściowe | Raport symulacji i eksport STL |
| 061 | M5 | częściowe | machine.yaml: napędy i wejścia rzeczywiste |
| 062 | M5 | częściowe | Generator INI/HAL: sim, Plant, step/dir |
| 063 | M5 | planowane | Generator EtherCAT (lcec, CiA 402) |
| 064 | M5 | planowane | Wrzeciono RS485 w generatorze |
| 065 | M5 | częściowe | Kinematyki 4 i 5 osi |
| 066 | M5 | częściowe | Automatyczna zmiana narzędzia |
| 067 | M5 | planowane | Kreator konfiguracji maszyny |
| 068 | M5 | planowane | Test latencji i raport kwalifikacji |
| 069 | M5 | częściowe | Diagnostyka napędów |
| 070 | M5 | częściowe | Łańcuch E-STOP i bezpieczeństwo |
| 071 | M5 | planowane | Asystent strojenia na Plant |
| 073 | M6 | planowane | Wtyczki deklaratywne: format i silnik |
| 074 | M6 | planowane | Menedżer wtyczek |
| 075 | M6 | planowane | Panel cykli i skryptów |
| 076 | M6 | planowane | Repozytorium społeczności i przykłady |
| 077 | M6 | częściowe | Instalator dla Debiana 12 + LinuxCNC 2.9 |
| 078 | M6 | częściowe | Pierwsze uruchomienie i linumert doctor |
| 079 | M6 | częściowe | Dokumentacja użytkownika |
| 080 | M6 | częściowe | Przegląd IP przed wydaniem |
| 081 | M6 | częściowe | Twardnienie |
| 082 | M6 | częściowe | Pełna regresja na Plant |
| 083 | M6 | planowane | Wydanie v0.5.0-alpha |
| 084 | M6 | planowane | Retrospektywa i kolejne półrocze |

## Pozostały zakres

### A-01 Audyt: uczciwość dokumentacji (fałszywe zdanie o wtyczkach, liczby generowane narzędziem)
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-01
- Czeka na decyzję właściciela D1/D2

### A-02 Audyt P0: jawny model joint↔oś (gantry X/Y1/Y2/Z, osie obrotowe), bezpieczna odmowa
- Część integracyjna wymaga LinuxCNC 2.9 SIM (decyzja D0)
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-02

### A-03 Audyt P1: jednostki i poprawność JOG (liniowe mm, obrotowe stopnie, jednostki INI)
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-03
- Czeka na decyzję właściciela (D1, D0/D3/D4/D5/D6 wg etapu)

### A-04 Audyt P1: autoryzacja — bezpieczne domyślne dla backendu linuxcnc, rozdział odczyt/sterowanie/serwis
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-04
- Czeka na decyzję właściciela (D1, D0/D3/D4/D5/D6 wg etapu)

### A-05 Audyt P1: wtyczki — fasada bez dostępu do usług sterowania, model zagrożeń
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-05
- Czeka na decyzję właściciela (D1, D0/D3/D4/D5/D6 wg etapu)

### A-06 Audyt P1: watchdog HAL, utrata procesu i ścieżka zatrzymania (fail-safe)
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-06
- Czeka na decyzję właściciela (D1, D0/D3/D4/D5/D6 wg etapu)

### A-07 Audyt P2: CI (lint, testy, C, sanitizery) i powtarzalne raporty
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-07
- Czeka na decyzję właściciela (D1, D0/D3/D4/D5/D6 wg etapu)

### A-08 Audyt P2: decyzja o kierunku — odziedziczony rdzeń vs nowe wdrożenie (PROVENANCE/DECYZJE)
- Plan: docs/PLAN_AUDYTU_P0_P1.md §4 A-08
- Czeka na decyzję właściciela (D1, D0/D3/D4/D5/D6 wg etapu)

### B-05 Rdzeń jako pakiet bez GUI: wydzielenie funkcji domen do wtyczek (kolejne domeny)
- Przenosić po jednej domenie (np. sim, plant) do wtyczek, gdy rdzeń pozostaje stabilny

### 001 Szkielet repozytorium, CI i licencja
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 002 Wytyczne IP i rejestr pochodzenia
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 003 Spike: LinuxCNC 2.9 w środowisku agenta
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 004 Konfiguracja sim 3 osie z QtDragon
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 005 Kopia bazowa ekranu QtDragon
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 006 Rdzeń: model stanu maszyny i atrapa
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 007 Katalog alarmów i tłumaczenia
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 008 Bufor i bramka G0
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 009 Specyfikacja wirtualnej maszyny Plant
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 010 Model obrabiarki machine.yaml (jedno źródło prawdy)
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 011 Plant: rdzeń dynamiki osi (C)
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 012 Plant: emulacja napędów CiA 402 i krokowców
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 013 Biblioteka napędów wirtualnych: szablony, kopiowanie, parametryzacja
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 014 Plant: łańcuch kinematyczny, przejazdy, zderzaki, krańcówki, I/O
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 015 Bazowanie po rozruchu: krańcówka, indeks, twardy zderzak, absolut, napęd
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 016 Plant: serwer LRT-NET
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 017 Komponent HAL lrt_net
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 018 Konfiguracja LinuxCNC dla Plant (3 osie)
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 019 Ograniczenia programowe, strefy zakazane i wyrocznia testowa
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 020 Magazyn narzędzi, pozycje wymiany i kolizje w Plant
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 021 Plant: wrzeciono VFD przez Modbus
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 022 Plant: panel sterowania i pulpit MPG
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 023 Edytor wirtualnej obrabiarki w panelu Plant
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 024 Plant: scenariusze i raport prototypu
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 025 Skrypty maszyn wirtualnych (VirtualBox)
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 026 Bufor i bramka G1 (prototyp P0)
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 027 Własny system projektowy ekranu
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 031 AUTO i wznowienie od linii
- D38-B: odzyskiwanie po Abort/E-STOP lub wymianie narzędzia i wykonanie helisy/łuku z zakładką; pełny odbiór run-from-line.

### 032 Baza narzędzi z typami
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 033 Zerowanie detalu i sonda
- Scenariusze Plant probe_z_touchplate i probe_corner (plant/scenarios) oraz sonda płytkowa (probe.type plate) — nie istnieją.
- Logika sondy QtDragon (Basic/Versa) w nowym stylu i klik przez GUI na pulpicie; ręczny odbiór G54–G59.3 w HMI.
- Ekran kalibracji sondy w HMI (D36) i wykorzystanie poprawki w cyklach sondowania; kalibracja na sprzęcie.

### 034 Ręczna zmiana narzędzia
- Rozliczyć dialog ToolDB, anulowanie W-2130 i opcjonalne wycofanie Z.

### 035 Alarmy na ekranie
- Pełne mapowanie kodów napędów/VFD i scenariusze alarmów z promptu.

### 036 Poziomy dostępu
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 039 Format .lnx i BaseMacroGenerator
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 040 Generatory: nagłówek, koniec, narzędzie, planowanie
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 041 Generatory: kieszenie
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 042 Generatory: wiercenie i gwintowanie
- Odbiór wszystkich wzorów, cykli, walidacji i podglądu przez GUI.

### 043 Generatory: rowki, czopy, kontur
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 044 Lekser G-code i walidacja w edytorze
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 045 Panel programu dialogowego
- Komplet operacji kroków, walidacja przy polach i kryteria oryginalnego promptu.

### 046 Podglądy 2D w formularzach
- Wszystkie prymitywy, wymiary i preview_2d wszystkich generatorów.

### 047 Menedżer programów i pliki .lnx
- Pełny menedżer, szablony i odbiór bezpiecznych operacji plikowych.

### 048 Biblioteka podprogramów o-word
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 049 Test technologiczny na Plant
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 051 Ścieżka z programu
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 052 Proces symulacji
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 053 Czas obróbki i porównanie z Plant
- Pełny wynik per narzędzie/krok i odbiór zakresu modelu; wyniki nie są ogólną gwarancją ±10%.

### 054 Przygotówka
- Zweryfikować w beta: kod przejęty z linumeRT jako ukończony; wskazać test beta jako dowód (tools/roadmap.py done)

### 055 Materiał 2.5D
- Pełny odbiór dokładności objętości ±2% i wydajności.

### 056 Reguły kolizji lite
- Pełna macierz reguł i tryb offline; nie przywracać komend E-STOP z symulacji.

### 058 Typy narzędzi w symulacji
- Pełne profile i K-303, obwiednia STL oraz odbiór stemplowania.

### 059 Raport symulacji i eksport STL
- Spójna droga offline „Symuluj” z panelu dialogowego i plików.

### 061 machine.yaml: napędy i wejścia rzeczywiste
- Pulpit (MPG, przyciski) i E-STOP rzeczywisty w sekcji hardware.
- Raport konkursu 03.

### 062 Generator INI/HAL: sim, Plant, step/dir
- Nazwy pinów Mesa i całe wyjście hardware: NIEZWERYFIKOWANE NA SPRZĘCIE.
- EtherCAT (063), wrzeciono PWM/mb2hal (064).

### 065 Kinematyki 4 i 5 osi
- Pełna fizyka osi obrotowych, generator kinematyk, DRO/TCP i five_axis_demo.

### 066 Automatyczna zmiana narzędzia
- Podpięcie makra do INI sim/Plant i generatora konfiguracji, widok magazynu, scenariusze ATC, walidacja stref wymiany, karuzela i parasol, dziennik transakcyjny i RECOVERY_REQUIRED po E-STOP.

### 069 Diagnostyka napędów
- Dekoder CiA402, wykresy napędów, ethercat slaves/master i test fault.

### 070 Łańcuch E-STOP i bezpieczeństwo
- Pełny generator i odbiór toru sprzętowego oraz niezależnego nadzoru PC; bez osłabiania kontraktu safety.

### 077 Instalator dla Debiana 12 + LinuxCNC 2.9
- Instalator /opt, update/rollback/uninstall, idempotencja, odbiór live USB/instalacji i latencji.

### 078 Pierwsze uruchomienie i linumert doctor
- Wersje/działanie LinuxCNC/HAL, uprawnienia, Plant, latencja i kreator pierwszego uruchomienia.

### 079 Dokumentacja użytkownika
- Komplet podręcznika dla zakresu 079; nie dokumentować planowanych funkcji jako działających.

### 080 Przegląd IP przed wydaniem
- Pełny audyt przed wydaniem, przegląd podobieństwa i wyniki sprawdzenia nazwy.

### 081 Twardnienie
- Pełny przegląd uprawnień/nasłuchu/limitów oraz pip-audit i raport.

### 082 Pełna regresja na Plant
- suite_all 3× PASS i naprawa OD-01: zielona macierz mimo CRASH/COVER_CRASH.

## Dowody ukończenia

- **A-00** — `docs/PLAN_AUDYTU_P0_P1.md`, `CODEX_STOP_READ.md`
- **B-01** — `src/linumert_headless/plugins.py`, `tests/test_plugins.py`
- **B-02** — `src/linumert_headless/transport/socket.py`, `tests/test_socket.py`
- **B-03** — `roadmap/plan.json`, `tools/roadmap.py`, `tests/test_roadmap.py`
- **B-04** — `AGENTS.md`, `docs/PLUGINS.md`, `docs/SOCKET.md`
- **B-06** — `LICENSE`, `SAFETY.md`
- **B-07** — `native/lrt_zmap.c`, `native/tests/test_zmap.c`, `src/linumert_sim/native.py`, `tests/test_native_zmap.py`, `tools/bench_zmap.py`
- **B-08** — `docs/NATIVE.md`, `tools/bench_sim.py`
- **B-09** — `native/lrt_gcode.c`, `native/lrt_gcode.h`, `tests/test_native_gcode.py`, `tools/bench_gcode.py`
- **B-10** — `native/lrt_sim.c`, `native/lrt_sim.h`, `src/linumert_sim/native_sim.py`, `tests/test_native_sim.py`
