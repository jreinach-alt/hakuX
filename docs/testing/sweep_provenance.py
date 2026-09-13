#!/usr/bin/env python3
"""Record how old a collected sweep column's binary is.

    sweep_provenance.py <collected-dir> <tip-sha>

`apk_sha` on each row already says *which* binary produced a score. It does not
say *when* that binary is. On 2026-09-12 a scoreboard column labelled
`today-partial` was built from a binary 87 commits and 2,111 `hw/` insertions
behind the branch tip: every correctness fix landed that day was absent from
it, and the table read as though the day had achieved nothing. The `apk_sha`
column could not catch it, because the sha was entirely consistent -- and
consistently old. Consistency is not currency.

Only commits touching `hw/` are counted. A commit that cannot change the build
cannot change a score, and counting docs would raise a warning on every heavy
documentation day -- which is precisely the day a reader learns to skip it.
"""
import json
import os
import subprocess
import sys


def sh(*a):
    try:
        return subprocess.check_output(a, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def main():
    out, tip = sys.argv[1], sys.argv[2]
    refs_file = os.path.join(out, ".refs")
    refs = sorted({l.strip() for l in open(refs_file)} - {""})

    info = []
    for r in refs:
        behind = sh("git", "rev-list", "--count", "%s..HEAD" % r, "--", "hw/")
        info.append({"ref": r,
                     "date": sh("git", "log", "-1", "--format=%cs", r),
                     "hw_behind_tip": int(behind) if behind.isdigit() else None})

    worst = max((i["hw_behind_tip"] or 0) for i in info) if info else 0
    json.dump({"tip": tip, "refs": info, "hw_behind_tip": worst},
              open(os.path.join(out, "PROVENANCE.json"), "w"), indent=2)

    if len(refs) > 1:
        print("  note: %d distinct refs in this column (%s)"
              % (len(refs), ", ".join(refs)))
    if worst:
        print("  WARNING: this column's binary is %d hw/ commit(s) behind %s. "
              "It does not measure the current tree." % (worst, tip))
    else:
        print("  provenance: current with %s on hw/" % tip)


if __name__ == "__main__":
    main()
