#!/usr/bin/env python3
"""Type-check worktree files with the NDK clang line from a compile database.

Usage: tcheck.py <compile_commands.json> <file relative to repo root>...
The command for each file is taken from the shared tree's database, its paths
re-pointed at this worktree, and run with -fsyntax-only.
"""
import json
import os
import shlex
import subprocess
import sys

SHARED = "/home/justin/hakuX"
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

db = json.load(open(sys.argv[1]))
by_file = {os.path.normpath(e["file"]): e for e in db}
rc = 0
for rel in sys.argv[2:]:
    e = by_file.get(os.path.join(SHARED, rel))
    if e is None:
        # A new file: borrow a neighbour's flags.
        d = os.path.join(SHARED, os.path.dirname(rel))
        e = next((v for k, v in by_file.items() if os.path.dirname(k) == d),
                 None)
        if e is None:
            print("no command for", rel)
            rc = 1
            continue
        src = e["file"]
    else:
        src = e["file"]
    args = e.get("arguments") or shlex.split(e["command"])
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "-o":
            skip = True
            continue
        if a in ("-c",) or a == src or a.endswith(os.path.basename(src)) and os.path.isabs(a):
            continue
        # Source paths move to the worktree; build products (glib, the
        # generated headers under .cxx) exist only in the shared tree.
        i = a.find(SHARED)
        if i >= 0 and os.path.exists(a[i:].replace(SHARED, WT, 1)):
            a = a.replace(SHARED, WT, 1)
        out.append(a)
    out += ["-fsyntax-only", "-Wall", os.path.join(WT, rel)]
    r = subprocess.run(out, cwd=e["directory"], capture_output=True, text=True)
    print("==", rel, "rc", r.returncode)
    sys.stdout.write(r.stderr[-6000:])
    rc |= r.returncode
sys.exit(rc)
