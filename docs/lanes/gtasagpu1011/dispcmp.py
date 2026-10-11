"""Pair each display image with the consumer frame whose post it matches, then
ask whether the shadow's darkening (that frame's pre->post mask) is in it.
Local: luminance in the mask / luminance in a ring 4-12 px around it, for pre,
post and the display image.  usage: dispcmp.py DUMP"""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdread

path = sys.argv[1]
base = os.path.dirname(path)
_, draws, frames, _ = fdread.load(path)
fr = {x["f"]: x for x in frames}
cons = [d for d in draws if d.get("shader", "").startswith("7f12c419")]

def dil(m, k):
    o = m.copy()
    for _ in range(k):
        n = o.copy()
        n[1:, :] |= o[:-1, :]; n[:-1, :] |= o[1:, :]
        n[:, 1:] |= o[:, :-1]; n[:, :-1] |= o[:, 1:]
        o = n
    return o

def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114

C = {}
for d in cons:
    rbs = {(e["k"], e["s"]): e for e in d.get("rb", [])}
    if ("pre", -1) not in rbs or ("post", -1) not in rbs:
        continue
    pre = np.asarray(fdread.load_rgba(base, rbs[("pre", -1)]).convert("RGB"), dtype=np.float64)
    post = np.asarray(fdread.load_rgba(base, rbs[("post", -1)]).convert("RGB"), dtype=np.float64)
    m = np.abs(post - pre).max(axis=2) > 2
    C[d["f"]] = (d, pre, post, m)

for f in sorted(fr):
    x = fr[f]
    if not x.get("image") or not os.path.exists(os.path.join(base, x["image"])):
        print("img f%-2d: none (img_sync %d)" % (f, x["img_sync"])); continue
    D = np.asarray(Image.open(os.path.join(base, x["image"])).convert("RGB"), dtype=np.float64)
    cand = [(np.abs(D - C[g][2]).mean(), g) for g in (f - 1, f, f + 1) if g in C]
    if not cand:
        print("img f%-2d: no consumer readback near" % f); continue
    e, g = min(cand)
    d, pre, post, m = C[g]
    if m.sum() < 50:
        print("img f%-2d = render f%d: mask %d px, too small" % (f, g, int(m.sum()))); continue
    ring = dil(m, 12) & ~dil(m, 4)
    # ring pixels the draw did not touch and where pre ~ post
    def rel(a):
        L = lum(a)
        return L[m].mean() / L[ring].mean()
    rp, rq, rd = rel(pre), rel(post), rel(D)
    # where on the post->pre scale the display sits: 0 = like pre, 1 = like post
    s = (rd - rp) / (rq - rp) if abs(rq - rp) > 1e-6 else float("nan")
    print("img f%-2d = render f%-2d (mae %.1f) mask %5d ring %5d  mask/ring: pre %.3f post %.3f disp %.3f  -> %.2f of the shadow" % (
        f, g, e, int(m.sum()), int(ring.sum()), rp, rq, rd, s))
