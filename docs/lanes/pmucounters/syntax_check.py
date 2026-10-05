#!/usr/bin/env python3
"""lane.pmucounters (#433): compile-check the [pmu433] hook INSIDE cpu-exec.c
with the Android build's own flags, before the grant lets it into the tree.

Takes the cpu-exec.c entry of the newest Android compile_commands.json, makes
a copy of this worktree's accel/tcg/cpu-exec.c with the two-hunk patch the
grant asks for (apply_hook below), puts hakux-pmu.c.inc beside it, points the
source-tree -I paths at this worktree, and runs the same compiler with
-fsyntax-only -Werror. Exit 0 = clean.

  syntax_check.py [--write] [--falsify]
      --write    applies the patch to the real file (after the grant only)
      --falsify  plants an undeclared name in the copied hook; must FAIL
"""
import glob
import json
import os
import shlex
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.abspath(os.path.join(HERE, "../../.."))
SRC_TREE = "/home/justin/hakuX"

INCLUDE = """
/* #433 [pmu433]: the CPU's own counters on this thread; HAKUX_PMU=1 only. */
#if defined(XBOX) && defined(__linux__)
#include "hw/xbox/nv2a/debug.h"
#include "hakux-pmu.c.inc"
#define PMU433_TICK() pmu433_tick()
#else
#define PMU433_TICK() do { } while (0)
#endif
"""
ANCHOR_INC = "#define JC425_COUNT(c, o) do { } while (0)\n#endif\n"
ANCHOR_CALL = "                    rr425_tick(cpu);\n"


def apply_hook(text):
    assert text.count(ANCHOR_INC) == 1, "include anchor"
    assert text.count(ANCHOR_CALL) == 1, "call anchor"
    text = text.replace(ANCHOR_INC, ANCHOR_INC + INCLUDE)
    return text.replace(ANCHOR_CALL,
                        ANCHOR_CALL + "                    PMU433_TICK();\n")


def main(argv):
    src = os.path.join(TREE, "accel/tcg/cpu-exec.c")
    text = apply_hook(open(src).read())
    if "--write" in argv:
        open(src, "w").write(text)
        shutil.copy(os.path.join(HERE, "hakux-pmu.c.inc"),
                    os.path.join(TREE, "accel/tcg/hakux-pmu.c.inc"))
        print("patched", src)
    dbs = sorted(glob.glob(SRC_TREE + "/android/app/.cxx/Release/*/arm64-v8a/"
                           "compile_commands.json"), key=os.path.getmtime)
    entry = None
    for e in json.load(open(dbs[-1])):
        if e["file"].endswith("accel/tcg/cpu-exec.c"):
            entry = e
            break
    assert entry, "no cpu-exec.c in " + dbs[-1]
    scratch = os.path.join(TREE, "scratch/syntax")
    os.makedirs(scratch, exist_ok=True)
    tmp = os.path.join(scratch, "cpu-exec.c")
    open(tmp, "w").write(text)
    shutil.copy(os.path.join(HERE, "hakux-pmu.c.inc"), scratch)
    if "--falsify" in argv:
        # the check must see the new code: an undeclared name in the copy
        # has to FAIL it (else XBOX/__linux__ hid the include and the PASS
        # is vacuous)
        with open(os.path.join(scratch, "hakux-pmu.c.inc"), "a") as f:
            f.write("\nstatic int PMU433_falsify(void) "
                    "{ return pmu433_no_such_name; }\n")
    args = shlex.split(entry["command"]) if "command" in entry \
        else entry["arguments"]
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
        # source-tree paths -> this worktree; generated (build) dirs stay
        if a.startswith(("-I" + SRC_TREE, SRC_TREE)) and "/.cxx/" not in a:
            a = a.replace(SRC_TREE + "/", TREE + "/")
        out.append(a)
    # the real file's own dir first for "trace.h" and friends, as for the
    # real file; then only the diagnostics in the new code count (the tree
    # has its own warnings, and the build does not use -Werror)
    out = out[:1] + ["-iquote", os.path.join(TREE, "accel/tcg")] + out[1:]
    out += ["-fsyntax-only", "-Wall", "-Wextra", "-Wno-unused-parameter",
            "-Wno-sign-compare", "-Wno-missing-field-initializers", tmp]
    print("db:", dbs[-1])
    r = subprocess.run(out, cwd=entry["directory"], capture_output=True,
                       text=True)
    lines = r.stderr.splitlines()
    mine = [ln for ln in lines if "hakux-pmu.c.inc" in ln or "PMU433" in ln]
    errors = [ln for ln in lines if " error: " in ln]
    for ln in mine + errors:
        print(ln)
    ok = r.returncode == 0 and not mine
    print("syntax check: %s (%d diagnostics in the new code, %d errors, "
          "%d lines of other warnings)" % ("PASS" if ok else "FAIL",
                                          len(mine), len(errors), len(lines)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
