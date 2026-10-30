#!/usr/bin/env python3
"""Generuje liczby z kontraktu i kolekcji pytest (bez deklaracji odbioru).

SPDX-License-Identifier: GPL-2.0-or-later
"""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    contract = json.loads((ROOT / "api/contract.json").read_text(encoding="utf-8"))
    collected = []

    class Collection:
        def pytest_collection_finish(self, session):
            collected.extend(item.nodeid for item in session.items)

    import pytest

    if pytest.main(["tests", "--collect-only", "-q"], plugins=[Collection()]) != 0:
        return 1
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    lines = ["# Stan kontraktu i kolekcji testów", "",
             "SPDX-License-Identifier: GPL-2.0-or-later", "",
             "> Generowane: `python tools/stan.py` (w środowisku z zależnościami projektu).", "",
             f"Punkt odniesienia HEAD: `{sha}`; raport obejmuje bieżące drzewo robocze.", "",
             f"Operacje: **{len(contract['operations'])}**. "
             f"Domeny: **{len(contract['domains'])}**.", "",
             "| Pole | Wartość | Liczba |", "|---|---|---|"]
    for field in ("status", "safety"):
        for value, count in sorted(Counter(op[field] for op in contract["operations"]).items()):
            lines.append(f"| {field} | {value} | {count} |")
    lines += ["", f"Testy zebrane przez pytest: **{len(collected)}**.", "",
              "Kolekcja nie oznacza wykonania ani PASS. Wyniki przebiegów są osobnymi dowodami.",
              "NIEZWERYFIKOWANE NA SPRZĘCIE. Testy fake/Plant nie stanowią odbioru LinuxCNC.", ""]
    (ROOT / "docs/STAN.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
