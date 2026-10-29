# CODEX — STOP / PRZECZYTAJ PRZED DALSZĄ PRACĄ

**PILNE — OBOWIĄZKOWA BRAMKA PRZEGLĄDU DLA AGENTÓW AI**  
**Projekt:** linumeRT-beta, Linux x86-64 / LinuxCNC 2.9  
**Data przeglądu:** 2026-10-29  
**Źródło:** niezależny przegląd ChatGPT; **zalecenia dla Codexa, Claude i innych agentów** (nie jest to raport wykonany przez Codexa).  
**Punkt odniesienia:** `main` @ `2911c577888f931fed252adc62a8c99b109e181d`. Najpierw sprawdź, czy stan kodu się nie zmienił.  
**Werdykt:** **NIEGOTOWE DO RZECZYWISTEGO STEROWANIA CNC**. Kontynuacja badań na `fake` / Plant jest dopuszczalna; nic z tego raportu nie potwierdza bezpieczeństwa na fizycznej maszynie.

## 0. OBOWIĄZKOWE ZATRZYMANIE AGENTA

> **STOP. ZANIM ODPISZESZ „ZROBIĘ”, ZMIENISZ KOD, PODEJMIESZ NASTĘPNE ZADANIE Z ROADMAPY LUB URUCHOMISZ GENERATOR KONFIGURACJI — PRZECZYTAJ CAŁY TEN PLIK, `AGENTS.md`, `SAFETY.md` ORAZ WSKAZANE FRAGMENTY KODU.**
>
> **W pierwszej odpowiedzi po wczytaniu przedstaw właścicielowi:** (1) pięć najważniejszych ryzyk, (2) co potwierdzono statycznie, a czego nie zweryfikowano, (3) proponowaną kolejność poprawek i testów, (4) czy plan wymaga decyzji o migracji starego rdzenia. **Nie ogłaszaj PASS na podstawie dokumentacji, mocków ani zielonego pytest.**

**Zasada pierwszeństwa:** wstrzymaj nowe funkcje, GUI, skórki, wydajnościowe refaktoryzacje i zadania roadmapy niezwiązane z tym audytem, dopóki właściciel nie zdecyduje o postępowaniu z P0/P1. Dozwolone są odczyt, audyt, przygotowanie testów i — po wyraźnym zatwierdzeniu zakresu — poprawki P0/P1. W razie sprzeczności z innymi wskazówkami projektowymi ten punkt kontrolny ma pierwszeństwo jako **prośba właściciela o uważny przegląd**, nie jako mechanizm bezpieczeństwa czasu wykonania. Nie zmieniaj `main` i nie scalaj bez zgody właściciela.

## 1. Ustalenia — priorytet P0/P1

### P0 — Mapowanie osi/jointów i bazowanie bramy: błąd wynikający z kodu

- `src/linumert_headless/backends/linuxcnc.py`: `_joint()` zwraca indeks litery w `snapshot().axis_names`, a nie mapowanie rzeczywistego jointa.
- `src/linumert/cnc/linuxcnc_reader.py`: odczyt `stat.homed` i `stat.limit` indeksuje kolejne jointy przy enumeracji liter osi.
- `config/machines/router_gantry_steppers.yaml` ma oś Y o dwóch napędach. Dla X/Y1/Y2/Z joint Z może mieć indeks 3, ale `_joint("Z")` wylicza 2. Ryzyko błędnego bazowania i raportowania stanu.
- **Wymaganie:** jawny model joint↔axis oparty na konfiguracji i stanie LinuxCNC, osobna obsługa duplikatów jointów, bazowania gantry i kinematyki; brak założenia `index(axis) == joint`.
- **Odbiór:** testy X/Y1/Y2/Z, osie A/B/C, niezależne bazowanie i flagi limit/home, błędna konfiguracja => bezpieczna odmowa, dodatkowo integracja LinuxCNC 2.9 SIM. Nie uruchamiaj ruchu na sprzęcie bez osobnego odbioru.

