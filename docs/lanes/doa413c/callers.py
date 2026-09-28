#!/usr/bin/env python3
"""For one thread of a simpleperf record: which emulator (libxemu) frames its
samples run under (#413).

    callers.py <rec.data> <tid> [--top 20]

For every sample, the libxemu frames in its callchain are listed leaf to
root. Prints the share of samples by (a) the innermost libxemu frame (the
emulator function that is running, or that called into the driver / libc),
(b) the outermost one (the thread's entry), and (c) every libxemu frame
anywhere in the chain (inclusive), plus the share of samples whose chain
reaches the Vulkan driver (a frame in vulkan.*.so).
"""
import collections
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from hostsplit import samples  # noqa: E402


def main():
    data, tid = sys.argv[1], sys.argv[2]
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 20
    inner = collections.Counter()
    outer = collections.Counter()
    incl = collections.Counter()
    drv = 0
    n = 0
    for t, _, _, chain in samples(data):
        if t != tid:
            continue
        n += 1
        xs = [s for f, s in chain if "libxemu" in f]
        if any("vulkan" in f for f, _ in chain):
            drv += 1
        inner[xs[0] if xs else "(no libxemu frame)"] += 1
        outer[xs[-1] if xs else "(no libxemu frame)"] += 1
        for s in set(xs):
            incl[s] += 1
    print(f"tid {tid}: {n} samples; chain reaches a vulkan.*.so frame in {drv} ({100 * drv / max(1, n):.1f}%)")
    for name, c in (("innermost libxemu frame", inner), ("outermost libxemu frame", outer),
                    ("libxemu frame anywhere (inclusive)", incl)):
        print(f"\n{name}:")
        for s, k in c.most_common(top):
            print(f"  {k:6d}  {100 * k / max(1, n):5.1f}%  {s[:100]}")


if __name__ == "__main__":
    main()
