"""Czas startu działającej instancji LinuxCNC i świeżość pliku INI.

SPDX-License-Identifier: GPL-2.0-or-later

``stat`` nie zawiera mapowania joint→oś, więc mapowanie czytamy z pliku INI. Plik edytowany
po starcie LinuxCNC może opisywać inną maszynę niż ta, która działa (potwierdzone na SIM:
INI zmienione z XYYZ na ZYYX — ``home("Z")`` zbazowało X). Dlatego INI nie może być nowsze
niż proces, który go załadował. NIEZWERYFIKOWANE NA SPRZĘCIE.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

# Rozdzielczość mtime systemu plików i zaokrąglenia btime: różnica poniżej tego nie jest zmianą.
TOLERANCE_S = 2.0
_PROCESSES = ("milltask", "linuxcncsvr")


def _real(path: str) -> str:
    return os.path.realpath(path)


def _boot_time(proc: Path) -> float | None:
    try:
        for line in (proc / "stat").read_text().splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _start_ticks(proc: Path, pid: str) -> int | None:
    try:
        text = (proc / pid / "stat").read_text()
        # nazwa procesu jest w nawiasach i może zawierać spacje; pole 22 liczymy po ostatnim ')'
        rest = text[text.rindex(")") + 2:].split()
        return int(rest[19])
    except (OSError, ValueError, IndexError):
        return None


def process_start_time(ini_path: str, *, proc_root: str | Path = "/proc",
                       clock_ticks: int | None = None) -> float | None:
    """Najwcześniejszy czas startu (epoch) procesu LinuxCNC z tym INI; ``None`` gdy nie znaleziono.

    Zakłada LinuxCNC na tym samym hoście co aplikacja (tak działa moduł ``linuxcnc``).
    """
    proc = Path(proc_root)
    boot = _boot_time(proc)
    ticks = clock_ticks or os.sysconf("SC_CLK_TCK")
    if boot is None or not ticks:
        return None
    wanted = _real(ini_path)
    starts = []
    try:
        pids = [p.name for p in proc.iterdir() if p.name.isdigit()]
    except OSError:
        return None
    for pid in pids:
        try:
            args = (proc / pid / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        names = [os.path.basename(a.decode(errors="replace")) for a in args[:1]]
        if not names or names[0] not in _PROCESSES or b"-ini" not in args:
            continue
        index = args.index(b"-ini")
        if index + 1 >= len(args) or _real(args[index + 1].decode(errors="replace")) != wanted:
            continue
        started = _start_ticks(proc, pid)
        if started is not None:
            starts.append(boot + started / ticks)
    return min(starts) if starts else None


def ini_changed_after_start(ini_path: str, start: float) -> bool:
    """Prawda, gdy plik INI zmieniono po starcie instancji (z tolerancją zaokrągleń)."""
    return os.stat(ini_path).st_mtime > start + TOLERANCE_S


StartLookup = Callable[[str], float | None]


def cached_start_lookup(ttl: float = 5.0, *, lookup: StartLookup = process_start_time,
                        clock: Callable[[], float] = time.monotonic) -> StartLookup:
    """Szukanie w /proc przy każdym odczycie stanu byłoby drogie; wynik ważny ``ttl`` sekund."""
    cache: dict[str, tuple[float, float | None]] = {}

    def find(ini_path: str) -> float | None:
        now = clock()
        hit = cache.get(ini_path)
        if hit is not None and now - hit[0] < ttl and hit[1] is not None:
            return hit[1]
        value = lookup(ini_path)
        cache[ini_path] = (now, value)
        return value

    return find
