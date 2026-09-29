#!/usr/bin/env python3
"""Compile this worktree's changed emulator files -fsyntax-only with the flags
a configured desktop build uses (its compile_commands.json), this worktree's
include roots first. A cheap local stand-in for CI's compile, not a build.

    syntax_check.py [--exe OUT --like TREE_FILE] [BUILD_DIR] FILE...

--exe links one self-contained FILE into OUT instead, with the flags of
TREE_FILE (keyinfo.c borrows vk/shaders.c's).
"""
import json
import os
import shlex
import subprocess
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
args = sys.argv[1:]
exe = like = None
if args[:1] == ["--exe"]:
    exe = os.path.abspath(args[1])
    like = os.path.relpath(os.path.abspath(args[3]), WT)
    args = args[4:]
build = "/home/justin/hakuX/build-desktop"
if args and os.path.isdir(args[0]):
    build = args.pop(0)
cmds = json.load(open(os.path.join(build, "compile_commands.json")))
src_root = None
rc = 0
for f in args:
    rel = os.path.relpath(os.path.abspath(f), WT)
    key = like or rel
    # A new file has no entry; borrow its directory neighbour's flags.
    cand = [c for c in cmds if c["file"].endswith("/" + key)] or \
           [c for c in cmds if os.path.dirname(c["file"]).endswith(os.path.dirname(key))]
    if not cand:
        print("%s: no compile command to borrow" % rel)
        rc = 1
        continue
    c = cand[0]
    argv = c.get("arguments") or shlex.split(c["command"])
    out = []
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("-o", "-MF", "-MQ", "-MT"):
            skip = True
            continue
        if a in ("-c", "-MD") or a == c["file"] or a.endswith(os.path.basename(c["file"])):
            continue
        out.append(a)
    cc = out[0]
    mode = ["-O0", "-o", exe] if exe else ["-fsyntax-only"]
    argv = [cc] + mode + ["-iquote", WT, "-I" + WT, "-I" + os.path.join(WT, "include")] + \
        out[1:] + [os.path.join(WT, rel)] + (["-lglib-2.0"] if exe else [])
    p = subprocess.run(argv, cwd=c["directory"], capture_output=True, text=True)
    msgs = [l for l in p.stderr.splitlines() if "error" in l or "warning" in l]
    print("%s: %s" % (rel, "ok" if p.returncode == 0 else "FAILED"))
    for m in msgs[:20]:
        print("   ", m)
    rc |= p.returncode
sys.exit(rc)
