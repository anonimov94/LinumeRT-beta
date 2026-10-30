# Przekazanie na następną sesję

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Codex · 2026-10-30

## Stan

- GitHub sprawdzony na początku sesji: `main` @ `57bc2c1`, `audit/plan-p0-p1` @ `a08b547`.
- Właściciel zatwierdził A-01 i A-02, na osobnych gałęziach, bez przepisywania rdzenia.
- Lokalnie: `audit/a01-documentation` (dokumentacja i generator raportu) oraz oparta
  na niej `audit/a02-joint-map` (poprawka P0). Właściciel następnie polecił push obu
  gałęzi; dostępność i SHA zweryfikuj przez `git ls-remote origin`. Bez zgody na merge.
- Aktualny skrót postępu, ograniczeń i kolejnych zadań znajduje się w `AGENTS.md`.
- Dowody, zmiany zachowania i ograniczenia: [AUDYT_A01_A02.md](AUDYT_A01_A02.md).
- Pozostałe P1 i nowe funkcje nadal otwarte. NIEZWERYFIKOWANE NA SPRZĘCIE.

## Następny krok

1. Przeczytać obowiązkowy `CODEX_STOP_READ.md`, `AGENTS.md`, `SAFETY.md` i raport zmian.
2. Sprawdzić aktualne SHA, gałąź i stan roboczy. Zmiany A-01/A-02 są już lokalnie;
   nie zaczynać ich ponownie; porównać lokalne SHA z gałęziami GitHub.
3. Niezależna recenzja zmian oraz decyzja D0 o środowisku LinuxCNC 2.9 SIM.
   A-02 pozostaje zablokowane w części integracyjnej. Nie zamykać na podstawie atrap.
4. Push/PR wyłącznie na wyraźne polecenie. Dalsze P1 wymagają zatwierdzenia zakresu.

## Pułapki

- Domyślny limit pytest 60 s przerwał pełny przebieg na fuzzingu `test_native_sim.py`.
  Powtórzenie ma limit 300 s ustawiony tylko zmienną `PYTEST_ADDOPTS`; testów nie zmieniono.
- Backend odrzuca kinematyki inne niż trivkins i niesynchronizowane bazowanie gantry.
- STOP JOG w LinuxCNC wysyła teraz ABORT dla całego ruchu, także przy wskazaniu jednej osi.
- Zmiana mapowania INI podczas działania wymaga ponownego rozruchu aplikacji.
- Wtyczki nadal mają dostęp do usług; A-01 poprawia opis, nie izoluje kodu.
- Reguły K-3xx nadal występują w Pythonie i C; nie zmieniano ich w tym przyroście.
