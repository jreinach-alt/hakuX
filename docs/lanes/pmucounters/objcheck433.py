#!/usr/bin/env python3
"""Compile the patched accel/tcg/cpu-exec.c to an object with the Android
build's flags, then check that every symbol it needs and the tree's last
object did not is defined in a shipped libxemu.so (a link check without a
full build)."""
import glob
import json
import os
import shlex
import subprocess
import sys
import zipfile

TREE = "/home/justin/hakux-work/wt/pmucounters"
SRC = "/home/justin/hakuX"
NDK = "/home/justin/Android/Sdk/ndk/29.0.14206865"
NM = NDK + "/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-nm"
APK = sys.argv[1]

db = sorted(glob.glob(SRC + "/android/app/.cxx/Release/*/arm64-v8a/"
                      "compile_commands.json"), key=os.path.getmtime)[-1]
entry = next(e for e in json.load(open(db))
             if e["file"].endswith("accel/tcg/cpu-exec.c"))
args = shlex.split(entry["command"]) if "command" in entry \
    else entry["arguments"]


def build(src, obj):
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ("-o", "-c"):
            skip = True
            continue
        if a.startswith("-o") or a == entry["file"]:
            continue
        if a.startswith(("-I" + SRC, SRC)) and "/.cxx/" not in a:
            a = a.replace(SRC + "/", TREE + "/")
        out.append(a)
    out = out[:1] + ["-iquote", TREE + "/accel/tcg"] + out[1:]
    out += ["-c", "-o", obj, src]
    r = subprocess.run(out, cwd=entry["directory"], capture_output=True,
                       text=True)
    if r.returncode:
        print(r.stderr[-3000:])
        sys.exit("compile failed: " + src)


def undef(obj):
    r = subprocess.run([NM, "-u", obj], capture_output=True, text=True)
    return {ln.split()[-1] for ln in r.stdout.splitlines() if ln.strip()}


os.makedirs(TREE + "/scratch/obj", exist_ok=True)
new = TREE + "/scratch/obj/cpu-exec-pmu.o"
build(TREE + "/accel/tcg/cpu-exec.c", new)
old_src = TREE + "/scratch/obj/cpu-exec-master.c"
subprocess.run("git -C %s show HEAD:accel/tcg/cpu-exec.c > %s"
               % (TREE, old_src), shell=True, check=True)
old = TREE + "/scratch/obj/cpu-exec-master.o"
build(old_src, old)
added = sorted(undef(new) - undef(old))
print("object:", new, os.path.getsize(new), "bytes")
print("undefined symbols the hook adds:", " ".join(added))

z = zipfile.ZipFile(APK)
so = next(m for m in z.namelist() if m.endswith("arm64-v8a/libxemu.so"))
path = TREE + "/scratch/obj/libxemu.so"
open(path, "wb").write(z.read(so))
r = subprocess.run([NM, "--defined-only", path], capture_output=True,
                   text=True)
defined = {ln.split()[-1] for ln in r.stdout.splitlines() if ln.strip()}
r = subprocess.run([NM, "-D", "--undefined-only", path], capture_output=True,
                   text=True)
imported = {ln.split()[-1].split("@")[0] for ln in r.stdout.splitlines()
            if ln.strip()}
bad = []
for s in added:
    where = ("libxemu.so" if s in defined else
             "imported by libxemu.so (libc/libdl)" if s in imported else None)
    print("  %-28s %s" % (s, where or "NOT FOUND"))
    if not where:
        bad.append(s)
print("link check:", "FAIL " + " ".join(bad) if bad else "PASS")
sys.exit(1 if bad else 0)