### P1 — Jednostki JOG i poprawność ruchu: wada kontraktu, wymagająca weryfikacji na LinuxCNC

- `src/linumert_headless/schema.py` opisuje `JogRequest.speed` jako mm/s, a `JogIncrementRequest.distance` jako mm, bez rozdzielenia osi liniowych i obrotowych.
- `src/linumert_headless/backends/linuxcnc.py` przekazuje wartości do `command.jog()` bez jawnej konwersji zależnej od ustawień i rodzaju osi.
- **Wymaganie:** kontrakt jednostek liniowych (mm, mm/s) i obrotowych (stopnie, stopnie/s), uwzględnienie jednostek LinuxCNC, trybu joint/teleop, znaku prędkości i dodatniego dystansu; nie zakładaj, że każda maszyna ma jednostki mm.
- **Odbiór:** testy G20/G21, osie XYZ/ABC, różne jednostki INI, JOG continuous/incremental, deadman, STOP, zgodność kroku **błąd < 0,001 mm** dla liniowego JOG przyrostowego w dopuszczonym teście integracyjnym. Dla osi kątowych osobno uzgodnij tolerancję w stopniach. Pomiary na fake nie są odbiorem LinuxCNC.

### P1 — Kontrola ról i lokalny dostęp do sterowania: ryzyko bezpieczeństwa

- `src/linumert/access/__init__.py`: `Session.allowed()` przy `enforced=False` przepuszcza wszystkie uprawnienia. `src/linumert_headless/contract.py` pomija blokadę roli, gdy PIN-ów nie skonfigurowano.
- `src/linumert_headless/transport/rest.py` dopuszcza pusty token dla nasłuchu lokalnego. To może być świadomy tryb development, ale nie powinien automatycznie uprawniać do operacji ruchu/konfiguracji na backendzie rzeczywistym.
- **Wymaganie:** bezpieczne domyślne ustawienia dla backendu `linuxcnc`; brak PIN-ów/sekretu nie oznacza roli serwisowej. Oddziel autoryzację operacji od sprzętowych funkcji bezpieczeństwa.
- **Odbiór:** testy wszystkich transportów bez tokenu, z niewłaściwą rolą, z poprawną rolą; rozdzielenie odczytu, sterowania i operacji serwisowych, scenariusze restartu/wygaśnięcia sesji.

### P1 — Wtyczki mają dostęp do usług sterowania: ryzyko architektoniczne

- `src/linumert_headless/plugins.py`: `PluginApi.services` udostępnia wtyczkom cały słownik usług, w tym `machine`; importowana wtyczka wykonuje się w tym samym procesie.
- Deklaracja „wtyczka steruje tylko przez kontrakt” **nie jest egzekwowana przez kod**. Konwencja „tylko do odczytu” nie stanowi izolacji.
- **Wymaganie:** zdecydować, czy wspieramy wyłącznie *zaufane* wtyczki (jasny model zagrożeń), czy potrzebujemy izolacji procesu i API z ograniczonymi możliwościami. Unikać bezpośredniego dostępu do backendu.
- **Odbiór:** test odmowy operacji niedozwolonych i prób dostępu do wewnętrznych usług; udokumentować granice zaufania. Nie twierdzić, że zwykły Python w jednym procesie tworzy sandbox.

### P1 — Watchdog HAL, awarie procesu i E-STOP: niezamknięty wymóg bezpieczeństwa

