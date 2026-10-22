#!/usr/bin/env python3
"""HAKUX_ZREP check for the HAKUX_QRY_INPASS A/B (#433).

usage: zrep_ab.py ZREP_A.txt [ZREP_B.txt] [--divisor N] [--max N] [--require-equal]

HAKUX_ZREP (vk/reports.c, #1039) writes
    q <query serial> <samples>
    r <report serial> <last query serial> <offset> <value> <early>
    c <report serial> <last query serial>
and a report counts the queries with serial in (qs of the last clear, its qs]
(ra_run and pgraph_vk_process_pending_reports_internal: the running sum is
zeroed by a clear, divided by the surface scale factor squared on the way out).

Per file:
  identity   every r line after the file's first c line has
             value == sum(q samples in that range) // divisor.
             Lines before the first c are skipped: their sum includes queries
             read before the frame dump armed HAKUX_ZREP. A report whose range
             names a serial with no q line is counted as unchecked.
  qpr        per r line, the q serials in (qs of the previous r or c, its qs]:
             a query split by a pass end shows here, never in a value.
With two files, the r lines are aligned by their offset sequence and the
aligned values compared: equal / differing, and the largest difference.

Exit 1 if either file has an identity mismatch or no checked report, or with
--require-equal if an aligned value differs or nothing aligned.
"""

import argparse
import bisect
import collections
import difflib
import sys


def load(path):
    qs = {}
    reps = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == "end":
                break
            if p[0] == "q" and len(p) == 3:
                qs[int(p[1])] = int(p[2])
            elif p[0] == "r" and len(p) == 6:
                reps.append(("r", int(p[1]), int(p[2]), int(p[3], 16),
                             int(p[4]), p[5] == "1"))
            elif p[0] == "c" and len(p) == 3:
                reps.append(("c", int(p[1]), int(p[2]), 0, 0, False))
    return qs, reps


def check(path, divisor, cap):
    qs, reps = load(path)
    keys = sorted(qs)
    pre = [0]
    for k in keys:
        pre.append(pre[-1] + qs[k])

    def span(lo, hi):
        """Sum and count of q serials in (lo, hi]."""
        a = bisect.bisect_right(keys, lo)
        b = bisect.bisect_right(keys, hi)
        return pre[b] - pre[a], b - a

    first_c = next((i for i, x in enumerate(reps) if x[0] == "c"), None)
    out = {"path": path, "q": len(qs), "r": sum(1 for x in reps if x[0] == "r"),
           "c": sum(1 for x in reps if x[0] == "c"), "checked": 0, "bad": [],
           "unchecked": 0, "early": 0, "qpr": collections.Counter(),
           "seq": []}
    if first_c is None:
        return out
    last_c = reps[first_c][2]
    prev = last_c
    for kind, rs, q, off, value, early in reps[first_c + 1:]:
        _, n = span(prev, q)
        prev = q
        if kind == "c":
            last_c = q
            continue
        out["qpr"][n] += 1
        if len(out["seq"]) < cap:
            out["seq"].append((off, value))
        out["early"] += early
        s, n = span(last_c, q)
        if n != q - last_c:
            out["unchecked"] += 1
            continue
        out["checked"] += 1
        if s // divisor != value:
            out["bad"].append((rs, off, value, s // divisor, n))
    return out


def show(o):
    print(f"{o['path']}: q={o['q']} r={o['r']} c={o['c']}  identity: "
          f"checked={o['checked']} mismatch={len(o['bad'])} "
          f"unchecked={o['unchecked']} early={o['early']}")
    hist = " ".join(f"{k}:{v}" for k, v in sorted(o["qpr"].items())[:12])
    print(f"  queries per report  {hist}")
    for rs, off, value, want, n in o["bad"][:10]:
        print(f"  MISMATCH rs={rs} off=0x{off:x} value={value} "
              f"sum//div={want} over {n} queries")


def compare(a, b):
    sa = [x[0] for x in a["seq"]]
    sb = [x[0] for x in b["seq"]]
    sm = difflib.SequenceMatcher(None, sa, sb, autojunk=False)
    aligned = equal = 0
    worst = (0, None)
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            va, vb = a["seq"][i + k][1], b["seq"][j + k][1]
            aligned += 1
            if va == vb:
                equal += 1
            elif abs(va - vb) > worst[0]:
                worst = (abs(va - vb), (sa[i + k], va, vb))
    print(f"A/B: aligned={aligned} of {len(sa)}/{len(sb)} reports  "
          f"equal={equal} differ={aligned - equal}")
    if worst[1]:
        off, va, vb = worst[1]
        print(f"  largest difference at off=0x{off:x}: A={va} B={vb}")
    return aligned, equal


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--divisor", type=int, default=1,
                    help="surface scale factor squared (default 1)")
    ap.add_argument("--max", type=int, default=20000,
                    help="reports per file taken into the A/B alignment")
    ap.add_argument("--require-equal", action="store_true")
    args = ap.parse_args()
    if len(args.files) > 2:
        ap.error("one or two files")
    res = [check(p, args.divisor, args.max) for p in args.files]
    rc = 0
    for o in res:
        show(o)
        if o["bad"]:
            rc = 1
        if o["checked"] == 0:
            print("  NOTHING CHECKED (no c line, or no report after it: "
                  "was a frame dump armed?)")
            rc = 1
    if len(res) == 2:
        aligned, equal = compare(*res)
        if args.require_equal and (aligned == 0 or aligned != equal):
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
