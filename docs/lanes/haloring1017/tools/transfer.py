"""The console's output against hakuX's, per draw, in framebuffer units (#939, (a), M7).

usage: transfer.py RENDER.npz REG.npz OVERLAY.png CAL.npz [blur=3] [frame=VIDEO.ppm]

CAL.npz is photocal.py's curve taken on the space background of hakuX's own
video frame at the photo's pose (pattern=v01806.ppm, f504.3; M5 put the photo
at f507), so it has data at every value the hull reaches (fb 0.08 to 0.33,
where the overlay calibration had none). Each photo pixel is read back to fb
units through the L curve (per pixel, not the mean, since the curve bends).

For the hull (n5) and the band (n4) separately, on each draw's blurred core:
  - the console's mean and median in fb units, hakuX's render (hullsw.py's
    final), and hakuX's video frame (if given) on the same pixels;
  - the console's value binned by hakuX's value: a gain (console = g x hakuX)
    keeps the ratio flat across bins; an added term (console = hakuX + b)
    shrinks it toward 1 as hakuX's value rises; a lerp toward white
    (console = hakuX + k (1 - hakuX)) shrinks it faster;
  - the least-squares fit of console = g x hakuX + b on the binned medians.
"""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
cal = np.load(calf)
con_ph = np.load(regf)["warped"] @ LUM
con = np.interp(con_ph, cal["ph_L"], cal["fb_L"])
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def ppm_l(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    return (np.frombuffer(parts[3][:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(np.float64) / 255) @ LUM


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
lid = R["lid"]
hx = np.nan_to_num(R["final"]) @ LUM
vid = ppm_l(opt["frame"]) if "frame" in opt else None
print(f"curve {calf}: fb {np.round(cal['fb_L'], 2)}")
print(f"                ph {np.round(cal['ph_L'], 2)}")
for name, L in (("hull n5", 1), ("band n4", 0)):
    full = (lid == L) & base
    den = boxblur(full.astype(float), BL)
    core = full & (den > 0.5)

    def sm(img):
        return (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[core]

    c, h = sm(con), sm(hx)
    line = f"{name}: core {core.sum()} px; console fb mean {c.mean():.3f} median {np.median(c):.3f}; " \
           f"hakuX render mean {h.mean():.3f} median {np.median(h):.3f}"
    if vid is not None:
        v = sm(vid)
        line += f"; hakuX video mean {v.mean():.3f} median {np.median(v):.3f}"
    print(line)
    qs = np.quantile(h, np.linspace(0, 1, 9))
    xs, ys = [], []
    print("   hakuX bin          n     hakuX med  console med  ratio  console - hakuX")
    for a, b in zip(qs[:-1], qs[1:]):
        s = (h >= a) & (h <= b)
        hm, cm = np.median(h[s]), np.median(c[s])
        xs.append(hm)
        ys.append(cm)
        print(f"   {a:.3f}-{b:.3f}  {s.sum():7d}    {hm:.3f}      {cm:.3f}      {cm / max(hm, 1e-6):5.2f}  {cm - hm:+.3f}")
    g, b0 = np.polyfit(xs, ys, 1)
    print(f"   fit console = {g:.2f} x hakuX {b0:+.3f}; Pearson r per pixel {np.corrcoef(c, h)[0, 1]:+.3f}")
