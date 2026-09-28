#!/usr/bin/env python3
"""Per-thread read rate and CPU share over windows of a taskio.sh capture (#413).

    taskio.py <taskio.txt> [--top 8]            one row per 2 s: busiest threads, reads
    taskio.py <taskio.txt> --win A B [--win C D] per thread over [A, B) device uptime s
    taskio.py --selftest

taskio.sh writes, once a second, `T <uptime>` then one line per thread:
`<tid> <rchar> <syscr> <read_bytes> | <raw stat>`. CPU is utime+stime ticks
(USER_HZ 100) from the stat line split on its last ')', so a thread name with
spaces or parentheses parses. A thread that appears mid-window is counted
from its first sample; one that vanished is counted to its last.
"""
import collections
import sys

HZ = 100


def parse(lines):
    """[(t, {tid: (name, rchar, syscr, read_bytes, ticks)})]"""
    snaps, cur, t = [], None, None
    for line in lines:
        if line.startswith("T "):
            if cur is not None:
                snaps.append((t, cur))
            t, cur = float(line.split()[1]), {}
            continue
        if cur is None or "|" not in line:
            continue
        io, stat = line.split("|", 1)
        f = io.split()
        if len(f) != 4 or ")" not in stat:
            continue
        name = stat[stat.index("(") + 1:stat.rindex(")")]
        rest = stat[stat.rindex(")") + 1:].split()
        # rest[0] is state (field 3); utime, stime are fields 14, 15
        ticks = int(rest[11]) + int(rest[12])
        cur[int(f[0])] = (name, int(f[1]), int(f[2]), int(f[3]), ticks)
    if cur is not None:
        snaps.append((t, cur))
    return snaps


def window(snaps, a, b):
    inside = [s for s in snaps if a <= s[0] < b]
    if len(inside) < 2:
        return None, {}
    t0, t1 = inside[0][0], inside[-1][0]
    first, last = {}, {}
    for t, d in inside:
        for tid, v in d.items():
            first.setdefault(tid, v)
            last[tid] = v
    out = {}
    for tid, v in last.items():
        u = first[tid]
        out[tid] = (v[0], v[1] - u[1], v[2] - u[2], v[3] - u[3], v[4] - u[4])
    return t1 - t0, out


def table(dt, rows, top):
    print(f"  {'tid':>6} {'thread':16} {'cpu %':>6} {'rchar KB/s':>11} {'syscr/s':>8} {'disk KB/s':>10}")
    tot = [0, 0, 0]
    for tid, (name, rc, sc, rb, tk) in sorted(rows.items(), key=lambda kv: -kv[1][4]):
        tot[0] += rc; tot[1] += sc; tot[2] += rb
        if top:
            top -= 1
            print(f"  {tid:>6} {name:16} {100 * tk / HZ / dt:6.1f} {rc / 1024 / dt:11.1f} {sc / dt:8.1f} {rb / 1024 / dt:10.1f}")
    readers = [(tid, r) for tid, r in rows.items() if r[1] > 0]
    readers.sort(key=lambda kv: -kv[1][1])
    print(f"  process: rchar {tot[0] / 1024 / dt:.1f} KB/s, {tot[1] / dt:.1f} read calls/s, disk {tot[2] / 1024 / dt:.1f} KB/s over {dt:.1f} s")
    for tid, r in readers[:4]:
        print(f"    reader {tid} {r[0]}: {r[1] / 1024 / dt:.1f} KB/s, {r[2] / dt:.1f} calls/s, "
              f"{r[1] / max(1, r[2]) / 1024:.1f} KB per call")


def selftest():
    s = ["P 100",
         "T 10.00", "5 1000 10 0 | 5 (xemu vcpu (0)) R 1 1 1 1 1 1 1 1 1 1 100 50 0 0",
         "6 0 0 0 | 6 (main) S 1 1 1 1 1 1 1 1 1 1 10 10 0 0",
         "T 12.00", "5 3048 12 4096 | 5 (xemu vcpu (0)) R 1 1 1 1 1 1 1 1 1 1 250 100 0 0",
         "6 0 0 0 | 6 (main) S 1 1 1 1 1 1 1 1 1 1 12 10 0 0"]
    snaps = parse(s)
    assert len(snaps) == 2 and snaps[0][1][5][0] == "xemu vcpu (0)", snaps
    dt, rows = window(snaps, 0, 99)
    assert dt == 2.0
    assert rows[5] == ("xemu vcpu (0)", 2048, 2, 4096, 200), rows[5]
    assert rows[6][4] == 2
    print("selftest ok")


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    snaps = parse(open(sys.argv[1], errors="replace").read().splitlines())
    args = sys.argv[2:]
    top = 8
    wins = []
    i = 0
    while i < len(args):
        if args[i] == "--top":
            top = int(args[i + 1]); i += 2
        elif args[i] == "--win":
            wins.append((float(args[i + 1]), float(args[i + 2]))); i += 3
        else:
            sys.exit(f"unknown {args[i]}")
    print(f"{len(snaps)} samples, uptime {snaps[0][0]:.1f}-{snaps[-1][0]:.1f}")
    if wins:
        for a, b in wins:
            dt, rows = window(snaps, a, b)
            print(f"window {a:.1f}-{b:.1f}")
            if dt:
                table(dt, rows, top)
        return
    # timeline: every 2 s, process read rate and the top 3 threads by CPU
    t = snaps[0][0]
    while t < snaps[-1][0]:
        dt, rows = window(snaps, t, t + 2.5)
        if dt:
            rc = sum(r[1] for r in rows.values())
            sc = sum(r[2] for r in rows.values())
            busy = sorted(rows.items(), key=lambda kv: -kv[1][4])[:3]
            b = "  ".join(f"{r[0][:12]}:{100 * r[4] / HZ / dt:.0f}%" for _, r in busy)
            print(f"{t:9.1f}  rchar {rc / 1024 / dt:8.1f} KB/s  {sc / dt:7.1f} calls/s   {b}")
        t += 2


if __name__ == "__main__":
    main()
