"""z16 FZy: count F16 words the RTZ model changes, transferred onto our capture."""
import os
import struct
import sys
from fractions import Fraction as F

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import dbff  # noqa: E402
import price  # noqa: E402

f32 = np.float32


def f16word(q):
    """ours: float32 of the value, bits; < 2^-6 -> 0; (bits-0x3C000000)>>11."""
    v = max(0.0, float(f32(float(q))))
    b = struct.unpack("I", struct.pack("f", v))[0]
    if b < 0x3C800000:
        return 0
    return min((b - 0x3C000000) >> 11, 0xFFFF)


def render_f16(vz, cutoff_word):
    prims = dbff.primitives()
    z = np.full((480, 640), cutoff_word, dtype=np.int64)
    for kind, x0, x1, y0, y1, za, zb, span in prims:
        a, b = vz(F(float(za)), {}), vz(F(float(zb)), {})
        n = (x1 - x0) if kind == 'x' else (y1 - y0)
        v = np.array([f16word(a + (b - a) * F(k, span)) for k in range(n)], dtype=np.int64)
        v2 = np.broadcast_to(v[None, :] if kind == 'x' else v[:, None], (y1 - y0, x1 - x0))
        sub = z[y0:y1, x0:x1]
        m = v2 < sub
        sub[m] = v2[m]
    return z


if __name__ == "__main__":
    run = sys.argv[1] if len(sys.argv) > 1 else "0-a-now-8e683b3a26-023-Depth_buffer_fixed_function"
    vp = struct.unpack("f", struct.pack("I", 0x43FFF800))[0]
    c22, c32 = price.consts(vp)
    for name in sorted(f[:-4] for f in os.listdir(price.GOLD) if f.startswith("z16") and "_FZy_" in f):
        cutoff = int(name.split("_M")[1].split("_")[0], 16)
        zo = render_f16(price.make_vz(c22, c32, False), cutoff)
        zs = render_f16(price.make_vz(c22, c32, True), cutoff)
        chg = zo != zs
        line = "%-24s words changed %5d" % (name, chg.sum())
        if name.endswith("_ZB"):
            g = price.word(os.path.join(price.GOLD, name + ".png"), True)
            o = price.word(os.path.join(price.RES, run, "captures1",
                                        "Depth_buffer_fixed_function::%s.png" % name), True)
            new = np.where(chg, o + (zs - zo), o)
            line += "  now %5d after %5d  ->g %4d away %4d  (replay-ours vs capture exact %d/%d)" % (
                (o != g).sum(), (new != g).sum(), ((new == g) & (o != g)).sum(),
                ((new != g) & (o == g)).sum(), (zo == o).sum(), o.size)
        print(line)
