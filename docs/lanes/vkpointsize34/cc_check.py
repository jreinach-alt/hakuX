#!/usr/bin/env python3
"""Syntax-check lane files with the desktop build's compile commands.

Objects go to /dev/null; the shared build tree is only read."""
import json, os, shlex, subprocess, sys

BUILD = os.environ.get("BUILD", "/home/justin/hakuX/build-desktop")
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
cmds = json.load(open(os.path.join(BUILD, "compile_commands.json")))
rc = 0
for rel in sys.argv[1:]:
    hit = [c for c in cmds if c["file"].endswith(rel)]
    if not hit:
        print(rel, "NO COMMAND"); rc = 1; continue
    c = hit[0]
    argv = shlex.split(c["command"])
    out = []
    skip = False
    for a in argv:
        if skip:
            skip = False; continue
        if a in ("-o", "-MF", "-MQ"):
            skip = True; continue
        if a in ("-MD",):
            continue
        out.append(a)
    # swap the source for the worktree's copy; point includes at it first
    out = [os.path.join(WT, rel) if a.endswith(rel) else a for a in out]
    # the build's -iquote names its own source root; point it at the worktree
    src = os.path.dirname(BUILD.rstrip("/"))
    out = [WT + a[len(src):] if a == src or a.startswith(src + "/") else a
           for a in out]
    out += ["-fsyntax-only"]
    r = subprocess.run(out, cwd=c["directory"], capture_output=True, text=True)
    print(rel, "rc=%d" % r.returncode)
    if r.returncode:
        print(r.stderr[-3000:]); rc = 1
sys.exit(rc)
