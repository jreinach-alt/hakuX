#!/usr/bin/env python3
"""Map each capture's output time to content position in a reference capture, by bit-exact 32-frame windows.

Usage: content_align.py <ref_result_dir> <result_dir> [...]
For each run: content windows (loud, not a lag-2400 replay) every 0.25 s, matched to their EARLIEST
occurrence in the reference. Prints the output-time -> reference-time map and its slope per 20 s.
A slope != 1 means the same content takes a different time to play out (the game produced it slower/faster).
"""
import glob, sys
import numpy as np

W, LAG, SR = 32, 2400, 48000


def load(r):
    p = [q for q in glob.glob(r + "/pulled/**/apu_monitor.s16le48k2ch.pcm*", recursive=True) if not q.endswith(".json")]
    x = np.fromfile(sorted(p)[0], dtype="<i2").reshape(-1, 2).astype(np.int64)
    return x


def hashes(x):
    v = ((x[:, 0] + 32768) * 65536 + (x[:, 1] + 32768)).astype(np.uint64)
    Q = np.uint64(0x9E3779B97F4A7C15)
    with np.errstate(over="ignore"):
        pw = np.cumprod(np.full(len(v), Q, dtype=np.uint64))  # Q^1..Q^n
        S = np.concatenate(([np.uint64(0)], np.cumsum(v * pw, dtype=np.uint64)))
        h = (S[W:] - S[:-W])
        # normalise by Q^(i+1) inverse: multiply by inv^(i+1)
        inv = pow(int(Q), -1, 1 << 64)
        ipw = np.cumprod(np.full(len(h), np.uint64(inv), dtype=np.uint64))
        h = h * ipw
    return h


ref = load(sys.argv[1])
rh = hashes(ref)
order = np.argsort(rh, kind="stable")      # stable: equal hashes keep ascending position -> first is earliest
srt = rh[order]
for r in sys.argv[2:]:
    x = load(r)
    h = hashes(x)
    n = len(x)
    loud = np.abs(x).max(axis=1) > 200
    rep = np.zeros(n, bool); rep[LAG:] = np.all(x[LAG:] == x[:-LAG], axis=1)
    pts = []
    for i in range(LAG, n - W, SR // 4):
        # first loud, non-replay window at or after i within 0.25 s
        for j in range(i, min(i + SR // 4, n - W), 37):
            if loud[j:j + W].all() and not rep[j:j + W].any():
                k = np.searchsorted(srt, h[j])
                if k < len(srt) and srt[k] == h[j]:
                    pos = order[k]
                    if np.array_equal(ref[pos:pos + W], x[j:j + W]):
                        pts.append((j / SR, pos / SR))
                break
    pts = np.array(pts)
    print(f"== {r.rsplit('/', 1)[-1]} vs {sys.argv[1].rsplit('/', 1)[-1]}: {len(pts)} matched points")
    if len(pts) < 10:
        continue
    for t0 in range(0, int(n / SR), 20):
        m = (pts[:, 0] >= t0) & (pts[:, 0] < t0 + 20)
        if m.sum() >= 5:
            a, b = np.polyfit(pts[m, 0], pts[m, 1], 1)
            print(f"   out {t0:3d}-{t0+20:3d} s: n={m.sum():3d} ref = {a:.3f}*out + {b:+.2f}  "
                  f"(ref span {pts[m,1].min():.1f}-{pts[m,1].max():.1f})")
