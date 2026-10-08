#!/usr/bin/env python3
"""Print the census series (one xemu-xfr XFR rpc line = 60 command buffers)
of one or more perflog soaks as draws/outer-ms per CB, with in/out, so a
scene that recurs across runs can be matched by its draw counts
(lane.gpunonrender, scope (D)).

    rpcseries.py <request-id> HH:MM:SS HH:MM:SS [<request-id> from until ...]

Each entry: time, draws per CB, outer ms per CB, in/out. Lines that the
perflog build logs under two tags are printed once.
"""
import os, re, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
a = sys.argv[1:]
RX = re.compile(r"XFR rpc all (\S+) (\S+) .* in (\S+) draws (\S+)")
for i in range(0, len(a), 3):
    rid, lo, hi = a[i], a[i + 1], a[i + 2]
    seen = set()
    out = []
    for line in open(os.path.join(D, rid, "logcat.txt"), errors="replace"):
        t = line[6:14]
        if not (lo <= t <= hi):
            continue
        m = RX.search(line)
        if not m:
            continue
        key = (t, m.group(2), m.group(4))
        if key in seen:
            continue
        seen.add(key)
        o, inn, dr = float(m.group(2)), float(m.group(3)), float(m.group(4))
        out.append("%s %4.0f/%5.1f/%.2f" % (t[3:], dr, o, inn / o if o else 0))
    print(rid)
    for j in range(0, len(out), 6):
        print("   " + "  ".join(out[j:j + 6]))
