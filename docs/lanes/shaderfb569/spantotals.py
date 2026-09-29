#!/usr/bin/env python3
"""Totals of the #569 fields over named spans of a soak (post-hoc reading aid).

    spantotals.py <logcat.txt>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbwin  # noqa: E402

KEYS = ("dt_ms", "dpm", "dpc_ms", "dvs_ms", "dgs_ms", "dfs_ms", "dsru", "dsrum", "dsru_ms",
        "dsnu", "dsnum", "dsnu_ms", "dgl_ms", "dsmod_ms", "dsv_ms", "dins_us")
SPANS = (("fight load 1 (frames: char select -> fight)", "16:20:15", "16:20:31"),
         ("win -> title -> stage 2 load", "16:23:21", "16:24:08"),
         ("attract/intro (16:19:30 window)", "16:19:30", "16:19:31"))


def main():
    wins, _, _ = fbwin.parse(open(sys.argv[1], errors="replace"))
    for name, a, b in SPANS + (("whole run", "00", "99"),):
        S = fbwin.span_of(wins, a, b)
        print("%s: %d windows" % (name, len(S)))
        print("   " + " ".join("%s=%.1f" % (k, fbwin.total(S, k)) for k in KEYS))
        print("   kd " + fbwin.fmt_kd(fbwin.kd_sum(S)))


if __name__ == "__main__":
    main()
