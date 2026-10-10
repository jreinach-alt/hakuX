#!/usr/bin/env python3
"""Pace windows binned by the vCPU's work per frame, per run: does a run
spend more off-CPU time per frame than another at the same work?

  workbin.py <spin pc> LABEL=<logcat or result dir> [...]

A window's work = on-CPU less the spin loop, ms/frame, as spinfps.py
computes it ([tlb68] on-CPU; [tpc787] share x [rr425] TB fraction for the
spin). Two runs of one route can ride different parts of the map, so their
fps and off-CPU differ by scene as well as by arm; at equal work per frame
the scene's load on the vCPU is matched and the off-CPU difference is the
arm's (or a GPU-side difference the vCPU waits on).
"""
import os
import re
import sys

TPC = re.compile(r"\[tpc787\] w=\d+ sn=\d+ us=(\d+) drop=\d+ (.*)")
RR = re.compile(r"\[rr425\] .* gapus=(\d+) tbus=(\d+)")
PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) .* ms=([\d.]+)")
TLB = re.compile(r"\[tlb68\] w=\d+ dt=(\d+) cpu=(\d+)")
LOCK = re.compile(r"\[lock474\] dt_ms=\d+ rd=\d+ rd_slow=\d+ rd_wait_ms=([\d.]+)"
                  r" .* wr_wait_ms=([\d.]+)")
BINS = [(0, 17), (17, 19), (19, 21), (21, 23), (23, 25), (25, 27), (27, 99)]


def windows(path, pc):
    if os.path.isdir(path):
        path = os.path.join(path, "logcat.txt")
    started = False
    wins = []
    cur = {"dt": 0, "cpu": 0, "spin": [], "tbf": [], "lock": 0.0}
    prev_f = None
    for line in open(path, errors="replace"):
        if not started:
            started = "mark gameplay" in line
            continue
        m = PACE.search(line)
        if m:
            f, ms = int(m.group(1)), float(m.group(2))
            if prev_f is not None and ms > 0 and f > prev_f:
                cur["frames"], cur["ms"] = f - prev_f, ms
                wins.append(cur)
            cur = {"dt": 0, "cpu": 0, "spin": [], "tbf": [], "lock": 0.0}
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
    out = []
    for w in wins:
        if not (w["dt"] and w["spin"] and w["tbf"]):
            continue
        wall = w["ms"] / w["frames"]
        on = w["cpu"] / w["dt"] * wall
        spin = on * (sum(w["spin"]) / len(w["spin"])) * \
            (sum(w["tbf"]) / len(w["tbf"]))
        out.append({"frames": w["frames"], "ms": w["ms"], "wall": wall,
                    "on": on, "spin": spin, "work": on - spin,
                    "off": wall - on, "lock": w["lock"] / w["frames"]})
    return out


def row(label, name, ws):
    if not ws:
        return
    fr = sum(w["frames"] for w in ws)
    ms = sum(w["ms"] for w in ws)

    def per(k):
        return sum(w[k] * w["frames"] for w in ws) / fr
    print("| %s | %s | %d | %.1f | %.1f | %.1f | %.1f | %.2f |" % (
        name, label, len(ws), fr * 1000.0 / ms, per("work"), per("off"),
        per("spin"), per("lock")))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    pc = argv[0]
    runs = []
    for a in argv[1:]:
        label, _, path = a.partition("=")
        runs.append((label, windows(path, pc)))
    print("| work bin ms/f | run | windows | fps | work ms/f | off-CPU ms/f "
          "| spin ms/f | lock474 ms/f |")
    print("|---|---|---|---|---|---|---|---|")
    for lo, hi in BINS:
        for label, ws in runs:
            row(label, "%g-%g" % (lo, hi),
                [w for w in ws if lo <= w["work"] < hi])
    for label, ws in runs:
        row(label, "all", ws)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
