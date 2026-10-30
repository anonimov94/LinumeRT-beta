"""Spójność generowanego stanu z kontraktem. SPDX-License-Identifier: GPL-2.0-or-later"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_report_matches_contract():
    contract = json.loads((ROOT / "api/contract.json").read_text())
    report = (ROOT / "docs/STAN.md").read_text()
    assert f"Operacje: **{len(contract['operations'])}**" in report
    assert f"Domeny: **{len(contract['domains'])}**" in report
    for field in ("status", "safety"):
        values = {op[field] for op in contract["operations"]}
        for value in values:
            count = sum(op[field] == value for op in contract["operations"])
            assert f"| {field} | {value} | {count} |" in report
