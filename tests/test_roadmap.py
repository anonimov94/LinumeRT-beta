"""Roadmapa: ROADMAP.md zgodny z plan.json, dowody istnieją.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BETA = Path(__file__).resolve().parent.parent


def test_roadmapa_jest_spojna() -> None:
    result = subprocess.run([sys.executable, str(BETA / "tools" / "roadmap.py"), "check"],
                            capture_output=True, text=True, cwd=BETA)
    assert result.returncode == 0, result.stdout + result.stderr
