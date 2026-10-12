#!/usr/bin/env python3
"""Syntax-check source files of this worktree with the NDK clang line (lane.fpsbelow1012).

Usage: ndkcheck.py <repo-relative path>...   Each file is compiled -fsyntax-only twice, as a release build and as a
perf build (-DNV2A_PERF_LOG=1, what HAKUX_PERF_LOG adds in android/app/src/main/cpp/CMakeLists.txt). The command is
the file's entry in the newest Release compile_commands.json under ~/hakuX/android/app/.cxx, with the source tree's
paths moved to this worktree (generated headers stay in the build tree). Prints rc and the diagnostics; exit 1 if
any compile fails. Not a build: no link and no APK.
"""
import glob
import json
import os
import re
import shlex
import subprocess
import sys

SRC = "/home/justin/hakuX"
WT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))


def entry(dbs, rel):
    for db in dbs:
        for e in json.load(open(db)):
            if e["file"] == os.path.join(SRC, rel):
                return e
    return None


def main():
    dbs = sorted(glob.glob(SRC + "/android/app/.cxx/Release/*/arm64-v8a/compile_commands.json"),
                 key=os.path.getmtime, reverse=True)
    bad = 0
    for rel in sys.argv[1:]:
        e = entry(dbs, rel)
        if not e:
            print("%s: no entry" % rel)
            bad = 1
            continue
        args = shlex.split(e["command"]) if "command" in e else list(e["arguments"])
        out = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == "-o":
                skip = True
                continue
            if a == "-c":
                continue
            if a.startswith("-I" + SRC) and "/android/app/.cxx/" not in a:
                a = "-I" + WT + a[len("-I" + SRC):]
            elif a == os.path.join(SRC, rel):
                a = os.path.join(WT, rel)
            out.append(a)
        for perf in (False, True):
            cmd = out + ["-fsyntax-only"] + (["-DNV2A_PERF_LOG=1"] if perf else [])
            p = subprocess.run(cmd, cwd=e["directory"], capture_output=True, text=True)
            warn = len(re.findall(r"warning:", p.stderr))
            print("%s %s: rc %d, %d warnings" % (rel, "perf" if perf else "release", p.returncode, warn))
            for line in p.stderr.splitlines():
                if "error:" in line or "warning:" in line:
                    print("   " + line.replace(WT + "/", ""))
            bad |= p.returncode != 0
    sys.exit(bad)


main()
