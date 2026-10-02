#!/usr/bin/env python3
"""Type-check C files with the exact NDK clang lines the shared tree's last
Android build used (compile_commands.json), re-pointed at this worktree.

    typecheck.py <worktree> file[=sibling] ...

A new file has no entry of its own; `new.c=sibling.c` borrows sibling.c's
line. Every -I into the shared tree is re-pointed, the bare one too
(cullnf276: a rewrite of "/home/justin/hakuX/" alone misses
"-I/home/justin/hakuX" and silently checks the shared tree's headers).
Generated and third-party include dirs that exist only in the shared tree
are left pointing there.
"""
import glob
import json
import os
import shlex
import subprocess
import sys

SHARED = "/home/justin/hakuX"
wt = os.path.abspath(sys.argv[1])
ccs = glob.glob(SHARED + "/android/app/.cxx/Release/*/arm64-v8a/compile_commands.json")
if not ccs:
    sys.exit("no compile_commands.json")
cc = json.load(open(ccs[0]))
rc = 0
for spec in sys.argv[2:]:
    rel, _, sib = spec.partition("=")
    look = sib or rel
    ents = [e for e in cc if e["file"].endswith("/" + look)]
    if not ents:
        print("NO ENTRY", look)
        rc = 1
        continue
    e = ents[0]
    args = e.get("arguments") or shlex.split(e["command"])
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "-o":
            skip = True
            continue
        if a == "-c":
            continue
        if os.path.isabs(a) and a.endswith("/" + look):
            a = os.path.join(wt, rel)
        if a == "-I" + SHARED:
            a = "-I" + wt
        elif a.startswith("-I" + SHARED + "/"):
            b = a.replace(SHARED + "/", wt + "/", 1)
            a = b if os.path.isdir(b[2:]) and "/.cxx/" not in b and "/build" not in b else a
        out.append(a)
    out += ["-c", "-o", "/dev/null", "-Wall"]
    r = subprocess.run(out, cwd=e["directory"], capture_output=True, text=True)
    print(rel, "rc=%d" % r.returncode)
    sys.stdout.write(r.stderr[-8000:])
    rc |= r.returncode
sys.exit(rc)
