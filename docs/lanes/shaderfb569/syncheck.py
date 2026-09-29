#!/usr/bin/env python3
"""-fsyntax-only on this lane's C files, with an existing build's flags.

    syncheck.py <compile_commands.json> [<source tree the build was made from>]

Takes each file's recorded compile command, points its source and every
include under the recorded tree at this worktree, drops -o/-MD outputs and
runs it with -fsyntax-only -Werror=implicit-function-declaration. Exit 1 on
any error.
"""
import json
import os
import shlex
import subprocess
import sys

FILES = ["hw/xbox/nv2a/pgraph/vk/draw.c", "hw/xbox/nv2a/pgraph/vk/compile_worker.c",
         "hw/xbox/nv2a/pgraph/vk/glsl.c", "hw/xbox/nv2a/pgraph/profile.c"]
HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def main():
    cc = sys.argv[1]
    src = sys.argv[2] if len(sys.argv) > 2 else "/home/justin/hakuX"
    db = json.load(open(cc))
    bad = 0
    for f in FILES:
        m = [e for e in db if e["file"].endswith(f) or e["file"].endswith("../" + f)]
        if not m:
            print("no command for", f)
            bad += 1
            continue
        e = m[0]
        args = e.get("arguments") or shlex.split(e["command"])
        out, skip = [], False
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("-o", "-MF", "-MQ", "-MT", "-c"):
                skip = a != "-c"
                continue
            if a == "-MD" or a.endswith(".c") and f.split("/")[-1] in a:
                continue
            if a.startswith("-I") and not a[2:].startswith("/"):
                a = "-I" + os.path.normpath(os.path.join(e["directory"], a[2:]))
            pre = "-I" if a.startswith("-I") else ""
            path = a[len(pre):]
            if (path == src or path.startswith(src + "/")) and not any(
                    path.startswith(src + x) for x in
                    ("/android/app/.cxx", "/subprojects", "/build")):
                a = pre + HERE + path[len(src):]
            out.append(a)
        # Relative includes (desktop build: -I../hw/...) resolve from the build
        # dir; put this tree's copies first.
        out += ["-I" + HERE + "/include", "-iquote", os.path.join(HERE, os.path.dirname(f)),
                "-fsyntax-only", "-Werror=implicit-function-declaration",
                os.path.join(HERE, f)]
        r = subprocess.run(out, cwd=e["directory"], capture_output=True, text=True)
        errs = [l for l in r.stderr.splitlines() if "error" in l]
        warns = [l for l in r.stderr.splitlines() if "warning" in l and HERE in l]
        print("%-45s rc=%d errors=%d warnings(in tree)=%d" % (f, r.returncode, len(errs), len(warns)))
        for l in errs[:20] + warns[:20]:
            print("   ", l)
        bad += r.returncode != 0
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
