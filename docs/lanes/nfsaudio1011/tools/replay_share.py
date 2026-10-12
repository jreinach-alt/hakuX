#!/usr/bin/env python3
"""Share of non-silent APU output that is a bit-exact copy of the output LAG frames earlier.

Usage: replay_share.py <result_dir> [<result_dir> ...]
Reads pulled/apu_monitor.s16le48k2ch.pcm* and logcat.txt from each dispatch result dir.
"""
import glob, re, sys
import numpy as np

LAGS = (1200, 2048, 2400, 4096, 4800)
MIN_RUN = 16      # frames; shorter equal runs are silence-adjacent coincidences
LOUD = 200        # |sample| threshold for "non-silent"


def runs(mask):
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def share(x, lag, loud):
    n = len(x)
    same = np.zeros(n, bool)
    same[lag:] = np.all(x[lag:] == x[:-lag], axis=1)
    m = same & loud
    s, e = runs(m)
    keep = (e - s) >= MIN_RUN
    out = np.zeros(n, bool)
    for a, b in zip(s[keep], e[keep]):
        out[a:b] = True
    return out, s[keep], e[keep]


for r in sys.argv[1:]:
    pcm = sorted(p for p in glob.glob(r + "/pulled/**/apu_monitor.s16le48k2ch.pcm*", recursive=True)
                 if not p.endswith(".json"))
    if not pcm:
        print(f"{r}: no pcm"); continue
    x = np.concatenate([np.fromfile(p, dtype="<i2") for p in pcm]).reshape(-1, 2).astype(np.int64)
    n = len(x)
    loud = np.abs(x).max(axis=1) > LOUD
    lc = open(r + "/logcat.txt", errors="replace").read()
    buf = re.findall(r"device buf (\d+) B, fifo (\d+) B", lc)
    starve = re.findall(r"= ([\d.]+)% of output", lc)
    print(f"== {r.rsplit('/', 1)[-1]}")
    print(f"   {n/48000:.1f} s, loud {loud.sum()/48000:.1f} s; device buf/fifo {buf[0] if buf else '?'}; "
          f"starve per 30 s: {' '.join(starve[:8])}")
    best = None
    for lag in LAGS:
        m, s, e = share(x, lag, loud)
        frac = m.sum() / max(loud.sum(), 1)
        print(f"   lag {lag:5d}: {m.sum()/48000:6.1f} s replayed = {100*frac:5.1f}% of loud output, {len(s)} runs")
        if best is None or m.sum() > best[1].sum():
            best = (lag, m, s, e)
    lag, m, s, e = best
    if len(s):
        L = e - s
        print(f"   best lag {lag}: run frames p10/p50/p90 {np.percentile(L,10):.0f}/{np.percentile(L,50):.0f}/"
              f"{np.percentile(L,90):.0f}; start mod 32 == 0: {100*np.mean(s % 32 == 0):.0f}%")
        if len(s) > 1:
            print(f"   splice interval p50 {np.median(np.diff(s)):.0f} frames")
    w = 48000 * 10
    print("   per 10 s (loud s / replay %): " + " ".join(
        f"{int(i/48000)}:{loud[i:i+w].sum()/48000:.0f}/{100*m[i:i+w].sum()/max(loud[i:i+w].sum(),1):.0f}"
        for i in range(0, n, w)))
