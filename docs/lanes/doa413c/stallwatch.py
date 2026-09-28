#!/usr/bin/env python3
"""Wait, on a live soak logcat, for the start of a DOA scene-load stall (#413).

    stallwatch.py <logcat.txt> <timeout s> [--gap 4] [--cpu 1500] [--after 'mark booted' --runlog soak.log]

A stall, as PR #417 measured it: the pusher gets nothing and nothing flips
(no `fifoskew` and no `gfps=` line), while the vCPU thread is pegged (the
last `[tlb68]` cpu= at least 1500 ms of its 2000 ms window). The logcat's own
clock is the reference: the gap is (newest line of any tag) - (newest
fifoskew/gfps line), so a slow host poll cannot fake one. `[tlb68]` and the
audio lines keep printing through a stall, which is what advances "newest".

Exit 0 with one line describing the stall when it holds; 1 on timeout.
--selftest runs the known answers below.
"""
import re
import sys
import time

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def state(lines):
    """(newest, last_work, last_cpu) over the lines; any may be None."""
    newest = last_work = last_cpu = None
    for line in lines:
        t = secs(line)
        if t is None:
            continue
        newest = t if newest is None else max(newest, t)
        if "fifoskew win=" in line or "gfps=" in line:
            last_work = t
        m = re.search(r"\[tlb68\] w=\d+ dt=\d+ cpu=(\d+)", line)
        if m:
            last_cpu = int(m.group(1))
    return newest, last_work, last_cpu


def stalled(lines, gap, cpu):
    newest, last_work, last_cpu = state(lines)
    if newest is None or last_work is None or last_cpu is None:
        return None
    if newest - last_work >= gap and last_cpu >= cpu:
        return f"stall: {newest - last_work:.1f} s since the last fifoskew/gfps line, vCPU cpu={last_cpu}"
    return None


def selftest():
    fight = [
        "09-26 12:52:41.520 I/hakuX-perf(1): fifoskew win=2002ms kicks=126",
        "09-26 12:52:41.621 I/hakuX-perf(1): gfps=29 x",
        "09-26 12:52:41.906 W/hakuX   (1): [tlb68] w=1 dt=2000 cpu=1950 ff=0",
        "09-26 12:52:43.521 I/hakuX-perf(1): fifoskew win=2001ms kicks=124",
        "09-26 12:52:43.933 W/hakuX   (1): [tlb68] w=2 dt=2000 cpu=1941 ff=0",
    ]
    assert stalled(fight, 4, 1500) is None, "a live pusher is not a stall"
    gap = fight + [
        "09-26 12:52:45.933 W/hakuX   (1): [tlb68] w=3 dt=2000 cpu=1833 ff=0",
        "09-26 12:52:47.933 W/hakuX   (1): [tlb68] w=4 dt=2000 cpu=1972 ff=0",
    ]
    r = stalled(gap, 4, 1500)
    assert r and "4.4 s" in r, r
    idle = fight + [
        "09-26 12:52:45.933 W/hakuX   (1): [tlb68] w=3 dt=2000 cpu=400 ff=0",
        "09-26 12:52:47.933 W/hakuX   (1): [tlb68] w=4 dt=2000 cpu=300 ff=0",
    ]
    assert stalled(idle, 4, 1500) is None, "a quiet vCPU is a pause, not this stall"
    assert stalled(gap[:1], 4, 1500) is None, "no tlb68 line yet"
    print("selftest ok")


def main():
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        return 0
    path, timeout = sys.argv[1], float(sys.argv[2])
    args = sys.argv[3:]
    opt = {"--gap": "4", "--cpu": "1500", "--after": None, "--runlog": None}
    for k, v in zip(args[::2], args[1::2]):
        opt[k] = v
    gap, cpu = float(opt["--gap"]), int(opt["--cpu"])
    end = time.time() + timeout
    while time.time() < end:
        if opt["--after"]:
            try:
                ready = opt["--after"] in open(opt["--runlog"], errors="replace").read()
            except OSError:
                ready = False
            if not ready:
                time.sleep(1)
                continue
        try:
            lines = open(path, errors="replace").read().splitlines()[-400:]
        except OSError:
            lines = []
        r = stalled(lines, gap, cpu)
        if r:
            print(r)
            return 0
        time.sleep(1)
    return 1


if __name__ == "__main__":
    sys.exit(main())
