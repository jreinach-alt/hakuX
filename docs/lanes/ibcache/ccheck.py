#!/usr/bin/env python3
"""Compile this worktree's copies of some files with the NDK command lines of
an existing Android build (its compile_commands.json), without a Gradle run.

    python3 docs/lanes/ibcache/ccheck.py [-S] <repo-relative file>...

Source include paths are pointed at this worktree; the build tree's generated
headers are kept. -S writes <name>.s next to the script's out/ dir instead of
checking syntax only, to read the code a change emits.
"""
import json, os, shlex, subprocess, sys

DB = os.environ.get("CCHECK_DB",
    "/home/justin/hakuX/android/app/.cxx/Release/135r5t6d/arm64-v8a/compile_commands.json")
SRC = "/home/justin/hakuX"
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

args = sys.argv[1:]
asm = "-S" in args
files = [a for a in args if a != "-S"]
db = {e["file"]: e for e in json.load(open(DB))}
rc = 0
for f in files:
    e = db.get(os.path.join(SRC, f))
    if not e:
        print("no entry for", f); rc = 1; continue
    argv = e.get("arguments") or shlex.split(e["command"])
    out = []
    skip = False
    for a in argv:
        if skip:
            skip = False; continue
        if a == "-o":
            skip = True; continue
        if a == "-c":
            continue
        if a.startswith("-I" + SRC) and not a.startswith("-I" + SRC + "/android/app/.cxx"):
            a = "-I" + WT + a[2 + len(SRC):]
        if a == os.path.join(SRC, f):
            a = os.path.join(WT, f)
        out.append(a)
    if asm:
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        out += ["-S", "-o", os.path.join(HERE, "out", os.path.basename(f) + ".s")]
    else:
        out += ["-fsyntax-only"]
    r = subprocess.run(out, cwd=e["directory"])
    print(f, "rc", r.returncode)
    rc |= r.returncode
sys.exit(rc)
