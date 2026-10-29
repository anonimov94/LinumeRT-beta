"""Benchmark pełnej symulacji offline (G-code -> materiał, kolizje, obciążenia).

SPDX-License-Identifier: GPL-2.0-or-later

    LRT_NATIVE=0 python3 tools/bench_sim.py   # Python/numpy
    LRT_NATIVE=1 python3 tools/bench_sim.py   # rdzeń C
    python3 tools/bench_sim.py /ścieżka       # dodatkowo profil cProfile w tym katalogu
"""

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from linumert_sim.offline import OfflineJob, simulate  # noqa: E402


def main() -> None:
    lines = [";@STOCK BOX X100 Y100 Z20", "G21 G90 G17", "T1 M6", "M3 S12000", "G0 X0 Y0 Z5"]
    for i in range(30000):
        a = i * 0.02
        lines.append(f"G1 X{50 + 30 * math.cos(a):.3f} Y{50 + 30 * math.sin(a):.3f} "
                     f"Z{-1 - 0.00005 * i:.4f} F1500")
    lines.append("M30")
    job = OfflineJob(program="\n".join(lines), tools=((1, 60.0, 6.0),))
    start = time.perf_counter()
    result = simulate(job)
    seconds = time.perf_counter() - start
    print(f"simulate: {result['segments']} segmentów, {seconds:.2f} s, "
          f"{result['segments'] / seconds:.0f} seg/s, usunięto {result['removed_mm3']} mm3, "
          f"zdarzeń {len(result['events'])}")
    if len(sys.argv) > 1:
        import cProfile
        import pstats

        out = Path(sys.argv[1]) / "bench_sim.prof"
        cProfile.runctx("simulate(job)", globals(), {"job": job, "simulate": simulate}, str(out))
        pstats.Stats(str(out)).sort_stats("tottime").print_stats(12)


if __name__ == "__main__":
    main()
