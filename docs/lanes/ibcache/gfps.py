#!/usr/bin/env python3
"""gfps of one capture_gta.sh session, by window relative to the gameplay mark (#507, lane.ibcache).

    gfps.py <session dir> --mark HH:MM:SS --prof HH:MM:SS

--mark and --prof are device-local times (the logcat's clock): the route's
`mark gameplay` and capture_gta.sh's `prof start`. Prints the hakuX-perf gfps
lines' median and range for the gameplay before the profile, and for the two
simpleperf recordings (rec-off at all threads, then rec-on at the vCPU), which
load the device differently. Offline; reads logcat.txt only.
"""
import argparse
import os
import re
import statistics


def secs(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--mark", required=True)
    ap.add_argument("--prof", required=True)
    a = ap.parse_args()
    mark, prof = secs(a.mark), secs(a.prof)
    rows = []
    pat = re.compile(r"^\d\d-\d\d (\d\d:\d\d:\d\d\.\d+) .*hakuX-perf.*"
                     r"gfps=(\d+) G:([\d.]+)")
    for line in open(os.path.join(a.dir, "logcat.txt"), errors="replace"):
        m = pat.match(line)
        if m:
            rows.append((secs(m.group(1)), int(m.group(2)), float(m.group(3))))
    wins = [("mark+10 .. prof start (no profiler)", mark + 10, prof),
            ("prof start .. +30 s (rec-off)", prof, prof + 30),
            ("prof +30 .. +62 s (rec-on, the profile)", prof + 30, prof + 62)]
    print("%s: %d gfps lines, mark %s, prof start %s"
          % (os.path.basename(os.path.normpath(a.dir)), len(rows),
             a.mark, a.prof))
    for name, lo, hi in wins:
        g = [r[1] for r in rows if lo <= r[0] < hi]
        ms = [r[2] for r in rows if lo <= r[0] < hi]
        if not g:
            print("  %-42s no lines" % name)
            continue
        print("  %-42s n=%2d gfps median %4.1f mean %4.1f (min %d max %d), "
              "G median %.1f ms"
              % (name, len(g), statistics.median(g), statistics.mean(g),
                 min(g), max(g), statistics.median(ms)))


if __name__ == "__main__":
    main()
