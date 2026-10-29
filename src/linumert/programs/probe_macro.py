"""Dwuetapowe sondowanie osi LinuxCNC 2.9 — dwa G38.2, wynik z drugiego styku.

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Claude (wersja bazowa), ChatGPT (dwa najazdy)

Odjazd między najazdami 1–2 mm, drugie podejście wolniejsze. G10 L20
dopiero po udanym drugim G38.2. M73 przywraca modalność po normalnym
powrocie (nie po ABORT). Wartości długości w mm, posuw w mm/min.
NIEZWERYFIKOWANE NA SPRZĘCIE.
"""

from __future__ import annotations

PROBE_AXES = ("X", "Y", "Z")
FINE_OVERRUN_MM = 0.5  # dodatkowa droga po poprzednim styku, gdy drugi nie zadziala
WORK_OFFSETS = ("G54", "G55", "G56", "G57", "G58", "G59", "G59.1", "G59.2", "G59.3")

_AXIS_BLOCK = """\
  G91
  G38.2 {a}#<dist> F#4
  G1 {a}#<backoff_move> F#4
  G38.2 {a}#<fine_dist> F#<fine_feed>
  G90
  G10 L20 P#5 {a}[#<_{l}> - #{param} + #6]
  G91
  G0 {a}#<final_back>"""


def _branch(index: int) -> str:
    axis = PROBE_AXES[index]
    return _AXIS_BLOCK.format(a=axis, l=axis.lower(), param=5061 + index)


PROBE_MACRO = f"""\
; SPDX-License-Identifier: GPL-2.0-or-later
; Model-Author: Claude, ChatGPT
; o<lrt_probe> call [os 0=X 1=Y 2=Z] [kierunek +/-1] [droga mm]
;   [posuw pierwszy mm/min] [P 1..9] [wartosc] [odjazd koncowy mm]
;   [posuw dokladny mm/min] [cofniecie miedzy najazdami 1..2 mm]
; Brak arg 8/9: drugi posuw = pierwszy, cofniecie = 1.5 mm.
; Brak styku G38.2 zatrzymuje makro przed G10 L20.
o<lrt_probe> sub
  M73
  #<fine_feed> = #8
  o80 if [#<fine_feed> LE 0]
    #<fine_feed> = #4
  o80 endif
  #<backoff> = #9
  o81 if [#<backoff> LE 0]
    #<backoff> = 1.5
  o81 endif
  #<dist> = [#2 * #3]
  #<backoff_move> = [0 - #2 * #<backoff>]
  #<fine_dist> = [#2 * [#<backoff> + ${FINE_OVERRUN_MM}]]
  #<final_back> = [0 - #2 * #7]
  G21 G94
  o10 if [#1 EQ 0]
${_branch(0)}
  o10 elseif [#1 EQ 1]
${_branch(1)}
  o10 elseif [#1 EQ 2]
${_branch(2)}
  o10 else
    (abort, lrt_probe: niepoprawna os)
  o10 endif
o<lrt_probe> endsub
M2
"""


def probe_call(axis: str, direction: int, distance: float, feed: float, offset: str,
               value: float, retract: float, *, approach_feed: float | None = None,
               backoff: float = 1.5) -> str:
    """Wygeneruj MDI dwóch najazdów (posuw pomiarowy = `feed`).

    Warstwa usługi waliduje zakresy i potwierdzenie operatora.
    """
    index = PROBE_AXES.index(axis.upper())
    p = WORK_OFFSETS.index(offset) + 1
    coarse = feed if approach_feed is None else approach_feed
    args = (index, direction, distance, coarse, p, value, retract, feed, backoff)
    return "o<lrt_probe> call " + " ".join(f"[{_num(v)}]" for v in args)


def _num(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


__all__ = ["PROBE_AXES", "PROBE_MACRO", "WORK_OFFSETS", "probe_call"]
