#!/usr/bin/env python3
"""Group N pgraph runs' captures by content, capture by capture.

usage: capgroups.py LABEL=<result dir> [LABEL=<result dir> ...]

For every capture name in any run, each run gets a letter: runs whose file
is byte-identical share a letter, '-' is a run without that capture. A
capture is printed when its runs do not all share one letter. The pattern
is what separates a render-mode difference (the sysmem runs share a letter
no GMEM run has, on every repeat) from a test that differs run to run (the
letters split inside one mode).

The PNG's decoded pixels are not read: two encodings of one image would
count as different, which errs toward reporting.
"""
import hashlib
import os
import sys


def captures(root):
    out = {}
    d = os.path.join(root, "captures1")
    for dp, _dn, fn in os.walk(d):
        for f in fn:
            if not f.endswith(".png"):
                continue
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, d)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def main():
    runs = []
    for a in sys.argv[1:]:
        label, _, path = a.partition("=")
        runs.append((label, captures(path)))
    names = sorted(set().union(*[set(c) for _l, c in runs]))
    print("runs:", " ".join("%s(%d)" % (l, len(c)) for l, c in runs))
    print("captures in any run:", len(names))
    patterns = {}
    moved = 0
    for n in names:
        letters = {}
        pat = []
        for _l, c in runs:
            h = c.get(n)
            if h is None:
                pat.append("-")
                continue
            if h not in letters:
                letters[h] = chr(ord("a") + len(letters))
            pat.append(letters[h])
        if len(letters) > 1:
            moved += 1
            p = "".join(pat)
            patterns.setdefault(p, []).append(n)
    print("captures whose runs are not all identical:", moved)
    print("pattern columns:", ",".join(l for l, _c in runs))
    for p in sorted(patterns, key=lambda k: (-len(patterns[k]), k)):
        v = patterns[p]
        print("%s  %3d  %s" % (p, len(v), ", ".join(v[:4]) + (" ..." if len(v) > 4 else "")))


if __name__ == "__main__":
    main()
