#!/usr/bin/env python3
"""#569: gfps, GPU Tot ms and the [uber569] counters over time, from `mark play`.

    doa_series.py <label>=<result dir> ... [--bin 30]

Reads each arm's logcat.txt with gpljudge's patterns and prints one row per
bin after the play mark: median gfps, median GPU Tot ms, and the last
[uber569] links and swapped counts seen by the end of the bin. It says how
long the ladder's cost lasts, which the play-span median in uberjudge.py
cannot.
"""
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "gpl569"))
import gpljudge  # noqa: E402

KV = re.compile(r"(\w+)=(\S+)")


def series(path, width):
    lines = open(path, errors="replace").read().splitlines()
    play = None
    gpu, gfps, uber = [], [], []
    for line in lines:
        t = gpljudge.secs(line)
        if t is None:
            continue
        m = gpljudge.MARK.search(line)
        if m and m.group(1) == "play" and play is None:
            play = t
        m = gpljudge.GPU.search(line)
        if m:
            gpu.append((t, float(m.group(1))))
        m = gpljudge.GFPS.search(line)
        if m:
            gfps.append((t, int(m.group(1))))
        i = line.find("[uber569]")
        if i >= 0:
            uber.append((t, dict(KV.findall(line[i:]))))
    if play is None:
        return None, []
    end = max([t for t, _ in gfps] + [play])
    rows = []
    b = play
    while b < end:
        g = [v for t, v in gfps if b <= t < b + width]
        u = [v for t, v in gpu if b <= t < b + width]
        last = [v for t, v in uber if t < b + width]
        lk = last[-1].get("links", "") if last else ""
        nx = last[-1].get("next", "") if last else ""
        rows.append((b - play, len(g), statistics.median(g) if g else None,
                     statistics.median(u) if u else None, lk, nx))
        b += width
    return play, rows


def main():
    width = 30.0
    arms = []
    args = sys.argv[1:]
    if "--bin" in args:
        i = args.index("--bin")
        width = float(args[i + 1])
        del args[i:i + 2]
    for a in args:
        label, d = a.split("=", 1)
        arms.append((label, d))
    for label, d in arms:
        play, rows = series(os.path.join(d, "logcat.txt"), width)
        print("==", label, os.path.basename(d.rstrip("/")))
        if play is None:
            print("  no mark play")
            continue
        print("  %6s %3s %6s %8s %7s %s" % ("t+s", "n", "gfps", "GPU ms", "links", "next=built/fail/swapped"))
        for t, n, g, u, lk, nx in rows:
            print("  %6.0f %3d %6s %8s %7s %s" % (
                t, n, "-" if g is None else "%.1f" % g,
                "-" if u is None else "%.1f" % u, lk, nx))


if __name__ == "__main__":
    main()
