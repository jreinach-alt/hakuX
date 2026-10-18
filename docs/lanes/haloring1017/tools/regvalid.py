"""Mask the frame pixels a photo registration extrapolated (#939, (a), M7).

usage: regvalid.py PHOTO.jpg REG.npz OVERLAY.png OUT.png [margin=2] [render=RENDER.npz]

photoreg.py samples the (half-resolution) photo at X, Y = quadratic(x, y)
and clamps X, Y to the photo: a frame pixel whose X or Y falls outside the
photo gets the photo's edge pixel, smeared along a line. Photo 5 ends near
frame x 590, so the hull's right edge in every M5-M7 statistic was partly
smear. This writes OUT.png: OVERLAY.png's mask with every frame pixel within
`margin` photo pixels of the photo's edge, or outside it, set to white, so
every tool that drops the overlays (ov > 0.06) drops these too, unchanged.
With render=, prints how much of each ring draw's area the smear covered.
"""
import sys

import numpy as np
from PIL import Image

photo_f, regf, ovf, outf = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
MG = float(opt.get("margin", 2))
W, H = 640, 480
ph = Image.open(photo_f)
ww, hh = ph.width // 2, ph.height // 2
reg = np.load(regf)
p, q = reg["p"], reg["q"]
gy, gx = np.mgrid[0:H, 0:W]
u, v = (gx + 0.5 - 320) / 320, (gy + 0.5 - 240) / 240
B = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], -1)
X, Y = B @ p, B @ q
valid = (X >= MG) & (X <= ww - 1 - MG) & (Y >= MG) & (Y <= hh - 1 - MG)
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255
out = np.where(valid, ov, 1.0)
Image.fromarray((out * 255).astype(np.uint8)).save(outf)
print(f"photo {ww}x{hh} (half res); frame px outside the photo: {(~valid).sum()} "
      f"(x range of valid columns per row 240: {np.nonzero(valid[240])[0].min()}-{np.nonzero(valid[240])[0].max()})")
if "render" in opt:
    lid = np.load(opt["render"])["lid"]
    for name, L in (("band n4", 0), ("hull n5", 1)):
        m = lid == L
        print(f"{name}: {m.sum()} px, of them outside the photo {(m & ~valid).sum()} "
              f"({(m & ~valid).sum() / max(m.sum(), 1):.1%})")
