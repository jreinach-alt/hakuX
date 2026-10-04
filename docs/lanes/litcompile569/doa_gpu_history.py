#!/usr/bin/env python3
"""Gate 4, post hoc: perflog GPU Tot ms/frame and fps after `mark play`, per DOA soak.

    doa_gpu_history.py <result dir>...

One `GPU: Tot` line closes every 60 flips, so each gap between two lines gives
that window's fps. Per run: the median Tot and the median window fps over the
lines after the route's `mark play`, and the median over the "fight-like"
windows (Tot >= 15 ms; the title and menus read 0.3-15 ms). A run is a
different build and route draw each time; this is a distribution for the
pair's base arm to sit in, not a paired test.
"""
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")
GPU = re.compile(r"GPU: Tot:([\d.]+)")
MARK = re.compile(r"hakuX-route.*: mark play")


def run(d):
    lc = os.path.join(d, "logcat.txt")
    play, pts, day, last = False, [], 0.0, None
    for ln in open(lc, errors="replace"):
        m = TS.match(ln)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        if MARK.search(ln):
            play = True
        g = GPU.search(ln)
        if g and play:
            pts.append((t, float(g.group(1))))
    fps = [(60.0 / (b[0] - a[0]), b[1]) for a, b in zip(pts, pts[1:]) if b[0] > a[0]]
    fight = [x for x in fps if x[1] >= 15.0]
    j = json.load(open(os.path.join(d, "result.json")))
    med = lambda xs: statistics.median(xs) if xs else float("nan")
    return (j.get("ref"), j.get("device_label"), len(pts), med([v for _, v in pts]),
            med([f for f, _ in fps]), len(fight), med([v for _, v in fight]), med([f for f, _ in fight]))


def main(ds):
    print("%-48s %-10s %-5s %4s %8s %6s | %4s %9s %6s" % (
        "result", "ref", "dev", "n", "Tot ms", "fps", "nF", "fight Tot", "fps"))
    for d in ds:
        try:
            r = run(d)
        except Exception as e:  # noqa: BLE001  one unreadable run does not stop the table
            print("%-48s unreadable: %s" % (os.path.basename(d.rstrip("/")), e))
            continue
        print("%-48s %-10s %-5s %4d %8.1f %6.1f | %4d %9.1f %6.1f" % (
            os.path.basename(d.rstrip("/"))[:48], r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
