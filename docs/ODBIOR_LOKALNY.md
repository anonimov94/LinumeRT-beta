# Lokalny odbiór beta — 2026-10-29

Model-Author: Codex. Zakres: samodzielny backend `beta/` wskazany przez właściciela.
Praca i testy wyłącznie na laptopie, bez Git, commitów, pushu i CI.
Katalog roboczy: `/home/dell/linumeRT-arena-finish/beta`.

## Potwierdzone braki i poprawki w toku

- WebSocket omijał kontrolę Host/Origin wykonywaną tylko w middleware HTTP.
  Kontrola jest teraz wykonywana przed przyjęciem połączenia; obcy Origin wymaga
  jawnego dopuszczenia. Poprawiono też rozpoznanie Host IPv6 z portem.
- Zmiany stanu trafiały z wątku roboczego bezpośrednio do kolejki asyncio.
  Przekazanie odbywa się teraz przez `call_soon_threadsafe`; zamykanie połączenia
  oczekuje na anulowanie zadania wysyłającego.
- Nieprawidłowe `params`, `hello` lub `id` mogły zrywać WebSocket.
  Zwracany jest błąd `invalid_request`, połączenie pozostaje użyteczne.
- Klient mógł podać cudzy identyfikator sesji jogu i uniemożliwić zatrzymanie przy
  swoim rozłączeniu. Własność ruchu WebSocket nadaje serwer.
- Zamykanie aplikacji nie zamykało backendu i pozostawiało wątek atrapy.
  Zamknięcie zatrzymuje jog i program, zwalnia backend i jest idempotentne.

## Weryfikacja

Trwa lokalna regresja Python i C. Wyniki zostaną dopisane po zakończeniu.
Środowisko `.venv`: Python 3.14; brak modułu LinuxCNC w systemowym Pythonie.
Testy transportów używają prawdziwego ASGI/HTTP/WebSocket i atrapy maszyny.
Nie są odbiorem LinuxCNC, RT, fizycznych wejść, napędów ani makr na maszynie.
NIEZWERYFIKOWANE NA SPRZĘCIE.

## Druga porcja: role, kontrakt i start

- Kontrola ról korzysta teraz z roli przypisanej operacji w kontrakcie. Stary słownik
  uprawnień ekranu nie obejmował nazw API, więc pozwalał operatorowi na operacje serwisu.
- Logowanie wystawia losowe, oddzielne tokeny sesji; wcześniej tokenem była nazwa roli.
  Blokada po pięciu błędnych PIN-ach zachowuje stan między żądaniami.
- Token API i token sesji są oddzielne: `X-LRT-Token` oraz `X-LRT-Session`.
  SDK zapamiętuje logowanie/wylogowanie; CLI ma `--session-token` i zmienną
  `LRT_SESSION_TOKEN`. WebSocket zapamiętuje rolę po `access.login`.
- Schematy kontraktu zachowują `$defs`; wcześniej odwołania `$ref` wskazywały
  nieistniejące definicje. Regresja sprawdza wszystkie odwołania wszystkich operacji.
- Błędy walidatorów Pydantic nie zawierają już obiektów wyjątków niezgodnych z JSON.
- Dodano punkt wejścia `linumert_headless` zgodny z wpisem DISPLAY oraz opcje
  `--ini`/`-ini`, `--root`, `--state-dir`. Samo `--ini` nie uruchamia LinuxCNC.
- Zamknięcie zapytania CLI nie zatrzymuje cudzej pracy: zatrzymanie dotyczy działającej
  pętli serwera lub posiadanego jogu; sam odczyt zwalnia wyłącznie połączenie backendu.

## Trzecia porcja: podtrzymanie i zgodność backendu

- Jog przyrostowy podlega teraz własności sesji i zatrzymaniu po rozłączeniu.
  Prędkość może być ujemna, dystans pozostaje dodatni. `machine.jog_keepalive`
  oraz ping WS podtrzymują ruch bez ponownego zadania przyrostu (86 operacji).
- Deadman działa przed odczytem stanu; awaria odczytu nie omija nadzoru.
- Jawne originy otrzymują obsługę CORS; limiter GET zwraca błąd API zamiast HTTP 500.
- SDK wybiera tematy także po stronie serwera; strumień WS ograniczony do 20 Hz.
- Adapter LinuxCNC używa `state(STATE_ESTOP/STATE_ESTOP_RESET)`, kontroluje wynik
  `wait_complete` i nie wykonuje MDI po odrzuconej zmianie trybu. Jog osi XZ
  używa indeksu kartezjańskiego Z=2 i włącza teleop. To test kontraktu API, nie live.
  Źródło: https://linuxcnc.org/docs/2.9/html/config/python-interface.html

Pierwotna lokalna seria `make lint test test-c` zakończyła się kodem 0.
Po poprawkach wymagane jest ponowne pełne uruchomienie; wynik końcowy poniżej.
