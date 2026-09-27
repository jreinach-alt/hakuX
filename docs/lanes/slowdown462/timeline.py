#!/usr/bin/env python3
"""Per-60-frame timeline of a perflog soak, with the route's shots beside it.

    timeline.py <result-id>

One row per hakuX-phase line: wall clock (device, as the logcat prints it),
seconds after logcat line 1, gfps, G, Tot, Surf, Draw, Pipe, Fin(Sub), Idle,
GPU and draws/frame (xemu-work, the last frame of the 60). Route events
(marks, shots) print inline at their times. This is how a window is picked by
what was on screen, not by where a route mark happens to fall.
"""
import os
import re
import sys
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\):\s?(.*)$")
NUM = re.compile(r"([A-Za-z]+):([\d.]+)")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


rid = sys.argv[1]
rdir = f"{D}/results/{rid}"
first = None
gf = work = None
events = []
for line in open(f"{rdir}/logcat.txt", errors="replace"):
    m = TS.match(line)
    if not m:
        continue
    t = ts(m.group(1))
    if first is None:
        first = t
    tag, body = m.group(2), m.group(3)
    if tag == "hakuX-perf" and body.startswith("gfps="):
        g = re.search(r"gfps=(\d+) G:([\d.]+)", body)
        gf = (int(g[1]), float(g[2])) if g else None
    elif tag == "xemu-work":
        work = sum(int(v) for k, v in re.findall(r"\b(DA|IE|IB|IA):(\d+)", body))
    elif tag == "hakuX-phase":
        left, _, right = body.partition("|")
        d = {k: float(v) for k, v in NUM.findall(left)}
        r = {k: float(v) for k, v in NUM.findall(right)}
        events.append((t, "%s %6.1f  gfps %3s G %5.1f | Tot %5.1f Surf %5.1f Draw %5.1f Pipe %4.1f Fin %4.1f(Sub %4.1f) Idle %5.1f GPU %5.1f | draws %s" % (
            m.group(1)[6:14], t - first, gf[0] if gf else "-", gf[1] if gf else float("nan"),
            r.get("Tot", float("nan")), d.get("Surf", 0), d.get("Draw", 0), d.get("Pipe", 0),
            d.get("Fin", 0), d.get("Sub", 0), d.get("Idle", 0), r.get("GPU", float("nan")), work)))
    elif tag == "hakuX-route":
        events.append((t, "%s %6.1f  -- route: %s" % (m.group(1)[6:14], t - first, body)))
# the route's shots are named HHMMSS-<name>.png in host time; list them for matching by eye
for t, s in sorted(events):
    print(s)
fr = f"{rdir}/route-frames"
if os.path.isdir(fr):
    print("shots (host clock):", " ".join(sorted(os.listdir(fr))))
