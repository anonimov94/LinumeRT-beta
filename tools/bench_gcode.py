#!/usr/bin/env python3
"""Benchmark interpretera podzbioru G-code (tekst -> lista ruchów).

SPDX-License-Identifier: GPL-2.0-or-later

    LRT_NATIVE=0 python3 tools/bench_gcode.py   # Python
    LRT_NATIVE=1 python3 tools/bench_gcode.py   # rdzeń C
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linumert_sim.path import parse_subset  # noqa: E402


def program(blocks: int = 40000) -> str:
    lines = ["G21 G90 G17 G54", "T1 M6", "M3 S12000", "G0 X0 Y0 Z5"]
    for i in range(blocks):
        a = i * 0.01
        lines.append(f"G1 X{50 + 30 * math.cos(a):.3f} Y{50 + 30 * math.sin(a):.3f} "
                     f"Z{-1 - 0.0001 * i:.4f} F800")
        if i % 2000 == 0:
            lines.append(f"G2 X{50 + 30 * math.cos(a):.3f} Y{50 + 30 * math.sin(a):.3f} I-5 J0")
    lines.append("M30")
    return "\n".join(lines)


if __name__ == "__main__":
    text = program()
    start = time.perf_counter()
    moves = parse_subset(text)
    seconds = time.perf_counter() - start
    lines = text.count("\n") + 1
    print(f"{lines} linii -> {len(moves)} ruchów, {seconds:.3f} s, {lines / seconds:.0f} linii/s")
