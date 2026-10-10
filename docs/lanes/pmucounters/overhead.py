#!/usr/bin/env python3
"""Overhead pair for #433: does counting slow the run?

For each logcat, from the route's `mark gameplay` line on:
  - fps per ~2 s pace window (hakuX-pace `f=N ... ms=T`: frames / time),
  - the vCPU thread's on-CPU share per [tlb68] window (cpu= / dt=),
  - vCPU on-CPU ms per frame (sum cpu / frames over the same span).

  overhead.py <logcat> [<logcat> ...] [--after REGEX]

Prints one row per file: windows, median and p10 fps, median busy share,
busy ms per frame. The pair is read by hand against the spread between two
runs of the same arm (pre-registered in NOTES 3d).
"""
import re
import statistics
import sys

PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) .* ms=([\d.]+)")
TLB = re.compile(r"\[tlb68\] w=\d+ dt=(\d+) cpu=(\d+)")


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def read(path, after):
    started = False
    fps, busy = [], []
    prev_f = None
    frames = 0
    cpu_ms = 0
    for line in open(path, errors="replace"):
        if not started:
            started = re.search(after, line) is not None
            continue
        m = PACE.search(line)
        if m:
            f, ms = int(m.group(1)), float(m.group(2))
            if prev_f is not None and ms > 0 and f >= prev_f:
                fps.append((f - prev_f) * 1000.0 / ms)
                frames += f - prev_f
            prev_f = f
            continue
        m = TLB.search(line)
        if m:
            dt, cpu = int(m.group(1)), int(m.group(2))
            if dt > 0:
                busy.append(cpu / dt)
                cpu_ms += cpu
    return fps, busy, frames, cpu_ms


def main(argv):
    after = r"hakuX-route.*mark gameplay"
    files = []
    i = 0
    while i < len(argv):
        if argv[i] == "--after":
            after = argv[i + 1]
            i += 2
            continue
        files.append(argv[i])
        i += 1
    if not files:
        print(__doc__)
        return 2
    print("| file | windows | fps median | fps p10 | fps mean "
          "| vCPU busy median | vCPU ms/frame |")
    print("|---|---|---|---|---|---|---|")
    for p in files:
        fps, busy, frames, cpu_ms = read(p, after)
        if not fps:
            print("| %s | 0 | - | - | - | - | - |" % p)
            continue
        print("| %s | %d | %.2f | %.2f | %.2f | %.3f | %s |" % (
            p, len(fps), statistics.median(fps), pct(fps, 10),
            statistics.mean(fps),
            statistics.median(busy) if busy else float("nan"),
            "%.2f" % (cpu_ms / frames) if frames else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
