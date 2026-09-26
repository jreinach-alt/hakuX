#!/usr/bin/env python3
"""Type-check this worktree's copy of a few TUs with the NDK clang line.

No desktop build tree exists on this host, so this borrows the exact arm64
compile line for each file from a warm Android build's compile_commands.json,
re-points it at this worktree's source, and compiles to /dev/null. Headers are
taken from this worktree first (-I<worktree>/...) so a changed psh.h is seen.

    python3 docs/lanes/cloud-271/typecheck.py [compile_commands.json]
"""
import glob
import json
import os
import shlex
import subprocess
import sys

FILES = [
    "hw/xbox/nv2a/pgraph/glsl/psh.c",
    "hw/xbox/nv2a/pgraph/vk/texture.c",
    "hw/xbox/nv2a/pgraph/vk/shaders.c",
    "hw/xbox/nv2a/pgraph/gl/shaders.c",
]

here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if len(sys.argv) > 1:
    cc_path = sys.argv[1]
else:
    cands = sorted(glob.glob("/home/justin/hakux-work/dispatch/build-tree/android/"
                             "app/.cxx/Release/*/arm64-v8a/compile_commands.json"),
                   key=os.path.getmtime)
    cc_path = cands[-1]
entries = json.load(open(cc_path))
print("compile_commands:", cc_path)

rc = 0
for rel in FILES:
    hit = [e for e in entries if e["file"].endswith("/" + rel)]
    if not hit:
        print(f"{rel}: NOT IN compile_commands (not built for Android?)")
        continue
    e = hit[0]
    src_root = e["file"][: -len(rel)]
    args = e.get("arguments") or shlex.split(e["command"])
    out = []
    skip = False
    def repoint(path):
        # Only paths that exist in this worktree: the build tree also holds
        # generated and third-party dirs (glib's install) under src_root.
        mine = here + "/" + path[len(src_root):]
        return mine if os.path.exists(mine) else path

    for a in args:
        if skip:
            skip = False
            continue
        if a in ("-o", "-c"):
            skip = a == "-o"
            continue
        if a.startswith(src_root):
            a = repoint(a)
        elif a.startswith("-I" + src_root):
            a = "-I" + repoint(a[2:])
        elif a == "-I" + src_root.rstrip("/"):
            a = "-I" + here   # the root itself: "hw/xbox/..." includes
        out.append(a)
    out += ["-o", "/dev/null", "-fsyntax-only", "-Wall"]
    p = subprocess.run(out, cwd=e["directory"], capture_output=True, text=True)
    errs = [l for l in p.stderr.splitlines() if "error" in l or "warning" in l]
    print(f"{rel}: exit {p.returncode}, {len(errs)} diagnostic lines")
    for l in errs[:20]:
        print("   ", l)
    rc |= p.returncode
sys.exit(rc)
