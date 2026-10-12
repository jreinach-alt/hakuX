#!/usr/bin/env python3
"""Per pace window after the mark, binned by the window's fps:
wall, vCPU on-CPU, the spin loop's part of it, and the measured lock wait,
all in ms per frame.

  spinfps.py <logcat> <spin pc> [HH:MM:SS until]

spin ms = [tpc787] share of TB time entered at <pc> x [rr425] TB fraction of
loop time (tbus / (tbus + gapus)) x on-CPU ms. An estimate: the 1-in-64 timed
dispatches are weighted by duration, so a long chained spin is caught whole.
"""
import re
import sys

path, pc = sys.argv[1], sys.argv[2]
until = sys.argv[3] if len(sys.argv) > 3 else None
TS = re.compile(r"^\d\d-\d\d (\d\d:\d\d:\d\d)")
TPC = re.compile(r"\[tpc787\] w=\d+ sn=\d+ us=(\d+) drop=\d+ (.*)")
RR = re.compile(r"\[rr425\] .* gapus=(\d+) tbus=(\d+)")
PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) .* ms=([\d.]+)")
TLB = re.compile(r"\[tlb68\] w=\d+ dt=(\d+) cpu=(\d+)")
LOCK = re.compile(r"\[lock474\] dt_ms=\d+ rd=\d+ rd_slow=\d+ rd_wait_ms=([\d.]+)"
                  r" .* wr_wait_ms=([\d.]+)")


def fresh():
    return {"dt": 0, "cpu": 0, "spin": [], "tbf": [], "lock": 0.0}


started = False
wins = []
cur = fresh()
prev_f = None
for line in open(path, errors="replace"):
    if not started:
        started = "mark gameplay" in line
        continue
    t = TS.match(line)
    if until and t and t.group(1) > until:
        break
    m = PACE.search(line)
    if m:
        f, ms = int(m.group(1)), float(m.group(2))
        if prev_f is not None and ms > 0 and f > prev_f:
            cur["frames"], cur["ms"] = f - prev_f, ms
            wins.append(cur)
        cur = fresh()
        prev_f = f
        continue
    m = TLB.search(line)
    if m:
        cur["dt"] += int(m.group(1))
        cur["cpu"] += int(m.group(2))
        continue
    m = RR.search(line)
    if m:
        g, tb = int(m.group(1)), int(m.group(2))
        if g + tb:
            cur["tbf"].append(tb / (g + tb))
        continue
    m = LOCK.search(line)
    if m:
        cur["lock"] += float(m.group(1)) + float(m.group(2))
        continue
    m = TPC.search(line)
    if m:
        tot = int(m.group(1))
        mine = 0
        for ent in m.group(2).split():
            p = ent.split(":")
            if len(p) == 4 and p[0] == pc:
                mine = int(p[2])
        cur["spin"].append(mine / max(1, tot))

bins = [(0, 24), (24, 27), (27, 29), (29, 29.7), (29.7, 99)]
print("%s: %d pace windows" % (path.split("/")[-2], len(wins)))
print("| fps bin | windows | fps | wall ms/f | on-CPU ms/f | spin ms/f "
      "| on-CPU less spin ms/f | off-CPU ms/f | lock474 wait ms/f |")
print("|---|---|---|---|---|---|---|---|---|")


def row(name, ws):
    ws = [w for w in ws if w["dt"] and w["spin"] and w["tbf"]]
    if not ws:
        return
    fr = sum(w["frames"] for w in ws)
    wall = sum(w["ms"] for w in ws) / fr
    busy = sum(w["cpu"] for w in ws) / sum(w["dt"] for w in ws)
    on = busy * wall
    spin = sum(w["cpu"] / w["dt"] * w["ms"] * (sum(w["spin"]) / len(w["spin"]))
               * (sum(w["tbf"]) / len(w["tbf"])) for w in ws) / fr
    lock = sum(w["lock"] for w in ws) / fr
    print("| %s | %d | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.2f |" % (
        name, len(ws), 1000.0 / wall, wall, on, spin, on - spin, wall - on,
        lock))


for lo, hi in bins:
    row("%g-%g" % (lo, hi),
        [w for w in wins if lo <= w["frames"] * 1000.0 / w["ms"] < hi])
row("all", wins)
