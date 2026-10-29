# Przekazanie na następną sesję

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Claude · 2026-10-29 · koniec sesji

## Stan
- `main` @ `57bc2c1`: szkielet, kontrakt (92 operacje), wtyczki, socket, roadmapa, rdzeń C (materiał, G-code,
  pętla symulacji), LICENSE (GPL-2.0), SAFETY.md, bramka audytu `CODEX_STOP_READ.md`.
- Gałąź `audit/plan-p0-p1`: **plan działania po audycie** (`docs/PLAN_AUDYTU_P0_P1.md`) i pozycje A-00…A-08 w roadmapie.
  **Nic z planu nie jest wdrożone.** Niezescalone — czeka na przegląd właściciela.
- **Nowe funkcje wstrzymane** (wtyczki 063/064, kolejne optymalizacje, GUI) do decyzji właściciela.
- Werdykt audytu: **NIEGOTOWE DO RZECZYWISTEGO STEROWANIA CNC**. Nic nie zweryfikowano na LinuxCNC ani sprzęcie.

## Od czego zacząć
1. Przeczytać `CODEX_STOP_READ.md`, `docs/PLAN_AUDYTU_P0_P1.md`, `AGENTS.md`, `SAFETY.md`.
2. Sprawdzić, czy `main` się nie zmienił od `57bc2c1` (`git log origin/main`).
3. Uzyskać decyzje właściciela **D0–D6** (tabela w §5 planu). Najważniejsza: **D0 — skąd LinuxCNC 2.9 SIM**.
4. Dopiero po decyzji: etap A-01 (poprawa dokumentacji), potem A-02 (P0 joint↔oś) na osobnych gałęziach
   `audit/pN-…`, test negatywny najpierw, PR bez automatycznego merge.

## Znane pułapki
- Reguły K-3xx istnieją w dwóch miejscach: `src/linumert_sim/engine.py` i `native/lrt_sim.c` (parytet: `tests/test_native_sim.py`).
- Zdanie „wtyczka steruje tylko przez kontrakt” w `AGENTS.md` i docs jest **nieprawdziwe** (poprawka: A-01/A-05).
- Lokalnie nie ma LinuxCNC; raport `docs/LINUXCNC_LOCAL.json` dotyczy tylko prostej maszyny XYZ.
- Push i PR tylko na wyraźne polecenie właściciela.
