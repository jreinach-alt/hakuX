#!/usr/bin/env python3
"""Titles whose 0.5 row lacks the profile-save step: status_html._registry()'s
view (inputs = a route exists, save = a stored or held save), plus each one's
golden and whether that golden carries a save directory."""
import os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "docs", "testing", "jobs"))
sys.path.insert(0, os.path.join(ROOT, "docs", "testing", "titles"))
os.environ.setdefault("TITLESTATE_DIR", "/home/justin/hakux-work/dispatch/titlestate")
import status_html  # noqa: E402
import titlestate  # noqa: E402


class F:
    D = "/home/justin/hakux-work/dispatch"


reg, src = status_html._registry(F)
rows = []
for tid, r in sorted(reg.items(), key=lambda kv: kv[1]["name"].lower()):
    g = titlestate.golden(tid)
    gs = g["save"] if g else ""
    dirs = len(titlestate.save_dirs(titlestate.disk_tid(tid), gs)) if gs else 0
    rows.append((r["name"][:34], tid, "inputs" if r["inputs"] else "-", ",".join(r["routes"].values())[:48],
                 "save" if r["save"] else ("n/a" if not r["needs_save"] else "NONE"), gs, dirs, r["save_na"][:40]))
w = "{:<35} {:<9} {:<6} {:<49} {:<5} {:<13} {:<4} {}"
print(w.format("title", "tid", "inp", "routes", "save", "golden", "dirs", "save_na"))
for row in rows:
    print(w.format(*row))
print()
print("inputs but no save:", sum(1 for x in rows if x[2] == "inputs" and x[4] == "NONE"))
print("inputs, golden without a save directory:", sum(1 for x in rows if x[2] == "inputs" and x[5] and not x[6]))
print("no inputs:", sum(1 for x in rows if x[2] == "-"))
