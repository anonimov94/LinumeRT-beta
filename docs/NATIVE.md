# Rdzeń natywny (C) — pomiary, decyzje, jak dodać jądro

SPDX-License-Identifier: GPL-2.0-or-later

Zasada: **gorąca pętla numeryczna → C11** (`native/`, bez zależności, `-ffp-contract=off`),
Python zostaje cienkim wiązaniem i wersją zapasową/wzorcem (`LRT_NATIVE=0`). Każde jądro ma
test parytetu z wersją Python. Tryby: `LRT_NATIVE=auto` (domyślnie), `0` (Python), `1` (wymagaj C).
Budowanie: `make native` (kompilacja + testy C), pomiary: `make bench`.

## Co jest w C

| Jądro | Plik | Python/numpy | C | Test parytetu |
|---|---|---|---|---|
| usuwanie materiału 2.5D | `native/lrt_zmap.c` | 1380 seg/s | 41 768 seg/s (30×) | mapy bit w bit, `tests/test_native_zmap.py` |
| interpreter podzbioru G-code | `native/lrt_gcode.c` | 80 tys. linii/s | 1,94 mln linii/s (24×) | korpus + fuzzing, `tests/test_native_gcode.py` |
| **cała pętla symulacji offline** (`native/lrt_sim.c`: próbkowanie, materiał, reguły K-3xx, obciążenia; `tools/bench_sim.py`) | 4120–4254 seg/s | 215 389 seg/s (52×) | zdarzenia, czasy i mapa materiału identyczne; `tests/test_native_sim.py` (scenariusze wymuszające każdy kod K-3xx + fuzzing) |

## Świadomie zostaje w Pythonie (pomiar, nie zgadywanie)

| Moduł | Pomiar | Decyzja |
|---|---|---|
| kolizje brył (`machine.collisions`) | 3 µs/wywołanie | za tanie, bez sensu |
| leksyka (`programs/lexer.py`) | ~85 tys. linii/s | parser z wyrażeniami i katalogiem błędów, używany tylko w `program.check`; koszt przepisania ≫ zysk |
| `estimate_canon` | ~170 tys. wywołań/s | działa na wyjściu rs274 (wymaga LinuxCNC), nie do sprawdzenia lokalnie |
| tryb symulacji **na żywo** (`SimEngine.step` wołany przez `live.py` z próbek Plant) | próbki napływają z częstotliwością Plant (~20 Hz), nie z pętli CPU | zostaje w Pythonie; `SimEngine` jest też wzorcem dla rdzenia C |

## Jak dodać jądro (dla modeli o małym kontekście)

1. Zmierz (`cProfile`, osobny `tools/bench_*.py`) — przenoś tylko to, co dominuje.
2. `native/lrt_<nazwa>.c` + `.h`: czysty C11, bez globalnego stanu, błędy przez kod zwrotu i
   komunikat w strukturze wyniku (nie `exit`), walidacja argumentów na wejściu.
3. Dopisz plik do `SRC`/`HDR` w `native/Makefile`; ustaw sygnatury w `linumert_sim/native.py::load`.
4. W module Pythona: `lib = native.load()`; gdy `None` → stara ścieżka. **Nie usuwaj** wersji Python.
5. Test parytetu `tests/test_native_<nazwa>.py`: te same wejścia przez `LRT_NATIVE=0` i `1`
   (`monkeypatch.setenv` + `native.reset_for_tests()`), w tym błędy i przypadki brzegowe, plus fuzzing.
   Sprawdź, że test nie jest pusty (np. że faktycznie zachodzą kontakty/błędy/łuki).
6. `tools/roadmap.py done ID --evidence …`.

Uwaga: sin/cos w C i numpy mogą różnić się o 1 ulp, więc wyniki zapisane jako float32
porównuj z tolerancją; arytmetykę bez funkcji przestępnych (mapa wysokości) porównuj bit w bit.
Biblioteka jest szukana obok źródeł (`native/build/`); instalacja `pip` bez źródeł wraca do Pythona.

## Pętla symulacji (lrt_sim) — jak jest zbudowana

- `native/lrt_sim.c` trzyma stan silnika (klucze `_active`/`_warned`, okno mocy skrawania, poprzednia próbka)
  i po jednym wywołaniu `lrt_sim_run(i0, i1)` przetwarza partię segmentów; Python pracuje partiami po 200
  (anulowanie i postęp między partiami, jak dotychczasowy rytm raportu).
- Zdarzenia wracają jako surowe struktury (`code`, pozycja, liczby, krótkie teksty); komunikaty z katalogu
  alarmów składa Python (`native_sim._events` → `Event.to_dict`), więc teksty nie mają drugiej kopii.
- Zachowania odziedziczone po wzorcu i świadomie powtórzone: zdarzenia **pierwszej próbki są odrzucane**
  (jej stan zostaje), współrzędne pierwszej próbki liczone w float32 (NEP 50), sortowanie części wg nazw.
- Poza zakresem rdzenia (np. >64 części nietnących) `native_sim.Unsupported` → wzorcowa pętla w Pythonie.
- Długości segmentów liczy Python (`math.dist`) i przekazuje tablicą do C: `ceil(sekundy/dt)` jest nieciągły,
  więc różnica 1 ulp względem własnego pierwiastka w C mogłaby zmienić liczbę próbek. Koszt ok. 0,3 µs/segment.
