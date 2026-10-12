#!/usr/bin/env python3
"""The vCPU's measured waits per frame, from lines a perflog run already has.

  waits.py <logcat> [--after REGEX] [--until HH:MM:SS]

From the route's `mark gameplay` on (to --until, if given):
  - [lock474]: the vCPU's PGRAPH MMIO wait for pgraph.lock (reads, writes),
    split by what the PFIFO thread was doing when it began (fs = the flip's
    surface update, fo = the flip op, ot = other), and the top registers;
  - [tlb68]: the vCPU thread's on-CPU ms per window (cpu= over dt=);
  - [idlehalt]: guest halts and the halted time;
  - [hakuX-ft1] (HAKUX_FRAMETRACE=1 runs only): vrun / vblk / vw (the vCPU's
    waits by reason: BQL, pfifo.lock, pgraph.lock, halt, ...) and vh (what
    the lock holder was doing: UNK, RUN, GPU, RENDER, IDLE, WAIT), ms/frame.

Frames come from the hakuX-pace `f=` counter over the same span.
"""
import re
import sys
from collections import defaultdict

TS = re.compile(r"^\d\d-\d\d (\d\d:\d\d:\d\d)")
PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) ")
LOCK = re.compile(r"\[lock474\] dt_ms=(\d+) rd=(\d+) rd_slow=\d+ "
                  r"rd_wait_ms=([\d.]+) rd_fs=([\d.]+) rd_fo=([\d.]+) "
                  r"rd_ot=([\d.]+) wr=\d+ wr_slow=\d+ wr_wait_ms=([\d.]+)")
REG = re.compile(r" r\d=0x([0-9a-f]+):(\d+):([\d.]+)")
TLB = re.compile(r"\[tlb68\] w=\d+ dt=(\d+) cpu=(\d+)")
HALT = re.compile(r"\[idlehalt\] .*?span_us=(\d+) run_us=(\d+) rq_us=(\d+) "
                  r"halts=(\d+)")
FT = re.compile(r"\[hakuX-ft1\] n=(\d+) .*? vrun=([\d.]+) vgw=[\d.]+ "
                r"vgi=([\d.]+) vrq=([\d.]+) vblk=([\d.]+) vw=([\d.,]+) "
                r"vh=([\d.,]+)")
VW = ["bql", "pfifo.lock", "pgraph.lock", "halt", "idle", "fence", "submit",
      "rthread", "download", "other"]
VH = ["UNK", "RUN", "GPU", "RENDER", "IDLE", "WAIT"]


def main(argv):
    after, until, path = r"hakuX-route.*mark gameplay", None, None
    i = 0
    while i < len(argv):
        if argv[i] == "--after":
            after = argv[i + 1]
            i += 2
        elif argv[i] == "--until":
            until = argv[i + 1]
            i += 2
        else:
            path = argv[i]
            i += 1
    if not path:
        print(__doc__)
        return 2
    started = False
    f0 = f1 = None
    lk = defaultdict(float)
    regs = defaultdict(lambda: [0, 0.0])
    tl_dt = tl_cpu = 0
    hl = defaultdict(int)
    ft_n = ft_bad = 0
    ft = defaultdict(float)
    for line in open(path, errors="replace"):
        if not started:
            started = re.search(after, line) is not None
            continue
        t = TS.match(line)
        if until and t and t.group(1) > until:
            break
        m = PACE.search(line)
        if m:
            f = int(m.group(1))
            f0 = f if f0 is None else f0
            f1 = f
            continue
        m = LOCK.search(line)
        if m:
            for k, v in zip(("dt", "rd", "rd_wait", "fs", "fo", "ot", "wr_wait"),
                            m.groups()):
                lk[k] += float(v)
            for a, n, w in REG.findall(line):
                regs[a][0] += int(n)
                regs[a][1] += float(w)
            continue
        m = TLB.search(line)
        if m:
            tl_dt += int(m.group(1))
            tl_cpu += int(m.group(2))
            continue
        m = HALT.search(line)
        if m:
            for k, v in zip(("span", "run", "rq", "halts"), m.groups()):
                hl[k] += int(v)
            continue
        m = FT.search(line)
        if m:
            n = int(m.group(1))
            vw = [float(v) * n for v in m.group(6).split(",")]
            vrun = float(m.group(2)) * n
            # a 1 s summary cannot hold more than ~1 s of one thread's time;
            # fpstelemetry1008's run has one line booking 40 s of lock wait
            if vrun + sum(vw) > 2500:
                ft_bad += 1
                continue
            ft_n += n
            ft["vrun"] += float(m.group(2)) * n
            ft["vgi"] += float(m.group(3)) * n
            ft["vrq"] += float(m.group(4)) * n
            ft["vblk"] += float(m.group(5)) * n
            for k, v in zip(VW, m.group(6).split(",")):
                ft["vw." + k] += float(v) * n
            for k, v in zip(VH, m.group(7).split(",")):
                ft["vh." + k] += float(v) * n
    frames = (f1 - f0) if f0 is not None and f1 is not None else 0
    print("file %s" % path)
    print("frames %d (pace f= %s..%s)" % (frames, f0, f1))
    if not frames:
        return 1
    if tl_dt:
        print("vCPU on-CPU (tlb68): %.1f%% of wall, %.2f ms/frame; "
              "wall %.2f ms/frame" % (100.0 * tl_cpu / tl_dt,
                                      tl_cpu / frames, tl_dt / frames))
    if hl:
        print("idlehalt: halts %d; run %.1f%% rq %.1f%% of span"
              % (hl["halts"], 100.0 * hl["run"] / hl["span"],
                 100.0 * hl["rq"] / hl["span"]))
    if lk:
        print("lock474 (ms/frame): read wait %.2f (fs %.2f, fo %.2f, ot %.2f),"
              " write wait %.2f; reads %.1f/frame; %.1f%% of wall"
              % (lk["rd_wait"] / frames, lk["fs"] / frames,
                 lk["fo"] / frames, lk["ot"] / frames,
                 lk["wr_wait"] / frames, lk["rd"] / frames,
                 100.0 * lk["rd_wait"] / lk["dt"]))
        top = sorted(regs.items(), key=lambda kv: -kv[1][1])[:4]
        print("  top registers by wait (ms/frame, reads/frame): " + ", ".join(
            "0x%s %.2f (%.1f)" % (a, w / frames, n / frames)
            for a, (n, w) in top))
    if ft_n:
        print("frametrace over %d flips (ms/frame; %d impossible lines "
              "dropped): vrun %.2f vrq %.2f vblk %.2f vgi %.2f"
              % (ft_n, ft_bad, ft["vrun"] / ft_n, ft["vrq"] / ft_n,
                 ft["vblk"] / ft_n, ft["vgi"] / ft_n))
        print("  vw: " + ", ".join("%s %.2f" % (k, ft["vw." + k] / ft_n)
                                   for k in VW if ft["vw." + k]))
        print("  vh (holder over the vCPU's lock waits): " + ", ".join(
            "%s %.2f" % (k, ft["vh." + k] / ft_n) for k in VH))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