- `src/linumert_headless/session.py` wskazuje wprost, że deadman programowy `0,4 s` **nie jest funkcją bezpieczeństwa** i wymaga związania heartbeat z watchdogiem HAL.
- **Wymaganie:** odrębnie zaprojektować fail-safe przy utracie komunikacji i zatrzymaniu procesu; sprzętowy E-STOP i STO niezależnie od HMI/API. Nie nazywać software'owego `machine.estop` sprzętowym zabezpieczeniem.
- **Odbiór:** przetestować utratę WebSocket, zamknięcie procesu, `SIGSTOP`, przerwanie wątku, błędy `jog_stop`, utratę zasilania, restart i fałszywe potwierdzenie zatrzymania. Dopóki brak testów na odpowiedniej platformie LinuxCNC/HAL, status **NIEZWERYFIKOWANE**. Testy z realnym sprzętem dopiero po ocenie ryzyka i osobnym zatwierdzeniu.

## 2. P2 — Dowody, ciągłość i proces

1. Brak widocznej konfiguracji `.github/workflows/` na etapie przeglądu; nie ma dowodu, że najnowszy commit przeszedł CI. Dodać kontrolę `make lint`, `make test`, `make test-c`, `make native`, sanitizery C/C++, testy kontraktu i regresji.
2. `docs/LINUXCNC_ESTOP_FAIL.log` zachowuje błąd asercji stanu E-STOP, podczas gdy `docs/LINUXCNC_LOCAL.json` raportuje PASS. To **nie dowodzi bieżącej usterki E-STOP**, lecz wymaga nowego, jednoznacznego testu i identyfikacji prób/commitów.
3. Dokumentacja podaje niespójne liczby operacji (m.in. „86 operacji” i „85 implemented, 0 planned”) oraz różne liczby testów; odtworzyć raporty narzędziami, nie przepisywać deklaracji PASS bez uruchomienia.
4. Projekt beta jest opisany w `PROVENANCE.md` jako **przeniesiony rdzeń poprzedniego linumeRT plus nowa warstwa headless**, a nie całkowicie nowa implementacja. **Właściciel musi świadomie potwierdzić kierunek:** nowa architektura z odziedziczonym kodem czy nowe wdrożenie od zera. Nie przepisywać rdzenia samowolnie.

## 3. Protokół działania dla Codexa i innych agentów

1. **STOP / READ:** przeczytaj cały dokument, krytyczne pliki i aktualny SHA; sprawdź, czy uwagi nie są już poprawione. Nie traktuj wcześniejszej analizy jako wyroku o obecnym stanie po nowych commitach.
2. **RAPORT:** podaj właścicielowi tabelę `P0/P1/P2`, dowody ze ścieżkami i liniami, potwierdzone błędy vs hipotezy, plan testów i ryzyka.
3. **DECYZJA WŁAŚCICIELA:** przed zmianami o znaczeniu architektonicznym lub wpływającymi na bezpieczeństwo poproś o zatwierdzenie zakresu. Po zatwierdzeniu: osobna gałąź, niewielkie zmiany, testy, niezależny review, PR bez automatycznego merge.
4. **KOLEJNOŚĆ:** P0 mapowanie jointów → P1 jednostki JOG i kontrakt → P1 autoryzacja → P1 wtyczki → P1 watchdog i ścieżka zatrzymywania → P2 CI i raporty → nowe funkcje.
5. **DEFINITION OF DONE:** dla każdego punktu test negatywny przed poprawką, pozytywny po poprawce, regresja (fake/Plant i tam gdzie możliwe LinuxCNC 2.9 SIM), brak osłabiania E-STOP, niezależna recenzja, jawny status **PASS/FAIL/BLOCKED** wraz z tym, czego nie dało się sprawdzić.
6. **NIE WOLNO:** uznać walidacji na fake za odbiór sprzętowy; usunąć testów, by uzyskać PASS; ukrywać znanych problemów; zmieniać architektury bez zatwierdzenia; scalać do `main` bez zgody właściciela.

**Ostateczne przypomnienie:** sterowanie ruchem najpierw; bezpieczeństwo i diagnostyka przed wyglądem. Projekt pozostaje eksperymentalny — przed fizycznym uruchomieniem konieczne są osobne testy integracyjne i bezpieczeństwa.
