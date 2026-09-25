#!/usr/bin/env python3
"""Syntax/type-check worktree files with the NDK clang line from a build tree's
compile_commands.json (no build, no tree dirtied).  lane.vklayer34.

usage: typecheck_tu.py <compile_commands.json> <worktree> <relpath>...
"""
import json
import os
import shlex
import subprocess
import sys

cc_path, wt = sys.argv[1], sys.argv[2]
cmds = json.load(open(cc_path))
rc = 0
for rel in sys.argv[3:]:
    hit = [c for c in cmds if c["file"].endswith("/" + rel)]
    if not hit:
        print(f"{rel}: not in {cc_path}")
        rc = 1
        continue
    c = hit[0]
    args = c.get("arguments") or shlex.split(c["command"])
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "-o":
            skip = True
            continue
        if a.endswith("/" + rel):
            a = os.path.join(wt, rel)
        out.append(a)
    out += ["-fsyntax-only", "-Wall"]
    p = subprocess.run(out, cwd=c["directory"], capture_output=True, text=True)
    msgs = [l for l in p.stderr.splitlines() if rel.split("/")[-1] in l]
    print(f"{rel}: exit {p.returncode}")
    print("\n".join(msgs[:20]))
    rc |= p.returncode
sys.exit(rc)
