"""R3 by pattern and by level: a non-zero v4.z (#939, (a), M6).

usage: floorfit.py DUMP.jsonl RAM.bin FRAME REG.npz OVERLAY.png CAL.npz [ks=0,0.05,0.1,0.2,0.3,0.5] [blur=3]

The ring's VP reads v4.z twice: as oD0.w (the final combiner's lerp toward
white) and as the floor of both lighting max()es. `n4` and `n5` feed v4 as a
2-component attribute, so v4.z is the missing-component default (0 in hakuX).
For each k the frame is rendered by hullsw.py with v4.z = k, and against the
console photo at FRAME's pose (M5):
  - rank r of the luminance on the hull (all, upper, lower) and the band. The
    lerp is a constant affine map, so the rank moves only by the floor;
  - mean luminance per region: the render with the lerp (hardware, if v4.z = k
    reaches both uses), the render's r0 (the floor alone), and the console read
    back to framebuffer units through CAL.npz's L curve (photocal.py).
Prints n4's and n5's vertex array records first, so the premise (v4 has two
components on both draws) is read from the dump, not assumed.
"""
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, frame, regf, ovf, calf = sys.argv[1:7]
frame = int(frame)
opt = dict(a.split("=", 1) for a in sys.argv[7:])
KS = [float(k) for k in opt.get("ks", "0,0.05,0.1,0.2,0.3,0.5").split(",")]
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
ram = open(ramf, "rb").read()
loaded = hs.g.load(dump)
for d in loaded[1]:
    if int(d["f"]) == frame and int(d["count"]) in hs.NAMES:
        print(f"{hs.NAMES[int(d['count'])]} vertex arrays [slot, addr, ?, stride, type, size, ?]: "
              + " ".join(str(v) for v in d.get("vr", [])))
con = np.load(regf)["warped"] @ LUM
cal = np.load(calf)
fbL, phL = cal["fb_L"], cal["ph_L"]
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


def rank(x):
    r = np.empty(len(x))
    r[np.argsort(x, kind="stable")] = np.arange(len(x))
    return r


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
yy = np.arange(hs.H)[:, None]
masks = None
print(f"f{frame}, blur {BL}; console in fb units through CAL's L curve")
print("k     region       px     rank r   render(lerp)  r0(floor only)  console photo  console fb")
for k in KS:
    t = time.time()
    R = hs.render(dump, ram, frame, v4z=k, loaded=loaded)
    if masks is None:
        base = ~ovm
        base[452:, :] = False
        base[:, :15] = False
        base[:30, :70] = False
        lid = R["lid"]
        masks = {"hull all": (lid == 1) & base, "hull upper": (lid == 1) & base & (yy < 300),
                 "hull lower": (lid == 1) & base & (yy >= 300), "band": (lid == 0) & base}
        cs = {}
        for name, m in masks.items():
            den = boxblur(m.astype(float), BL)
            cs[name] = (m & (den > 0.5), den)
    fin = np.nan_to_num(R["final"]) @ LUM
    r0 = (fin - k) / (1 - k) if k < 1 else fin
    for name, (m, den) in cs.items():
        full = masks[name]
        sm = lambda img: (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[m]  # noqa: E731
        rr = np.corrcoef(rank(sm(fin)), rank(sm(con)))[0, 1]
        cp = con[full].mean()
        print(f"{k:4.2f}  {name:11s} {full.sum():6d}   {rr:+.3f}    {fin[full].mean():.3f}         {r0[full].mean():.3f}"
              f"           {cp:.3f}          {np.interp(cp, phL, fbL):.3f}", flush=True)
    print(f"      ({time.time() - t:.0f} s)", flush=True)
