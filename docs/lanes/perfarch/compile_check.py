#!/usr/bin/env python3
"""Compile this worktree's tcg/tcg.c and tcg/tcg-op.c for arm64 Android with
the exact flags of an existing Android build tree, to /tmp, touching nothing
else. Generated headers are read from that build tree, so a change to them
would not be seen -- none of this lane's files are generated."""
import json
import os
import shlex
import subprocess
import sys

BUILD = ("/home/justin/hakuX/android/app/.cxx/Release/3z4l2q3k/arm64-v8a")
OLD = "/home/justin/hakuX"
NEW = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
FILES = sys.argv[1:] or ["tcg/tcg.c", "tcg/tcg-op.c"]

cc = json.load(open(os.path.join(BUILD, "compile_commands.json")))
rc = 0
for rel in FILES:
    ent = next(e for e in cc if e["file"] == os.path.join(OLD, rel))
    args = shlex.split(ent.get("command") or " ".join(ent["arguments"]))
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            out.append("/tmp/perfarch_" + os.path.basename(rel) + ".o")
            continue
        if a == "-o":
            skip = True
            out.append(a)
            continue
        # Sources from this worktree; generated headers stay in BUILD.
        if a.startswith("-I" + OLD) and not a.startswith("-I" + OLD + "/android/app/.cxx"):
            a = "-I" + NEW + a[len("-I" + OLD):]
        elif a == os.path.join(OLD, rel):
            a = os.path.join(NEW, rel)
        out.append(a)
    out += ["-Wall", "-Wno-unused-function", "-Wno-missing-braces"]
    r = subprocess.run(out, cwd=ent["directory"], capture_output=True,
                       text=True)
    lines = [l for l in r.stderr.splitlines()
             if "perfarch" in l or "hostbench" in l or "error" in l
             or "hakux" in l.lower()]
    print("%s: %s" % (rel, "ok" if r.returncode == 0 else "FAILED"))
    print("\n".join(lines[:60]))
    rc |= r.returncode
sys.exit(rc)
