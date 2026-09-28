#!/usr/bin/env python3
"""Type-check this lane's C files with the exact NDK clang lines the shared
tree's last Android build used (compile_commands.json), re-pointed at this
worktree. Usage: typecheck.py <worktree> [file ...]"""
import glob, json, os, shlex, subprocess, sys

wt = os.path.abspath(sys.argv[1])
files = sys.argv[2:] or ["system/physmem.c", "accel/tcg/cputlb.c"]
ccs = glob.glob("/home/justin/hakuX/android/app/.cxx/Release/*/arm64-v8a/compile_commands.json")
if not ccs:
    sys.exit("no compile_commands.json")
cc = json.load(open(ccs[0]))
rc = 0
for rel in files:
    ents = [e for e in cc if e["file"].endswith("/" + rel)]
    if not ents:
        print("NO ENTRY", rel); rc = 1; continue
    e = ents[0]
    args = e.get("arguments") or shlex.split(e["command"])
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False; continue
        if a == "-o":
            skip = True; continue
        if a == "-c":
            continue
        if a.endswith(rel) and os.path.isabs(a):
            a = os.path.join(wt, rel)
        if a.startswith("-I/home/justin/hakuX/"):
            b = a.replace("/home/justin/hakuX/", wt + "/")
            # generated and third-party dirs exist only in the shared tree
            a = b if os.path.isdir(b[2:]) and "/.cxx/" not in b and "/build" not in b else a
        out.append(a)
    out += ["-c", "-o", "/dev/null", "-Wall"]
    r = subprocess.run(out, cwd=e["directory"], capture_output=True, text=True)
    print(rel, "rc=%d" % r.returncode)
    sys.stdout.write(r.stderr[-6000:])
    rc |= r.returncode
sys.exit(rc)
