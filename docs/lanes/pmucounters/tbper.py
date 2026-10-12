#!/usr/bin/env python3
"""Per-entry us and entries per frame of one [tpc787] entry pc, by fps bin."""
import re, sys
path, pc = sys.argv[1], sys.argv[2]
TPC = re.compile(r"\[tpc787\] w=\d+ sn=(\d+) us=(\d+) drop=\d+ (.*)")
PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) .* ms=([\d.]+)")
started = False; prev_f = None; cur = []
bins = {}
for line in open(path, errors="replace"):
    if not started:
        started = "mark gameplay" in line; continue
    m = PACE.search(line)
    if m:
        f, ms = int(m.group(1)), float(m.group(2))
        if prev_f is not None and ms > 0 and f > prev_f:
            fps = (f - prev_f) * 1000.0 / ms
            k = "<24" if fps < 24 else "24-27" if fps < 27 else "27-29.7" if fps < 29.7 else ">=29.7"
            b = bins.setdefault(k, [0, 0, 0, 0, 0])
            b[0] += f - prev_f
            for sn, tot, us, n in cur:
                b[1] += us; b[2] += n; b[3] += sn; b[4] += tot
        cur = []; prev_f = f; continue
    m = TPC.search(line)
    if m:
        us = n = 0
        for e in m.group(3).split():
            p = e.split(":")
            if len(p) == 4 and p[0] == pc:
                us, n = int(p[2]), int(p[3])
        cur.append((int(m.group(1)), int(m.group(2)), us, n))
print("| bin | frames | us/entry | sampled entries/frame | timed dispatches/frame | share of TB time |")
print("|---|---|---|---|---|---|")
for k in ("<24", "24-27", "27-29.7", ">=29.7"):
    if k in bins:
        fr, us, n, sn, tot = bins[k]
        print("| %s | %d | %.2f | %.2f | %.0f | %.3f |" % (k, fr, us / max(1, n), n / fr, sn / fr, us / max(1, tot)))
