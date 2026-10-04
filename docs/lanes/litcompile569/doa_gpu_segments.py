#!/usr/bin/env python3
"""Gate 4, post hoc: perflog GPU Tot ms per frame by scene, both arms.

    doa_gpu_segments.py <base dir> <fix dir> BASE_SEGS FIX_SEGS

Each *_SEGS is name=HH:MM:SS-HH:MM:SS[,name=...], placed from the route frames.
Reports, per segment, the median and the count of `GPU: Tot` samples closing
in it (one per 60 flips), restricted to windows with no pipeline miss
(dpm == 0). Written after the pair ran, beside the registered E reading.
"""
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shaderfb569"))
import fbwin  # noqa: E402

GPU = re.compile(r"GPU: Tot:([\d.]+) Rnd:([\d.]+)")


def hms(s):
    h, m, x = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(x)


def samples(d):
    lc, _ = fbwin.logcat_of(d)
    lines = open(lc, errors="replace").read().splitlines()
    wins, _, _ = fbwin.parse(lines)
    miss = [(w["t"] - w["dt_ms"] / 1000.0 - 0.5, w["t"] + 0.5) for w in wins if w["dpm"] >= 1]
    out = []
    for ln in lines:
        m = GPU.search(ln)
        t = fbwin.secs(ln)
        if m and t is not None and not any(a <= t <= b for a, b in miss):
            out.append((t, float(m.group(1))))
    return out


def segs(spec):
    r = []
    for part in spec.split(","):
        name, span = part.split("=")
        a, b = span.split("-")
        r.append((name, hms(a), hms(b)))
    return r


def main(bd, fd, bs, fs):
    sb, sf = samples(bd), samples(fd)
    for (name, a, b), (_, c, d) in zip(segs(bs), segs(fs)):
        xb = [v for t, v in sb if a <= t <= b]
        xf = [v for t, v in sf if c <= t <= d]
        if not xb or not xf:
            print("%-10s base n=%d fix n=%d: no samples" % (name, len(xb), len(xf)))
            continue
        mb, mf = statistics.median(xb), statistics.median(xf)
        print("%-10s base %5.1f ms (n=%3d)  fix %5.1f ms (n=%3d)  fix/base %.2f" % (
            name, mb, len(xb), mf, len(xf), mf / mb))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
