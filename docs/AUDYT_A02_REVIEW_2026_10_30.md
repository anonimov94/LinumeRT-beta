# Kontynuacja przeglądu A-01/A-02 — 2026-10-30

SPDX-License-Identifier: GPL-2.0-or-later

Punkt odniesienia: `audit/a02-joint-map` @
`de843d566515a5c1eea4e215a3cbfbf129b457cc`, z lokalnymi testami opisanymi poniżej.
Drzewo przed przeglądem było czyste. `git ls-remote origin` potwierdził tę samą
wersję gałęzi A-02, A-01 @ `105e36f` oraz main @ `57bc2c1`.

## Zakres i dowody

Przeczytano dokument STOP, AGENTS, SAFETY, raport i plan audytu oraz implementację
AxisMap, czytnika, backendu, generatora stanu i ich testy. Jest to przegląd
uzupełniający w kolejnej sesji Codex, nie zamknięcie niezależnego odbioru.

Dodano 10 przypadków do `tests/test_linuxcnc_axis_map.py`:

- HOME, JOG ciągły i przyrostowy nie wysyłają polecenia ruchu, jeśli drugie
  potwierdzenie (zmiana teleop) zwróci timeout lub RCS_ERROR — 6 przypadków.
- STOP wszystkich osi, STOP Y i JOG Y z prędkością zero wysyłają ABORT bez
  odczytu NML, którego poll zgłasza wyjątek — 3 przypadki.
- Zmiana ścieżki INI z identycznym mapowaniem odmawia HOME przed poleceniami.

Testy przechodzą na istniejącym kodzie: rozszerzają ochronę regresyjną,
nie są dowodem nowo wykrytej i naprawionej usterki. Nie zmieniono kodu sterowania.

## Wyniki tej sesji

- `make PYTHON=.venv/bin/python lint`: PASS (ruff i strażnik bez GUI).
- `.venv/bin/python -m pytest tests/test_linuxcnc_axis_map.py
  tests/test_cnc_reader.py tests/test_stan.py tests/test_startup_backend.py
  tests/test_machine_service.py -q`: PASS, 86 przypadków.
- `.venv/bin/python tools/roadmap.py check`: PASS.
- `git diff --check`: PASS przed zapisaniem tego raportu; kontrola powtórzona po zapisie.
- Pełnego zestawu testów nie uruchamiano w tej sesji. Historyczne wyniki pozostają
  w poprzednim raporcie i nie są wynikiem obecnego przebiegu.

## Otwarte ustalenia

Mapowanie osi/jointów jest jawne, agregacja home/limit i odmowy mają lokalne
regresje. Semantyka synchronizowanego HOME oraz rzeczywisty skutek ABORT nadal
wymagają LinuxCNC 2.9 SIM. STOP w backendzie obejmuje cały ruch; opis speed
w `schema.py:106` nadal mówi o zatrzymaniu tej osi — znana niespójność A-03.

JOG nadal przekazuje speed/distance bez konwersji. `contract.py:202` pomija
kontrolę roli przy braku enforced, a `plugins.py:116` udostępnia usługi.
Są to potwierdzone zachowania kodu; skutków na konkretnej maszynie nie badano.
Watchdog HAL pozostaje otwartym odbiorem, a programowy deadman go nie zastępuje.

Sprawdzenie `shutil.which` dla linuxcnc/halcmd i `importlib.util.find_spec`
dla linuxcnc zwróciło None. D0 (platforma SIM) pozostaje do rozstrzygnięcia.
Nie zamykano A-01/A-02 ani nie zmieniano statusów roadmapy. Przed implementacją
A-03 wymagane jest zatwierdzenie tego zakresu zgodnie z AGENTS i dokumentem STOP.
Decyzja o zachowaniu odziedziczonego rdzenia pozostaje aktualna.

**NIEZWERYFIKOWANE NA SPRZĘCIE.** Brak odbioru LinuxCNC SIM; wyniki atrap
nie potwierdzają gotowości do rzeczywistego sterowania CNC.
