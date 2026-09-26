#!/usr/bin/env python3
"""#431: read each title's swap interval from hakuX's own flip pacing in a soak.

    swap_interval.py <result-id> [...]

A soak's logcat carries one `hakuX-pace` line per 60 flips (profile.c,
docs/testing/perf/pace_check.py): vK counts the flips that consumed K
VBLANKs (v4 is 4 or more). The first line of each process is dropped, as
pace_check.py drops it (its window starts at boot).

A game on presentation interval 2 (a 30 fps cap) can never flip one VBLANK
after its last flip, however fast it renders. So:

  interval 1     1-VBLANK flips are >= 2% of the flips and >= 30 in all: the
                 game is not capped at 30, which is a 60 fps target.
  capped at 30   >= 90% of the flips take exactly 2 VBLANKs, none takes 1,
                 and <= 5% take 3 or more: a steady 30 with headroom.
  inconclusive   otherwise. Most often the emulator is slower than 30 and a
                 60 fps game cannot show its 1-VBLANK flips.

Flips taking 0 VBLANKs (more than one flip inside a VBLANK) are reported:
they mean the game presents immediately, uncapped.

Each soak is read twice: the whole run, and from the route's `mark play`
onward (run.log), which is gameplay only where #397's reviewer confirmed it.
Writes nothing.
"""
import os
import re
import sys
from datetime import datetime

R = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results/"
PACE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\d+\s+\d+\s+I hakuX-pace\s*:|^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+) I/hakuX-pace\(\s*(\d+)\)")
FIELDS = re.compile(r"f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)")


def pace_lines(run):
    out, seen = [], set()
    for line in open(R + run + "/logcat.txt", errors="replace"):
        if "hakuX-pace" not in line:
            continue
        m = FIELDS.search(line)
        if not m:
            continue
        pid = re.search(r"hakuX-pace\(\s*(\d+)\)", line)
        pid = pid.group(1) if pid else "?"
        t = datetime.strptime("2026-" + line[:18], "%Y-%m-%d %H:%M:%S.%f")
        if pid not in seen:          # the first line of a process starts at boot
            seen.add(pid)
            continue
        out.append((t, [int(m.group(i)) for i in range(2, 7)]))
    return out


def mark_play(run):
    try:
        for line in open(R + run + "/run.log", errors="replace"):
            m = re.match(r"ROUTE (\d\d:\d\d:\d\d\.\d+) mark play\s*$", line.strip())
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def classify(v):
    n = sum(v)
    if n == 0:
        return "no flips", n
    f1, f2, f3p = v[1] / n, v[2] / n, (v[3] + v[4]) / n
    if v[1] >= 30 and f1 >= 0.02:
        return "interval 1 (60)", n
    if v[1] == 0 and f2 >= 0.90 and f3p <= 0.05:
        return "capped at 30", n
    return "inconclusive", n


def main():
    for run in sys.argv[1:]:
        lines = pace_lines(run)
        mp = mark_play(run)
        spans = [("whole run", lines)]
        if mp:
            day = lines[0][0].strftime("%Y-%m-%d") if lines else "2026-09-26"
            cut = datetime.strptime(day + " " + mp, "%Y-%m-%d %H:%M:%S.%f")
            spans.append(("from mark play " + mp[:8], [x for x in lines if x[0] >= cut]))
        print(run)
        for label, ls in spans:
            v = [sum(x[1][k] for x in ls) for k in range(5)]
            verdict, n = classify(v)
            pct = ["%4.1f" % (100.0 * c / n) if n else "  - " for c in v]
            print("   %-24s %5d flips  v0..v4 %% %s  -> %s" % (label, n, " ".join(pct), verdict))


if __name__ == "__main__":
    main()
