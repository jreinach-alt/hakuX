#!/usr/bin/env python3
"""Exec-loop and indirect-branch probe rates from a dispatch result's logcat.

    rates.py RESULT_ID [RESULT_ID ...] [FROM_S TO_S]

Reads the `[jc425]` line (lane.jcache425, every 2 s): the loop's probes
(`l*` hit + miss outcomes) are one per TB dispatched by cpu_exec_loop, which
is one per return to the loop plus the first TB after a longjmp; the helper's
probes (`i*`) are one per indirect branch or goto_ptr exit. `ln` / `in` are
probes the qht could not answer: the loop's become translations, the
helper's become returns to the loop (the helper hands back the epilogue).
Pairs each window with the nearest `[tlb68]` line's `cpu=`/`dt=` (the vCPU
thread's CPU share). Window: seconds since the first `[jc425]` line
(default 90-240). Prints medians.
"""
import re
import statistics
import sys

R = "/home/justin/hakux-work/dispatch/results/"
KV = re.compile(r"(\w+)=(-?\d+)")
TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d+)")


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    h, mi, s, f = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(f) / 10 ** len(f)


def main():
    args = sys.argv[1:]
    nums = [a for a in args if re.match(r"^\d+(\.\d+)?$", a)]
    lo = float(nums[0]) if nums else 90.0
    hi = float(nums[1]) if len(nums) > 1 else 240.0
    for rid in args:
        if rid not in nums:
            one(rid, lo, hi)


def one(rid, lo, hi):
    t0 = None
    cpu = None
    rows = []
    for line in open(R + rid + "/logcat.txt", errors="replace"):
        if "[tlb68]" in line:
            d = dict((k, int(v)) for k, v in KV.findall(line))
            if d.get("dt"):
                cpu = d["cpu"] / d["dt"]
        elif "[jc425]" in line:
            t = secs(line)
            if t0 is None:
                t0 = t
            if t is None or not lo <= t - t0 <= hi:
                continue
            d = dict((k, int(v)) for k, v in KV.findall(line))
            dt = d["dt"] / 1000.0
            loop = sum(d["l" + o] for o in "heps" + "k")
            ind = sum(d["i" + o] for o in "heps" + "k")
            rows.append((loop / dt, ind / dt, d["in"] / dt, d["ln"] / dt,
                         cpu or 0.0))
    if not rows:
        print(rid, "no [jc425] windows in range")
        return
    med = [statistics.median(r[i] for r in rows) for i in range(5)]
    print("%s: %d windows %g-%gs  loop %.2f M/s  indirect %.2f M/s  "
          "helper qht-none %.0f /s  loop qht-none %.0f /s  vCPU cpu/wall %.3f"
          % (rid, len(rows), lo, hi, med[0] / 1e6, med[1] / 1e6, med[2],
             med[3], med[4]))


if __name__ == "__main__":
    main()
