#!/usr/bin/env python3
"""Which TBs (by entry pc, [tpc787]) gain share of TB time in slow pace
windows? A guest poll loop that waits on the GPU would.

  tbbins.py <logcat> [slow fps] [fast fps]
"""
import re
import sys
from collections import defaultdict

path = sys.argv[1]
slow = float(sys.argv[2]) if len(sys.argv) > 2 else 26.0
fast = float(sys.argv[3]) if len(sys.argv) > 3 else 29.7
TPC = re.compile(r"\[tpc787\] w=\d+ sn=\d+ us=(\d+) drop=\d+ (.*)")
PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) .* ms=([\d.]+)")

started = False
prev_f = None
cur = []
acc = {"slow": [0, defaultdict(int), {}], "fast": [0, defaultdict(int), {}]}
for line in open(path, errors="replace"):
    if not started:
        started = "mark gameplay" in line
        continue
    m = PACE.search(line)
    if m:
        f, ms = int(m.group(1)), float(m.group(2))
        if prev_f is not None and ms > 0 and f > prev_f:
            fps = (f - prev_f) * 1000.0 / ms
            key = "slow" if fps < slow else "fast" if fps >= fast else None
            if key:
                a = acc[key]
                for tot, ents in cur:
                    a[0] += tot
                    for pc, b, us in ents:
                        a[1][pc] += us
                        a[2][pc] = b
        cur = []
        prev_f = f
        continue
    m = TPC.search(line)
    if m:
        ents = []
        for e in m.group(2).split():
            p = e.split(":")
            if len(p) == 4:
                ents.append((p[0], p[1], int(p[2])))
        cur.append((int(m.group(1)), ents))

s, fa = acc["slow"], acc["fast"]
pcs = set(s[1]) | set(fa[1])
rows = []
for pc in pcs:
    ss = s[1][pc] / max(1, s[0])
    fs = fa[1][pc] / max(1, fa[0])
    rows.append((ss - fs, pc, s[2].get(pc) or fa[2].get(pc), ss, fs))
rows.sort()
print("TB time: slow (<%g fps) %d us, fast (>=%g) %d us" % (slow, s[0], fast,
                                                          fa[0]))
print("| pc | bytes | slow share | fast share | slow - fast |")
print("|---|---|---|---|---|")
for d, pc, b, ss, fs in rows[:6] + rows[-10:]:
    print("| %s | %s | %.4f | %.4f | %+.4f |" % (pc, b, ss, fs, d))
