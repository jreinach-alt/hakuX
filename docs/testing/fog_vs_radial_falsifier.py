#!/usr/bin/env python3
"""#41's registered falsifier, run against one dispatcher arm.

    fog_vs_radial_falsifier.py <result-dir>

`fog_radial_band.py` recovers silicon's program-mode RADIAL coordinate from
the goldens. That recovery runs through one inversion -- that in
`FogGen_*-radial` the 8-bit fog factor is readable per pixel as the blue
channel, because the suite's final combiner is `f*(0,0,1) + (1-f)*(1,0,0)`
and clips at neither end -- and an inversion asserted is worth nothing.

This checks it against the one renderer whose input coordinate is known
exactly: ours. The program writes `oFog = (50 - 0.2*i, 0, 0, 0)` over 374
quads, so driving `psh.c`'s fog model with that coordinate predicts our own
mean fog factor per capture, before any arm exists. If those six numbers come
back, the inversion is sound and the bound derived through it stands; if any
lands more than 3.0 off, the forward model is wrong and the band is
retracted rather than patched.

Measured 2026-09-12 on arm `1789264422-fog41-probe`: all six exact to 0.00,
with the drawn region exactly 181,016 px in every capture.
"""
import glob, os, sys
import numpy as np
from PIL import Image

arm = sys.argv[1]
pred = {
    "FogGen_VS-linear-radial":    233.29,
    "FogGen_VS-exp-radial":       181.61,
    "FogGen_VS-exp2-radial":      186.22,
    "FogGen_VS-exp_abs-radial":   160.25,
    "FogGen_VS-exp2_abs-radial":  186.22,
    "FogGen_VS-linear_abs-radial": 227.94,
}
roots = [arm] + sorted(glob.glob(os.path.join(arm, "captures*")))
def find(name):
    for r in roots:
        for n in ("Fog_gen::%s.png" % name, "%s.png" % name):
            p = os.path.join(r, n)
            if os.path.exists(p):
                return p
    return None

print(f"{'capture':<30}{'predicted':>10}{'measured':>10}{'delta':>9}{'px':>9}  verdict")
worst = 0.0
for name, want in pred.items():
    p = find(name)
    if not p:
        print(f"{name:<30}{want:>10.2f}   MISSING"); continue
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (r + b == 255) & (g == 0)
    got = float(b[m].mean()) if m.any() else float("nan")
    d = abs(got - want); worst = max(worst, d)
    print(f"{name:<30}{want:>10.2f}{got:>10.2f}{d:>9.2f}{int(m.sum()):>9}  "
          f"{'ok' if d <= 3.0 else 'OUT OF TOLERANCE'}")
print(f"\nworst deviation {worst:.2f} against a stated tolerance of 3.0")
print("PASS -- the forward model holds" if worst <= 3.0 else
      "FAIL -- the forward model is wrong; the (204.06, 221.81) band is retracted")
