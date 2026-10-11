#!/usr/bin/env python3
"""Calibration table: for every logcat under the work tree that carries [rr425w] telemetry, the longest stretch in
which the guest is pinned (one pc takes the returns, idle ~0), the longest stretch in which the guest's audio is
quiet (no new non-silent window), and the longest stretch in which both hold. Frames are not in a logcat, so the
third signal (the screen) is not scored here: pinned+quiet is an UPPER BOUND for the HANG rule.

    python3 docs/lanes/hangwatch/calibrate.py [root]

Prints a markdown table, longest pinned+quiet first. Read-only.
"""

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import hangwatch  # noqa: E402


def main(argv):
    root = argv[0] if argv else "/home/justin/hakux-work"
    paths = []
    for dp, dn, fn in os.walk(root):
        if "/.git" in dp or dp.count("/") > 12:
            continue
        for f in fn:
            if "logcat" in f and f.endswith((".txt", ".log")):
                paths.append(os.path.join(dp, f))
    rows = []
    for p in sorted(paths):
        try:
            with open(p, "rb") as f:
                head = f.read()
        except OSError:
            continue
        if b"[rr425w]" not in head:
            continue
        with open(p, errors="replace") as f:
            longest, events = hangwatch.scan(f)
        pinned = [v for _, s, v in events if s == "pinned"]
        if not pinned:
            continue
        rows.append((longest["pinned+quiet"], longest["pinned"], longest["quiet"], sum(pinned) / len(pinned),
                     len(pinned), p))
    rows.sort(reverse=True)
    print(f"logcats with [rr425w] telemetry: {len(rows)} (of {len(paths)} logcat files under {root})")
    print()
    print("| pinned+quiet s | pinned s | quiet s | pinned share of windows | windows | log |")
    print("|---:|---:|---:|---:|---:|---|")
    for pq, pn, qu, share, nwin, p in rows:
        print(f"| {pq:.0f} | {pn:.0f} | {qu:.0f} | {share:.3f} | {nwin} | {p.split('/hakux-work/')[-1]} |")
    if rows:
        print()
        print(f"max pinned+quiet over all {len(rows)} logs: {rows[0][0]:.0f} s")
        print(f"logs with pinned+quiet >= {hangwatch.HANG_S:.0f} s: {sum(1 for r in rows if r[0] >= hangwatch.HANG_S)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
