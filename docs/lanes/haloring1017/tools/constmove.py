"""Which vertex constants move frame to frame, per draw (#939, symptom (c)).

usage: constmove.py DUMP F0 F1 COUNT[,COUNT...]

For each draw picked by its index count (the first such draw in a frame),
over frames F0..F1, print every constant component that is not the same in
all frames: first value, last value, median per-frame step, and how many
frames it changed in. A surface that is meant to turn with the ring carries
a moving constant (the hull's c13.w); a surface with none is drawn static by
the guest itself.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

dump, f0, f1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
counts = [int(x) for x in sys.argv[4].split(",")]
session, draws, frames, skips, shaders = g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
want = set(range(f0, f1 + 1))
st = g.replay(draws, want)

for count in counts:
    series = {}
    for d in draws:
        if d["f"] in want and d["count"] == count and d["f"] not in series:
            series[d["f"]] = st[(d["f"], d["n"])]["c"]
    fs = sorted(series)
    print(f"== count {count}: {len(fs)} frames {fs[0] if fs else '-'}..{fs[-1] if fs else '-'}")
    if len(fs) < 2:
        continue
    width = len(series[fs[0]])
    for i in range(width):
        vals = [g.f32(series[f][i]) for f in fs]
        if all(v == vals[0] for v in vals):
            continue
        steps = [b - a for a, b in zip(vals, vals[1:])]
        moved = sum(1 for s in steps if s != 0)
        reg, comp = divmod(i, 4)
        print(f"  c{reg}.{'xyzw'[comp]}  first {vals[0]:+.6f}  last {vals[-1]:+.6f}"
              f"  median step {statistics.median(steps):+.7f}  moved in {moved}/{len(steps)}")
    c = series[fs[0]]
    print("  c13", " ".join(f"{g.f32(c[13 * 4 + k]):.5f}" for k in range(4)),
          " c14", " ".join(f"{g.f32(c[14 * 4 + k]):.5f}" for k in range(4)),
          " c12", " ".join(f"{g.f32(c[12 * 4 + k]):.4f}" for k in range(4)))
