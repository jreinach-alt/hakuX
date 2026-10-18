"""hullsw.py's render against hakuX's own Turnip video at one frame (#939, M6).

usage: vidratio.py RENDER.npz VIDEO.ppm OUT.png

M4's control was the desktop at f290. This is the same check on run 13's Nova
video at photo 5's pose: per draw, the video's luminance against the
render's, a ratio map (video / render, so a later multiply pass such as `n6`,
which hullsw.py does not draw, shows as a region well below 1), and the
render's luminance r with the video inside each draw.
OUT.png: video | render | ratio (0..2 as black..white, red where the render has no ring).
"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import hullsw as hs  # noqa: E402

R = np.load(sys.argv[1])
v = hs.ppm_rgb(sys.argv[2])
LUM = np.array([0.299, 0.587, 0.114])
vl = v @ LUM
fl = np.nan_to_num(R["final"]) @ LUM
lid = R["lid"]
ratio = vl / np.maximum(fl, 0.02)
for name, L in (("band n4", 0), ("hull n5", 1)):
    m = lid == L
    m[452:, :] = False
    a, b = vl[m], fl[m]
    q = np.percentile(ratio[m], [10, 25, 50, 75, 90])
    print(f"{name}: px {m.sum()} video mean {a.mean():.3f} render mean {b.mean():.3f} r {np.corrcoef(a, b)[0, 1]:.3f} "
          f"ratio p10/25/50/75/90 " + " ".join(f"{x:.2f}" for x in q))
    low = m & (ratio < 0.6)
    print(f"   ratio < 0.6: {low.sum()} px ({low.sum() / m.sum():.0%})")
rr = np.clip(ratio / 2, 0, 1)
rgb = np.repeat(rr[..., None], 3, 2)
rgb[lid < 0] = [0.4, 0, 0]
img = np.concatenate([np.clip(v, 0, 1), np.clip(np.nan_to_num(R["final"]), 0, 1), rgb], 1)[170:470]
Image.fromarray((img * 255).astype(np.uint8)).save(sys.argv[3])
