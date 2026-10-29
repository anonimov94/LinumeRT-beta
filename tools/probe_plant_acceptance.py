"""Strict evaluation of Plant/LinuxCNC probe-contact measurements.

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: ChatGPT

Input CSV columns:
  axis,feed_mm_min,plant_surface_mm,linuxcnc_contact_mm
Optional: run_id, substeps, reply_age_cycles, ferror_mm

Contact coordinates must use the same frame. In particular, LinuxCNC #5061/2/3
are not interchangeable with joint positions and must be converted to the Plant
surface reference frame before evaluation. No offset or fit is applied.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

LIMIT_MM = 0.001
REQUIRED = ("axis", "feed_mm_min", "plant_surface_mm", "linuxcnc_contact_mm")


def evaluate(rows: list[dict[str, str]], limit: float = LIMIT_MM) -> dict:
    """Fail closed: malformed, missing or non-finite measurements are rejected."""
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("limit must be finite and positive")
    if not rows:
        raise ValueError("no probe samples")
    errors: list[dict] = []
    groups: dict[tuple[str, float], list[float]] = defaultdict(list)
    for index, row in enumerate(rows, 1):
        missing = [key for key in REQUIRED if key not in row or not str(row[key]).strip()]
        if missing:
            raise ValueError(f"row {index}: missing {', '.join(missing)}")
        axis = row["axis"].upper()
        if axis not in ("X", "Y", "Z"):
            raise ValueError(f"row {index}: invalid axis {axis!r}")
        try:
            feed = float(row["feed_mm_min"])
            surface = float(row["plant_surface_mm"])
            contact = float(row["linuxcnc_contact_mm"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"row {index}: invalid numeric field") from exc
        if not all(math.isfinite(x) for x in (feed, surface, contact)) or feed <= 0:
            raise ValueError(f"row {index}: non-finite field or non-positive feed")
        err = contact - surface
        groups[(axis, feed)].append(err)
        errors.append({"row": index, "axis": axis, "feed_mm_min": feed,
                       "error_mm": err, "pass": abs(err) < limit})
    summaries = []
    for (axis, feed), values in sorted(groups.items()):
        summaries.append({
            "axis": axis, "feed_mm_min": feed, "count": len(values),
            "mean_error_mm": sum(values) / len(values),
            "max_abs_error_mm": max(map(abs, values)),
            "range_mm": max(values) - min(values),
            "pass": all(abs(v) < limit for v in values),
        })
    return {"pass": all(r["pass"] for r in errors),
            "limit_exclusive_mm": limit, "samples": len(errors),
            "groups": summaries, "measurements": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LinuxCNC/Plant probe acceptance; strict < limit")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--limit-mm", type=float, default=LIMIT_MM)
    parser.add_argument("--output", type=Path, help="JSON output")
    args = parser.parse_args(argv)
    try:
        with args.csv_path.open(newline="", encoding="utf-8") as handle:
            result = evaluate(list(csv.DictReader(handle)), args.limit_mm)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"invalid probe evidence: {exc}\n")
    report = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
