#!/usr/bin/env python3
"""Per-line pacing timeline of a title soak, for one or more runs side by side.

    timeline.py <logcat.txt> [<logcat.txt> ...]

For every `hakuX-perf gfps=` line (printed each 60th guest frame, profile.c):
seconds since the first hakuX line, gfps, G (guest flip-to-flip ms, median and
range over the 60 frames), Vpf (VBLANKs per flip) and Ri (renderer-thread idle
ms per guest frame). Renderer busy = 1 - Ri/G. Also prints each `hakuX-audiocap
starve:` line, whose zero-filled share says whether the guest's audio kept up
with real time in that window.
"""
import re
import sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/(hakuX[\w-]*)\(\s*\d+\):\s?(.*)$")
PERF = re.compile(r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\).*?S:([\d.]+) J:([\d.]+) "
                  r"Df:(\d+).*?Vpf:([\d.]+) Ri:([\d.]+) Tq:(\d+)")
STARVE = re.compile(r"starve: (\d+)/(\d+) callbacks short.*?= ([\d.]+)% of output")


def rows(path):
    t0 = None
    out = []
    for line in open(path, errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        t = datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if t0 is None:
            t0 = t
        tag, body = m.group(2), m.group(3)
        if tag == "hakuX-perf" and body.startswith("gfps="):
            p = PERF.search(body)
            if p:
                g = p.groups()
                busy = 100.0 * (1 - float(g[8]) / float(g[1])) if float(g[1]) else 0
                out.append("%6.1f gfps=%-3s G=%6s (%6s-%7s) Vpf=%-5s Ri=%-6s busy=%3.0f%%" % (
                    t - t0, g[0], g[1], g[2], g[3], g[7], g[8], busy))
        elif tag == "hakuX-audiocap" and "starve:" in body:
            s = STARVE.search(body)
            if s:
                out.append("%6.1f   audio starve %s/%s callbacks short, %s%% zero-filled" % (
                    (t - t0,) + s.groups()))
    return out


for p in sys.argv[1:]:
    print("==", p)
    print("\n".join(rows(p)))
