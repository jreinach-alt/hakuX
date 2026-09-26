#!/usr/bin/env python3
"""vCPU-side counters of a title soak, per line, beside the pacing they explain.

    cpuread.py <logcat.txt>

Prints, with seconds since the first hakuX line:
  [tlb68]  cpu (vCPU thread CPU ms per ~2 s window, cputlb.c), sd (tlb_set_dirty:
           notdirty writes re-enabled), rd/rdc (tlb_reset_dirty / code arming),
           jc (jump-cache flushes), rdus/jcus (their time, us)
  pages    slow stores and how many reached the invalidator, plus the inval
           line's ev/cg/iv (hakuX-pages, #68 instrumentation)
  gfps     the hakuX-perf pacing line's gfps, G and Vpf
"""
import re
import sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/(hakuX[\w-]*)\s*\(\s*\d+\):\s?(.*)$")
KV = re.compile(r"(\w+)=([\w.:,]+)")

t0 = None
for line in open(sys.argv[1], errors="replace"):
    m = TS.match(line)
    if not m:
        continue
    t = datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
    if t0 is None:
        t0 = t
    tag, body = m.group(2), m.group(3)
    t -= t0
    if tag == "hakuX" and body.startswith("[tlb68]"):
        kv = dict(KV.findall(body))
        print("%6.1f tlb68 cpu=%-5s sd=%-8s rd=%-5s rdc=%-5s rdus=%-6s jc=%-5s jcus=%-6s rdo=%-4s pf=%s" % (
            t, kv["cpu"], kv["sd"], kv["rd"], kv["rdc"], kv["rdus"], kv["jc"], kv["jcus"],
            kv["rdo"], kv["pf"]))
    elif tag == "hakuX-pages" and body.startswith("slow stores"):
        s = re.match(r"slow stores (\d+) \((\d+) reached", body)
        print("%6.1f pages slow_stores=%s reached_inval=%s" % (t, s.group(1), s.group(2)))
    elif tag == "hakuX-perf" and body.startswith("gfps="):
        g = re.search(r"gfps=(\d+) G:([\d.]+).*Vpf:([\d.]+)", body)
        print("%6.1f gfps=%s G=%s Vpf=%s" % ((t,) + g.groups()))
