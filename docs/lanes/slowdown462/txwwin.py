#!/usr/bin/env python3
"""The txw[] per-step wall of pgraph_vk_bind_textures over a soak window.

    txwwin.py <result dir> <from s> <to s>

txw[] (hakuX-stall, 26936d9639 perflog) writes one line per 60 guest flips:
`txw[f<flips> <s> bt<ms>/<calls> res<ms> ct<ms>/<calls> sdl.. scan.. faf..
bs.. flq nd cp.. up..]`, each ms per flip, most with calls per flip. Seconds
count from the first hakuX-route line (the route's start, a second or two
after launch), as the other windows in these NOTES do. Lines are weighted by
their flips. Nesting: bt holds res and ct; ct holds sdl, scan, faf, bs, cp,
up; bs holds flq and nd.
"""
import re
import sys
from datetime import datetime

d, lo, hi = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")
t0 = None
rows = []
for l in open(f"{d}/logcat.txt", errors="replace"):
    if t0 is None and "hakuX-route" in l:
        t0 = ts(l)
    m = re.search(r"txw\[f(\d+) ([0-9.]+)s (.*)\]", l)
    if m and t0:
        t = (ts(l) - t0).total_seconds()
        kv = {}
        for k, ms, calls in re.findall(r"([a-z]+)([0-9.]+)(?:/([0-9.]+))?", m.group(3)):
            kv[k] = (float(ms), float(calls) if calls else None)
        rows.append((t, int(m.group(1)), float(m.group(2)), kv))
if t0 is None:
    sys.exit("no hakuX-route line in logcat")
inw = [r for r in rows if lo <= r[0] <= hi]
flips = sum(r[1] for r in inw)
secs = sum(r[2] for r in inw)
if not flips:
    sys.exit(f"no txw lines in {lo}-{hi} s")
print(f"{len(inw)} txw lines, {flips} flips in {secs:.1f} s = {flips / secs:.2f} fps, "
      f"{1000 * secs / flips:.1f} ms/flip (window {lo:.0f}-{hi:.0f} s)")
keys = list(inw[0][3])
for k in keys:
    ms = sum(r[3][k][0] * r[1] for r in inw) / flips
    c = [r[3][k][1] for r in inw if r[3][k][1] is not None]
    cs = f"  {sum(r[3][k][1] * r[1] for r in inw) / flips:6.2f} calls/flip" if c else ""
    print(f"{k:5s} {ms:6.2f} ms/flip{cs}")
