#!/usr/bin/env python3
"""Count non-deferred PFIFO finishes (sd) against all finishes in a run's gameplay.

Usage: sd_share.py <result-dir-name>@HH:MM:SS

Reads the hakuX-stall "Finish:N(vtx.. sc.. sd.. ..." counts (one line per 60
frames) from the device time given onward. sd > 0 is the case the GPU-stamp
over-count (5c35880d0a) touched. The run ref c3a0c70ace does not contain that
commit, so these runs carry it wherever sd > 0.
"""
import os
import re
import sys

BASE = os.path.expanduser("~/hakux-work/dispatch/results")
FIN = re.compile(r"Finish:(\d+)\(vtx\d+ sc\d+ sd(\d+)")


def main(arg):
    name, _, start = arg.partition("@")
    path = os.path.join(BASE, name, "logcat.txt")
    fin = sd = lines = 0
    with open(path, errors="replace") as f:
        for line in f:
            if start and line.split()[1] < start:
                continue
            m = FIN.search(line)
            if m:
                lines += 1
                fin += int(m.group(1))
                sd += int(m.group(2))
    share = (100.0 * sd / fin) if fin else 0.0
    print("%s from %s: stall lines=%d finishes=%d sd=%d (%.1f%% of finishes are sd)" % (
        name, start or "start", lines, fin, sd, share))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
