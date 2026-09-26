"""Price the RTZ vertex-depth model against every DBFF FZn capture on disk.

The change is transferred onto OUR real capture rather than scored as a pure
replay: new = ours_capture + (silicon_model - our_model) on the pixels whose
winner is unchanged, so the label and anything the replay does not model stay
exactly as captured.  Colour captures move only where the depth-test winner
changes; that set is reported as an upper bound.
"""
import math
import os
import sys
from fractions import Fraction as F

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import model  # noqa: E402
import dbff  # noqa: E402

f32 = np.float32
GOLD = dbff.GOLD
RES = "/home/justin/hakux-work/dispatch/results"


def consts(vp):
    za = f32(200.0) / f32(199.0)
    p22 = f32(za * f32(vp))
    c32 = f32(f32(f32(7.0) * p22) - p22)
    return F(float(p22)), F(float(c32))


def make_vz(c22, c32, sil):
    def vz(zw, m):
        if sil:
            p = model.rnd(zw * c22, 'rtz')
            zc = model.rnd(p + c32, 'rtz')
            w = model.rnd(zw + 7, 'rtz')
            r = model.rnd(1 / w, 'rtz')
            return model.rnd(zc * r, 'rtz')
        # ours on the GPU: RNE products/sums, z * rcp(w) with rcp RNE
        p = model.rnd(zw * c22, 'rne')
        zc = model.rnd(p + c32, 'rne')
        w = model.rnd(zw + 7, 'rne')
        r = model.rnd(1 / w, 'rne')
        return model.rnd(zc * r, 'rne')
    return vz


def render(vz, cutoff):
    dbff.vertex_z = vz
    dbff._cache.clear()
    return dbff.render({'k': 1}, cutoff, tag=True)


def word(path, z16):
    a = np.array(Image.open(path).convert("RGBA"), dtype=np.int64)
    if z16:
        # RGB565 expanded to 8 bits per channel; take the top bits back
        return ((a[:, :, 0] >> 3) << 11) | ((a[:, :, 1] >> 2) << 5) | (a[:, :, 2] >> 3)
    return (a[:, :, 3] << 16) | (a[:, :, 0] << 8) | a[:, :, 1]


def main():
    runs = sys.argv[1:] or ["0-a-now-8e683b3a26-023-Depth_buffer_fixed_function",
                            "z-c866527e03-023-Depth_buffer_fixed_function",
                            "1790359589-xbox-full6743-dry2-2802408"]
    names = sorted(f[:-4] for f in os.listdir(GOLD) if "_FZn_" in f)
    print("%-26s %-3s | %s" % ("capture", "fmt", " | ".join("%-38s" % r[:38] for r in runs)))
    print("%-30s | %s" % ("", " | ".join("%8s %8s %6s %6s %6s" % ("now", "after", "chg", "->g", "away")
                                         for _ in runs)))
    for name in names:
        z16 = name.startswith("z16")
        vp = 65535.0 if z16 else 16777215.0
        c22, c32 = consts(vp)
        cutoff = int(name.split("_M")[1].split("_")[0], 16)
        zo, po = render(make_vz(c22, c32, False), cutoff)
        zs, ps = render(make_vz(c22, c32, True), cutoff)
        winner_chg = po != ps
        val_chg = (zo != zs)
        g_path = os.path.join(GOLD, name + ".png")
        zb = name.endswith("_ZB")
        cells = []
        for r in runs:
            cap = os.path.join(RES, r, "captures1", "Depth_buffer_fixed_function::%s.png" % name)
            if not os.path.exists(cap):
                cells.append("%8s %8s %6s %6s %6s" % ("-", "-", "-", "-", "-"))
                continue
            if zb:
                g = word(g_path, z16)
                o = word(cap, z16)
                new = o + (zs - zo)
                now = int((o != g).sum())
                after = int((new != g).sum())
                chg = int((new != o).sum())
                tog = int(((new == g) & (o != g)).sum())
                away = int(((new != g) & (o == g)).sum())
            else:
                g = np.array(Image.open(g_path).convert("RGB"), dtype=np.int64)
                o = np.array(Image.open(cap).convert("RGB"), dtype=np.int64)
                dif = (g != o).any(axis=2)
                now = int(dif.sum())
                chg = int(winner_chg.sum())
                # a winner change at a pixel where we already match silicon can only go away
                away = int((winner_chg & ~dif).sum())
                tog = int((winner_chg & dif).sum())  # upper bound
                after = now - tog + away
            cells.append("%8d %8d %6d %6d %6d" % (now, after, chg, tog, away))
        print("%-30s | %s" % (name, " | ".join(cells)))


if __name__ == "__main__":
    main()
