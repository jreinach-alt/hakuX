#!/usr/bin/env python3
"""Guest idle share and vCPU run time over the scored window (#507, leg 5a).

    idleread.py <request id> ...

From soakread.py's scratch copies: for each `[rr425w]` window from
mark gameplay + 10 s to the end, idle_us / (idle_us + busy_us) (the guest's
own idle loop at 8001b02e), and for each `[idlehalt]` window run_us / span_us
(vCPU host thread on-CPU). Prints the median and the count of each. A probe
that saves vCPU work on a capped title moves the idle share up; if the vCPU
stays on-CPU, the saving is spin (see the vcpu-saving-is-spin memory).
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "scratch", "res"))
TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")
RRW = re.compile(r"\[rr425w\] .*idle_us=(\d+) busy_us=(\d+)")
IH = re.compile(r"\[idlehalt\] .*span_us=(\d+) run_us=(\d+)")
LK = re.compile(r"\[lock474\] dt_ms=(\d+) rd=(\d+) .*rd_wait_ms=([\d.]+) .*wr=(\d+) ")
MARK = re.compile(r"ROUTE (\d\d):(\d\d):(\d\d\.\d+) mark gameplay")


def secs(m):
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


for rid in sys.argv[1:]:
    d = os.path.join(SCR, rid)
    mark = None
    for line in open(os.path.join(d, "run.log"), errors="replace"):
        m = MARK.match(line)
        if m:
            mark = secs(m)
    idle, run, rd, rdw, wr = [], [], [], [], []
    for line in open(os.path.join(d, "logcat.txt"), errors="replace"):
        t = TS.match(line)
        if not t or mark is None or secs(t) < mark + 10:
            continue
        m = RRW.search(line)
        if m:
            i, b = int(m.group(1)), int(m.group(2))
            if i + b:
                idle.append(i / (i + b))
        m = IH.search(line)
        if m and int(m.group(1)):
            run.append(int(m.group(2)) / int(m.group(1)))
        m = LK.search(line)
        if m and int(m.group(1)):
            s = int(m.group(1)) / 1000
            rd.append(int(m.group(2)) / s)
            rdw.append(float(m.group(3)) / s)
            wr.append(int(m.group(4)) / s)
    med = lambda xs: round(statistics.median(xs), 4) if xs else None
    print(json.dumps({"id": rid, "mark": mark is not None,
                      "guest_idle_med": med(idle), "n_rrw": len(idle),
                      "vcpu_oncpu_med": med(run), "n_ih": len(run),
                      "pgraph_rd_per_s": med(rd), "rd_wait_ms_per_s": med(rdw),
                      "pgraph_wr_per_s": med(wr), "n_lk": len(rd)}))
