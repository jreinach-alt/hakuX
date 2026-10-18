"""The video's clock from the hull's own scroll (#939, M2b).

usage: clockfit.py DUMP.jsonl MAP.tsv BANDFIT_N5.tsv [off=0]

MAP.tsv is a first vidmap.py map (from the dump's wall clock); BANDFIT_N5.tsv
is bandfit.py draws=n5 images=MAP.tsv with a scan wide enough to cover the
first map's error. The hull scrolls by one fixed step per dump frame (run 13:
0.00078085, sd 0 over 600 frames), so the fitted offset d* of a video frame
names the dump frame it shows: f_true = (d* - off - c13.w(0)) / step, off being
the hull's on-screen offset from its c13.w (desktop M2: about 0). This prints
f_true against the first map's frame per video frame, fits
t_video = T0 + K * f_true, and prints line=T0,K for vidmap.py. The hull is the
control: the owner saw it turn on every build. A residual small next to the
first map's error says the clock is right; the band is then fitted on frames
whose pose is right to a frame or two.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

dump, mapf, bf = sys.argv[1:4]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
OFF = float(opt.get("off", 0))
session, draws, frames, skips, shaders = g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
want = {(d["f"], d["n"]) for d in draws if d["kind"] == "inline_elements" and d["count"] == 4362}
st = g.replay(draws, {f for f, n in want})
cw = {f: g.f32(st[(f, n)]["c"][13 * 4 + 3]) for f, n in want}
F = np.array(sorted(cw))
W = np.array([cw[f] for f in F])
step, c0 = np.polyfit(F, W, 1)
print(f"hull c13.w = {c0:.6f} + {step:.8f} * f, max residual {np.abs(W - (c0 + step * F)).max():.2e}")

tv = {}
for ln in open(mapf).read().splitlines()[1:]:
    p = ln.split("\t")
    tv[int(p[0])] = float(p[1])
fn, ft, tt, rr = [], [], [], []
for ln in open(bf).read().splitlines()[1:]:
    p = ln.split("\t")
    if p[1] != "n5" or not p[4]:
        continue
    f = int(p[0])
    ftrue = (float(p[4]) - OFF - c0) / step
    fn.append(f)
    ft.append(ftrue)
    tt.append(tv[f])
    rr.append(float(p[5]))
    print(f"map frame {f:4d}  t_video {tv[f]:7.3f}  d* {float(p[4]):.5f}  r* {float(p[5]):.3f}  "
          f"f_true {ftrue:7.1f}  ({ftrue - f:+6.1f} frames)")
fn, ft, tt = np.array(fn), np.array(ft), np.array(tt)
K, T0 = np.polyfit(ft, tt, 1)
res = (tt - (T0 + K * ft)) / K
print(f"t_video = {T0:.4f} + {K:.6f} * f_true ({1 / K:.3f} frames per second); residual rms {np.sqrt(np.mean(res ** 2)):.2f} "
      f"frames, max {np.abs(res).max():.2f}; first map off by {np.mean(ft - fn):+.1f} frames on average")
print(f"line={T0:.4f},{K:.6f}")
