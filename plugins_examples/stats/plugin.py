"""Wtyczka przykładowa ``stats``: statystyki programu G-code.

SPDX-License-Identifier: GPL-2.0-or-later

Wzorzec dla nowych wtyczek: manifest ``plugin.yaml`` + ``register(api)``. Wtyczka dokłada
operację ``stats.gcode`` do kontraktu i korzysta z usługi ``program`` rdzenia.
"""

from __future__ import annotations

import re

from pydantic import Field

from linumert_headless.schema import Model, ProgramName

_WORD = re.compile(r"\b([GM])\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


class GcodeStats(Model):
    name: str
    lines: int
    blocks: int
    rapid: int = Field(description="liczba G0")
    linear: int = Field(description="liczba G1")
    arcs: int = Field(description="liczba G2/G3")
    tool_changes: int = Field(description="liczba M6")
    comments: int


def analyse(name: str, text: str) -> GcodeStats:
    lines = text.splitlines()
    counts = {"G0": 0, "G1": 0, "G2": 0, "G3": 0, "M6": 0}
    blocks = comments = 0
    for raw in lines:
        code = re.sub(r"\([^)]*\)", "", raw.split(";", 1)[0]).strip()
        if raw.strip().startswith((";", "(")):
            comments += 1
        if not code:
            continue
        blocks += 1
        for letter, number in _WORD.findall(code):
            key = f"{letter.upper()}{int(float(number))}"
            if key in counts:
                counts[key] += 1
    return GcodeStats(name=name, lines=len(lines), blocks=blocks, rapid=counts["G0"],
                      linear=counts["G1"], arcs=counts["G2"] + counts["G3"],
                      tool_changes=counts["M6"], comments=comments)


def register(api) -> None:
    def handler(request: ProgramName, ctx) -> GcodeStats:
        program = ctx.services["program"].read(request)
        return analyse(program.name, program.text)

    api.query("stats.gcode", summary="Statystyki programu G-code", request=ProgramName,
              result=GcodeStats, handler=handler)
