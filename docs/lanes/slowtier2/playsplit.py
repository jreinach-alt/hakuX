#!/usr/bin/env python3
"""Medians of a perflog soak's per-window lines over one span, with the log
line numbers they came from.

    playsplit.py <result-id> <from-s> <to-s>

Seconds are after logcat line 1 (timeline.py's base). Reads hakuX-perf gfps=,
hakuX-phase, hakuX-cpu, xemu-surf, xemu-work, [tlb68], [rr425w], [sdcall],
[lock474], [idlehalt] and hakuX-stall pipe[. Each row is the median over the
span's lines of that tag, with n and the first and last logcat line number.
"""
import os
import re
import statistics
import sys
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\): (.*)$")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


FIELDS = {
    "gfps": (r"^gfps=", [("fps", r"gfps=(\d+)"), ("G", r"G:([\d.]+)"),
                          ("Gmax", r"G:[\d.]+\([\d.]+-([\d.]+)\)"),
                          ("Vpf", r"Vpf:([\d.]+)"), ("Ri", r"Ri:([\d.]+)")]),
    "phase": (r"^Surf:", [("Surf", r"Surf:([\d.]+)"), ("Tex", r"Tex:([\d.]+)"),
                           ("TxH", r"TxH:([\d.]+)"), ("Shd", r"Shd:([\d.]+)"),
                           ("Draw", r"Draw:([\d.]+)"), ("Pipe", r"Pipe:([\d.]+)"),
                           ("Fin", r"Fin:([\d.]+)"), ("Sub", r"Sub:([\d.]+)"),
                           ("Fen", r"Fen:([\d.]+)"), ("Flip", r"Flip:([\d.]+)"),
                           ("Idle", r"Idle:([\d.]+)"), ("Tot", r"Tot:([\d.]+)"),
                           ("GPU", r"GPU:([\d.]+)"), ("GPU.R", r"GPU:[\d.]+\(R:([\d.]+)"),
                           ("GPU.X", r" X:([\d.]+)")]),
    "cpu": (r"^CPU:", [("Push", r"Push:([\d.]+)"), ("Pull", r"Pull:([\d.]+)"),
                        ("Lw", r"Lw:([\d.]+)")]),
    "surf": (r"^Srf:", [("dl_ms", r" dl:([\d.]+)"), ("upl_ms", r" upl:([\d.]+)"),
                         ("n_dl", r"#dl:(\d+)"), ("n_upl", r"#upl:(\d+)")]),
    "work": (r"^BE:", [("draws", r"^BE:(\d+)"), ("PGen", r"PGen:(\d+)"),
                        ("SGen", r"SGen:(\d+)")]),
    "tlb68": (r"^\[tlb68\]", [("dt", r"dt=(\d+)"), ("cpu", r"cpu=(\d+)"),
                               ("rdus", r"rdus=(\d+)"), ("rdous", r"rdous=(\d+)")]),
    "rr425w": (r"^\[rr425w\]", [("idle_us", r"idle_us=(\d+)"),
                                 ("busy_us", r"busy_us=(\d+)")]),
    "sdcall": (r"^\[sdcall\]", [("su_deferred", r"su_deferred=(\d+)"),
                                 ("dl", r"/dl(\d+)/")]),
    "lock474": (r"^\[lock474\]", [("rd_wait_ms", r"rd_wait_ms=([\d.]+)"),
                                   ("wr_wait_ms", r"wr_wait_ms=([\d.]+)"),
                                   ("flip_op_ms", r"flip_op_ms=([\d.]+)")]),
    "idlehalt": (r"^\[idlehalt\]", [("on", r" on=(\d+)"), ("halts", r"halts=(\d+)")]),
    "pipe": (r"^pipe\[", [("ev", r"pipe\[ev(\d+)"), ("pend", r"pend(\d+)")]),
}


def main():
    rid, frm, to = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    rdir = f"{D}/results/{rid}"
    t0 = None
    got = {k: {f: [] for f, _ in v[1]} for k, v in FIELDS.items()}
    lines = {k: [] for k in FIELDS}
    for n, line in enumerate(open(f"{rdir}/logcat.txt", errors="replace"), 1):
        m = TS.match(line)
        if not m:
            continue
        t = ts(m.group(1))
        if t0 is None:
            t0 = t
        if not frm <= t - t0 <= to:
            continue
        msg = m.group(3)
        for k, (head, fields) in FIELDS.items():
            if re.match(head, msg):
                lines[k].append(n)
                for f, pat in fields:
                    mm = re.search(pat, msg)
                    if mm:
                        got[k][f].append(float(mm.group(1)))
    print(f"{rid}  span {frm:.0f}-{to:.0f} s after logcat line 1")
    for k in FIELDS:
        if not lines[k]:
            print(f"{k:9s} no lines")
            continue
        cells = " ".join(f"{f}={statistics.median(v):g}" if v else f"{f}=-"
                         for f, v in got[k].items())
        print(f"{k:9s} n={len(lines[k]):3d} logcat.txt:{lines[k][0]}-{lines[k][-1]}"
              f"  median {cells}")
    tl, rr = got["tlb68"], got["rr425w"]
    if tl["dt"]:
        print(f"derived   vCPU on-CPU {100 * sum(tl['cpu']) / sum(tl['dt']):.1f}% of wall"
              " (sum cpu / sum dt)")
    if rr["idle_us"]:
        i, b = sum(rr["idle_us"]), sum(rr["busy_us"])
        print(f"derived   guest idle loop {100 * i / (i + b):.1f}% of the sampled vCPU"
              " time (sum idle_us / sum of idle_us + busy_us)")
    ph = got["phase"]
    if ph["Tot"]:
        tot, idle = statistics.median(ph["Tot"]), statistics.median(ph["Idle"])
        print(f"derived   renderer busy {tot - idle:.1f} ms/frame (median Tot - median"
              f" Idle), idle {100 * idle / tot:.0f}% of Tot")
    print()


main()
