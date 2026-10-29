#!/usr/bin/env python3
"""Roadmapa beta: jedyne źródło statusów to roadmap/plan.json; ROADMAP.md jest generowany.

SPDX-License-Identifier: GPL-2.0-or-later

    python3 tools/roadmap.py list [--status partial] [--area M5]
    python3 tools/roadmap.py next              # najniższe nieukończone ID (nie-GUI)
    python3 tools/roadmap.py show 063
    python3 tools/roadmap.py done 063 --evidence src/x.py tests/test_x.py
    python3 tools/roadmap.py set 063 --status partial --remaining "EtherCAT: brak PDO"
    python3 tools/roadmap.py add B-06 --title "..." --area core
    python3 tools/roadmap.py render            # przepisz ROADMAP.md
    python3 tools/roadmap.py check             # ROADMAP.md zgodny z plan.json, dowody istnieją
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

BETA = Path(__file__).resolve().parent.parent
PLAN = BETA / "roadmap" / "plan.json"
VIEW = BETA / "ROADMAP.md"
STATUSES = ("planned", "partial", "done", "gui_later", "blocked")
OPEN = {"planned", "partial", "blocked"}
LABEL = {"planned": "planowane", "partial": "częściowe", "done": "ukończone",
         "gui_later": "GUI (na końcu)", "blocked": "zablokowane"}


def load() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def save(plan: dict) -> None:
    plan["updated"] = datetime.date.today().isoformat()
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VIEW.write_text(render(plan), encoding="utf-8")


def sort_key(item: dict) -> tuple:
    ident = item["id"]
    return (0, ident) if ident.startswith("B-") else (1, ident)


def render(plan: dict) -> str:
    items = sorted(plan["items"], key=sort_key)
    count = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    lines = ["# ROADMAP — linumeRT headless (beta)", "",
             "> Plik GENEROWANY z `roadmap/plan.json` przez `python3 tools/roadmap.py render`. "
             "Nie edytuj ręcznie.", "",
             f"Aktualizacja: {plan['updated']} · " +
             " · ".join(f"{LABEL[s]}: {n}" for s, n in count.items()), ""]
    for line in plan["policy"].values() if isinstance(plan["policy"], dict) else ():
        if isinstance(line, str):
            lines.append(f"- {line}")
    lines += ["", "| ID | Obszar | Status | Zakres |", "|---|---|---|---|"]
    for i in items:
        lines.append(f"| {i['id']} | {i['area']} | {LABEL[i['status']]} | {i['title']} |")
    lines += ["", "## Pozostały zakres", ""]
    for i in items:
        if i["status"] in OPEN and i.get("remaining"):
            lines.append(f"### {i['id']} {i['title']}")
            lines += [f"- {r}" for r in i["remaining"]] + [""]
    lines += ["## Dowody ukończenia", ""]
    for i in items:
        if i["status"] == "done" and i.get("evidence"):
            lines.append(f"- **{i['id']}** — " + ", ".join(f"`{e}`" for e in i["evidence"]))
    return "\n".join(lines) + "\n"


def find(plan: dict, ident: str) -> dict:
    for item in plan["items"]:
        if item["id"] == ident:
            return item
    sys.exit(f"nie ma pozycji {ident}")


def check(plan: dict) -> list[str]:
    problems = []
    if not VIEW.is_file() or VIEW.read_text(encoding="utf-8") != render(plan):
        problems.append("ROADMAP.md nie zgadza się z plan.json (uruchom: tools/roadmap.py render)")
    ids = [i["id"] for i in plan["items"]]
    problems += [f"zduplikowane ID: {i}" for i in {x for x in ids if ids.count(x) > 1}]
    for i in plan["items"]:
        if i["status"] not in STATUSES:
            problems.append(f"{i['id']}: zły status {i['status']}")
        if i["status"] == "done":
            if not i.get("evidence"):
                problems.append(f"{i['id']}: done bez dowodów (--evidence)")
            problems += [f"{i['id']}: brak pliku dowodu {e}" for e in i.get("evidence", [])
                         if not (BETA / e).exists()]
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--status", choices=STATUSES)
    ls.add_argument("--area")
    sub.add_parser("next")
    show = sub.add_parser("show")
    show.add_argument("id")
    done = sub.add_parser("done")
    done.add_argument("id")
    done.add_argument("--evidence", nargs="+", required=True)
    st = sub.add_parser("set")
    st.add_argument("id")
    st.add_argument("--status", choices=STATUSES)
    st.add_argument("--remaining", action="append")
    st.add_argument("--evidence", nargs="*")
    add = sub.add_parser("add")
    add.add_argument("id")
    add.add_argument("--title", required=True)
    add.add_argument("--area", required=True)
    sub.add_parser("render")
    sub.add_parser("check")
    args = p.parse_args(argv)
    plan = load()

    if args.cmd == "list":
        for i in sorted(plan["items"], key=sort_key):
            if (args.status and i["status"] != args.status) or (
                    args.area and i["area"] != args.area):
                continue
            print(f"{i['id']:<5} {i['area']:<9} {LABEL[i['status']]:<14} {i['title']}")
    elif args.cmd == "next":
        for i in sorted(plan["items"], key=sort_key):
            if i["status"] in OPEN:
                print(f"{i['id']} [{LABEL[i['status']]}] {i['title']}")
                for r in i.get("remaining", []):
                    print(f"  - {r}")
                break
        else:
            print("wszystko ukończone")
    elif args.cmd == "show":
        print(json.dumps(find(plan, args.id), ensure_ascii=False, indent=2))
    elif args.cmd == "done":
        item = find(plan, args.id)
        missing = [e for e in args.evidence if not (BETA / e).exists()]
        if missing:
            sys.exit(f"brak plików dowodu: {missing}")
        item.update(status="done", remaining=[], evidence=args.evidence)
        save(plan)
        print(f"{args.id}: ukończone; ROADMAP.md przepisany")
    elif args.cmd == "set":
        item = find(plan, args.id)
        if args.status:
            item["status"] = args.status
        if args.remaining is not None:
            item["remaining"] = args.remaining
        if args.evidence is not None:
            item["evidence"] = args.evidence
        save(plan)
    elif args.cmd == "add":
        if any(i["id"] == args.id for i in plan["items"]):
            sys.exit(f"{args.id} już istnieje")
        plan["items"].append({"id": args.id, "area": args.area, "title": args.title,
                              "status": "planned", "remaining": [], "evidence": []})
        save(plan)
    elif args.cmd == "render":
        save(plan)
    elif args.cmd == "check":
        problems = check(plan)
        print("\n".join(problems) or "OK: roadmapa spójna")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
