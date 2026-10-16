"""#939 (b) judge: the Halo menu ring's texture u-offset, c[13].w, per frame, against its own smooth line.

usage: offsetres.py DUMP.jsonl [COUNT,COUNT]   (default 4362,864: the hull draw and the terrain strip)

For each draw (picked by index count, first in its frame), it reads c13.w on every dumped frame and
predicts each frame from its neighbours (median slope over +-6 frames, the frame itself left out).
A frame whose residual is a drop of 0.02 to 0.03 is a glitch frame: the Nova's truncating FIST
(NOTES.md "(b) root cause"); on the hull it is exactly -7/255, on the terrain strip -0.0255..-0.0275.
Any other residual over 0.002 is listed as an anomaly.
Run 11 (truncating FIST, frames 0..599): hull 9 glitch frames, terrain strip 76. Correct rounding: 0.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdread as g  # noqa: E402

GLITCH = -7.0 / 255.0
TOL = 0.002
HALF = 6


def series(draws, count):
    want = set(d["f"] for d in draws if d["count"] == count)
    st = g.replay(draws, want)
    out = {}
    for d in draws:
        if d["count"] == count and d["f"] not in out:
            out[d["f"]] = g.f32(st[(d["f"], d["n"])]["c"][13 * 4 + 3])
    return out


def wrap(r):
    return ((r + 0.5) % 1.0) - 0.5


def judge(vals):
    fs = sorted(vals)
    glitch, anomaly = [], []
    for k, f in enumerate(fs):
        nb = [fs[j] for j in range(max(0, k - HALF), min(len(fs), k + HALF + 1)) if j != k]
        if len(nb) < 4:
            continue
        slopes = [wrap(vals[b] - vals[a]) / (b - a) for a, b in zip(nb, nb[1:])]
        s = statistics.median(slopes)
        pred = statistics.median([vals[j] + s * (f - j) for j in nb])
        r = wrap(vals[f] - pred)
        if -0.03 < r < -0.02:
            glitch.append((f, vals[f], r))
        elif abs(r) > TOL:
            anomaly.append((f, vals[f], r))
    return fs, glitch, anomaly


def main():
    dump = sys.argv[1]
    counts = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "4362,864").split(",")]
    _, draws, _, _, _ = g.load(dump)
    for d in draws:
        for k in ("f", "n", "count"):
            d[k] = int(d[k]) if isinstance(d[k], str) else d[k]
    for c in counts:
        vals = series(draws, c)
        if not vals:
            print(f"count {c}: no draws")
            continue
        fs, glitch, anomaly = judge(vals)
        exact = sum(1 for _, _, r in glitch if abs(r - GLITCH) < 1e-5)
        print(f"count {c}: frames {fs[0]}..{fs[-1]} ({len(fs)}), glitch (drop 0.02-0.03) {len(glitch)} "
              f"(exactly 7/255: {exact}), other {len(anomaly)}")
        for f, v, r in glitch[:20]:
            print(f"  glitch f{f} w={v:.6f} res={r:+.6f}")
        for f, v, r in anomaly[:10]:
            print(f"  other  f{f} w={v:.6f} res={r:+.6f}")


if __name__ == "__main__":
    main()
