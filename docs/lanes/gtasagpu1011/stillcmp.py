"""Is the shadow a consumer draws in a dump also in the run's screen stills?
Takes one consumer's pre->post mask (the pixels the projection darkened), and
for each still: box-downscales it to the render size, aligns it to the dump's
display image (integer shift, +-8 px, best mean absolute error outside the
HUD), and computes mean luminance in the mask over a ring 4-12 px around it.
That ratio is set on the pre (no shadow) to post (shadow) scale, as dispcmp.py
does for the dump's own images: 0 = like pre, 1 = like post.
usage: stillcmp.py DUMP F N STILL [STILL ...]"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdread  # noqa: E402
from dispcmp_lib import dil, lum  # noqa: E402

path, F, N = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
stills = sys.argv[4:]
base = os.path.dirname(path)
_, draws, frames, _ = fdread.load(path)
d = next(x for x in draws if x["f"] == F and x["n"] == N)
rbs = {(e["k"], e["s"]): e for e in d.get("rb", [])}
pre = np.asarray(fdread.load_rgba(base, rbs[("pre", -1)]).convert("RGB"), dtype=np.float64)
post = np.asarray(fdread.load_rgba(base, rbs[("post", -1)]).convert("RGB"), dtype=np.float64)
H, W = pre.shape[:2]
m = np.abs(post - pre).max(axis=2) > 2
ring = dil(m, 12) & ~dil(m, 4)
fr = {x["f"]: x for x in frames}
img = fr.get(F, {}).get("image")
ref = (np.asarray(Image.open(os.path.join(base, img)).convert("RGB"), dtype=np.float64)
       if img and os.path.exists(os.path.join(base, img)) else post)
# alignment region: the lower half, left of the HUD, away from the frame edge
ay0, ay1, ax0, ax1 = H // 2, H - 10, 10, W - 10


def rel(a):
    L = lum(a)
    return L[m].mean() / L[ring].mean()


rp, rq = rel(pre), rel(post)
print("f%d n%d: mask %d px, ring %d px; mask/ring pre %.3f post %.3f display %.3f" % (
    F, N, int(m.sum()), int(ring.sum()), rp, rq, rel(ref)))
for s in stills:
    im = Image.open(s).convert("RGB")
    a = np.asarray(im.resize((W, H), Image.BOX), dtype=np.float64)
    best = None
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            sh = np.roll(np.roll(a, dy, axis=0), dx, axis=1)
            e = np.abs(sh[ay0:ay1, ax0:ax1] - ref[ay0:ay1, ax0:ax1]).mean()
            if best is None or e < best[0]:
                best = (e, dy, dx, sh)
    e, dy, dx, sh = best
    r = rel(sh)
    t = (r - rp) / (rq - rp)
    print("%s: shift %+d,%+d mae %.1f  mask/ring %.3f  -> %.2f of the shadow" % (
        os.path.basename(s), dx, dy, e, r, t))
