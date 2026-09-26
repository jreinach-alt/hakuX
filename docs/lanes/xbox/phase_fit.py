# Fit a constant (s,t) shift of the TEX1 checker to each quad of a golden, i.e.
# measure the bump offset silicon applied, when the offsets are ~constant.
import itertools
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import bump_oracle as bo
from yuv_bump_oracle import csc
test, suite = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "Bump_map")
g = np.asarray(Image.open(f"{bo.GOLD}/{suite}/{test}.png").convert("RGBA")).astype(int)
cols, counts = np.unique(g.reshape(-1, 4), axis=0, return_counts=True)
top2 = [tuple(c) for c, n in sorted(zip(cols.tolist(), counts), key=lambda x: -x[1]) if tuple(c) not in ((32, 32, 32, 254), (255, 255, 255, 0))][:2]
red = bo.checker_red(suite if suite in bo.CHECKER else "Bump_map")
print(test, "classes:", top2)
step = 1.0 / 2048
for ys, xs in itertools.product((0, 1), (0, 1)):
    l, t = bo.ORIGIN_X + xs * bo.STRIDE, bo.ORIGIN_Y + ys * bo.STRIDE
    q = g[t:t + bo.QUAD, l:l + bo.QUAD]
    c1 = (q == np.array(top2[0])).all(axis=2); c0 = (q == np.array(top2[1])).all(axis=2)
    known = c1 | c0
    u = (np.arange(bo.QUAD) + 0.5) / bo.QUAD
    U, V = np.meshgrid(u, u)
    best = (0, 0, 0)
    for a in np.arange(0, 16 / 256, step):
        tx = (np.floor(np.mod(U + a, 1.0) * 256).astype(int)) % 256
        for b in np.arange(0, 16 / 256, step):
            ty = (np.floor(np.mod(V + b, 1.0) * 256).astype(int)) % 256
            r = red[ty, tx]
            agree = max(((r == c1) & known).sum(), ((r == c0) & known).sum())
            if agree > best[0]:
                best = (agree, a, b)
    agree, a, b = best
    print(f"quad G{'s' if ys else 'u'} B{'s' if xs else 'u'}: best constant shift s+={a*256:6.3f} t+={b*256:6.3f} texels (mod 16)  agreement {agree/known.sum()*100:5.1f}% of {known.sum()}")
