"""c13.w of the band (n4) and the hull (n5) over every frame of a gd dump (#939, M1/M2).

usage: c13series.py DUMP.jsonl

Per-frame steps of each scroll (mean, sd, range), the ratio of the hull's step
to the band's, and the least-squares line hull = c + k * band with its
residual. On a build where the guest ticks once per frame the steps have sd 0
and the line is exact; a frame that takes two ticks shows as a double step.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

S, draws, frames, skips, sh = g.load(sys.argv[1])
want = {}
for d in draws:
    if d.get("kind") == "inline_elements" and int(d.get("count")) in (864, 4362):
        want[(int(d["f"]), int(d["n"]))] = int(d["count"])
st = g.replay(draws, set(f for f, n in want))
w = {864: {}, 4362: {}}
for (f, n), cnt in want.items():
    w[cnt][f] = g.f32(st[(f, n)]["c"][13 * 4 + 3])
fs = sorted(set(w[864]) & set(w[4362]))
a = np.array([w[864][f] for f in fs])
b = np.array([w[4362][f] for f in fs])
F = np.array(fs)
print("frames", F[0], F[-1], len(F))
da, db = np.diff(a), np.diff(b)
print("n4 per-frame step: mean %.7f sd %.7f min %.7f max %.7f" % (da.mean(), da.std(), da.min(), da.max()))
print("n5 per-frame step: mean %.7f sd %.7f min %.7f max %.7f" % (db.mean(), db.std(), db.min(), db.max()))
ok = (np.abs(db) > 1e-9)
print("ratio n5/n4 step: median %.4f, p10 %.4f p90 %.4f" % (np.median(db[ok] / da[ok]), np.percentile(db[ok] / da[ok], 10),
                                                           np.percentile(db[ok] / da[ok], 90)))
k, c0 = np.polyfit(a, b, 1)
r = b - (c0 + k * a)
print("linear b = %.5f + %.4f a, residual rms %.6f max %.6f" % (c0, k, np.sqrt(np.mean(r ** 2)), np.abs(r).max()))
for i in range(0, len(F), max(1, len(F) // 15)):
    print(F[i], "%.6f %.6f" % (a[i], b[i]), "res %+.6f" % r[i])
