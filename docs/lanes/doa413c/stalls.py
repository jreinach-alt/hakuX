#!/usr/bin/env python3
"""Every pusher gap in a soak logcat: when, how long, the vCPU's load in it,
and the fifoskew line that closes it (#413).

    stalls.py <logcat.txt> [--min 3]

A gap is the time between two consecutive work lines (`fifoskew` or `gfps=`)
of at least --min s. The vCPU column lists the `[tlb68]` cpu= readings (ms of
2000) inside the gap; the closing line's kicks/drain are the pusher's own
account of the gap (drain = kick to pusher done, ns).
"""
import re
import sys

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")


def secs(line):
    m = TS.match(line)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def main():
    path = sys.argv[1]
    mn = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 3.0
    last_t = last_line = None
    cpus = []
    marks = []
    for line in open(path, errors="replace"):
        t = secs(line)
        if t is None:
            continue
        m = re.search(r"\[tlb68\] w=\d+ dt=\d+ cpu=(\d+)", line)
        if m:
            cpus.append(int(m.group(1)))
        m = re.search(r"hakuX-route.*: (prof \S+ \S+)", line)
        if m:
            marks.append(m.group(1))
        if "fifoskew win=" in line or "gfps=" in line:
            if last_t is not None and t - last_t >= mn:
                close = ""
                if "fifoskew" in line:
                    k = re.search(r"kicks=(\d+)", line).group(1)
                    d = re.search(r"drain\(n=(\d+) mean=(\d+) p50=\d+ p90=\d+ p99=\d+ max=(\d+)", line)
                    close = f"kicks {k}, drained {d.group(1)}, mean {int(d.group(2)) / 1e6:.1f} ms, max {int(d.group(3)) / 1e6:.0f} ms"
                else:
                    close = line.split("gfps=")[1].split()[0] + " gfps"
                print(f"{line[6:18]} gap {t - last_t:5.1f} s from {last_line[6:18]}  vCPU {cpus}  "
                      f"close: {close}  {' '.join(marks)}")
            last_t, last_line = t, line
            cpus = []
            marks = []


if __name__ == "__main__":
    main()
