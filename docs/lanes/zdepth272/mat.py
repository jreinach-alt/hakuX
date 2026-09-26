"""Replay the XDK default composite matrix z/w columns in float32."""
from fractions import Fraction as F
import numpy as np

f32 = np.float32


def composite(x87=False):
    za = f32(200.0) / f32(199.0)
    vp22 = f32(16777215.0)
    p22 = f32(za * vp22)          # P'22 = za*vp22 + 1*0
    p32 = f32(f32(-za) * vp22)    # P'32 = -za*vp22 + 0
    c22 = p22
    if x87:
        c32 = f32(float(F(7) * F(float(p22)) + F(float(p32))))
    else:
        c32 = f32(f32(f32(7.0) * p22) + p32)
    return dict(za=za, p22=p22, p32=p32, c22=c22, c32=c32, c23=f32(1), c33=f32(7))


if __name__ == "__main__":
    for x87 in (False, True):
        m = composite(x87)
        print("x87" if x87 else "sse", {k: (float(v), hex(np.float32(v).view(np.uint32))) for k, v in m.items()})
        print("  c32 - 6*c22 =", float(F(float(m['c32'])) - 6 * F(float(m['c22']))))
