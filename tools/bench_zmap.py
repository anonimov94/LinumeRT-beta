#!/usr/bin/env python3
"""Benchmark usuwania materiału (StockMap.cut): zygzak frezem po przygotówce.

SPDX-License-Identifier: GPL-2.0-or-later

    LRT_NATIVE=0 python3 tools/bench_zmap.py   # numpy
    LRT_NATIVE=1 python3 tools/bench_zmap.py   # rdzeń C
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linumert_sim.cutter import Cutter  # noqa: E402
from linumert_sim.zmap import StockMap  # noqa: E402


def run(passes: int = 60, kind: str = "ball") -> tuple[float, float, float]:
    cutter = Cutter(1, kind, 3.0, 20.0, 3.0, 25.0, 60.0, 16.0)
    stock = StockMap("BOX", 0, 0, 120, 80, -10, 0, cell=0.5)
    removed, segments = 0.0, 0
    start = time.perf_counter()
    for i in range(passes):
        y = 4 + i * 1.2
        a, b = (2, 118) if i % 2 == 0 else (118, 2)
        for j in range(40):                      # krótkie segmenty jak z interpolacji łuków
            x0 = a + (b - a) * j / 40
            x1 = a + (b - a) * (j + 1) / 40
            removed += stock.cut(cutter, (x0, y, -4.0), (x1, y, -4.0)).removed
            segments += 1
    return time.perf_counter() - start, removed, segments


if __name__ == "__main__":
    seconds, removed, segments = run()
    print(f"{segments} segmentów, {seconds:.3f} s, usunięto {removed:.2f} mm³, "
          f"{segments / seconds:.0f} seg/s")
