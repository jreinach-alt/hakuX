#!/usr/bin/env python3
"""An offline oracle for BumpMapTests::Test16bit -- R16B16 through the HILO
dot mapping -- for scoring rival readings of `dotmap_hilo_1` against the
hardware goldens without a device.

Everything the path depends on is a literal in the test source, so the
expected framebuffer can be computed on the host.  Constants are from
nxdk_pgraph_tests @33e7c6b (src/tests/bump_map_tests.cpp:211).

The pipeline modelled, per quad (168x168 at (146,66), stride 180):

  U,V      position in the quad, from the pixel centre
  stage 0  STAGE_2D_PROJECTIVE, texcoord0 1/256..3/256, so the quad
           straddles both the x=2 and the y=2 seam of the bump texture and
           the tent filter ramps between them across the middle half
  hilo     dotmap_hilo_1 of that texel -> (hi, lo, 1)
  stage 1  STAGE_DOT_PRODUCT,  texcoord1 = (10, 0, U, 1) -> dot1 = 10*hi + U
  stage 2  STAGE_DOT_ST,       texcoord2 = (0, 15, V, 1) -> dot2 = 15*lo + V
  tex2     (dot1, dot2) sampled NEAREST, CLAMPed, from a 256x256
           checkerboard of 8-texel cells, red 0xFF0000FE / grey 0x7F202122
  output   that texel, SRC_ALPHA/ONE_MINUS_SRC_ALPHA over a 0xFE202020 clear

The bump texture is R16B16: the R16 field is the texel's high half (the A
and R byte positions of the 32-bit word) and B16 the low half (G and B), so
hi comes from R16 and lo from B16.  The test's converter byte-replicates,
so the stored fields are 0x0202, 0xffff, 0x0101, 0x0303 and so on.

DrawRectangles is called with x_channel='G', y_channel='A', which means
GSIGNED = xsigned flags the lo field and ASIGNED = ysigned flags the hi
field -- each 16-bit field takes the sign flag of the byte position holding
its high byte.

Validation gates, both met before any rival is believed:
  1. the integer blend reproduces the only two colours these goldens hold,
     (254,0,0,255) and (33,32,32,191);
  2. modelling psh.c's own shader (`--model byte8 --sign none`) reproduces
     our capture to 2,616 and 1,616 px of 111,496 -- the residual is #38's
     texture-coordinate floor, which this oracle does not model.

Usage:
  bump16_oracle.py --rivals
  bump16_oracle.py --rivals --cap DIR   # score against a capture, not gold
"""
import argparse
import itertools
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures  # noqa: E402

GOLD = "/home/justin/goldens/results"
FB_W, FB_H = 640, 480
TEX = 256
QUAD, STRIDE = 168, 180
ORIGIN_X, ORIGIN_Y = 146, 66
CLEAR_ARGB = (0xFE, 0x20, 0x20, 0x20)

# bump_map_tests.cpp:227 -- RGBA8888 words, so the bytes are R,G,B,A.
BUMP_COLORS = {
    False: [0x02000100, 0x02000300, 0xFF000100, 0xFF000300],
    True: [0x02000300, 0x0200FF00, 0x00000300, 0x0000FF00],
}


def rgba8888(w):
    return ((w >> 24) & 0xFF, (w >> 16) & 0xFF, (w >> 8) & 0xFF, w & 0xFF)


def abgr8888(w):
    return (w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 0xFF)


def blend_over_clear(rgba):
    r, g, b, a = rgba
    a_s = a / 255.0
    ca, cr, cg, cb = CLEAR_ARGB
    return tuple([int(round(s * a_s + d * (1 - a_s)))
                  for s, d in ((r, cr), (g, cg), (b, cb))] +
                 [int(round(a * a_s + ca * (1 - a_s)))])


RED = np.array(blend_over_clear(abgr8888(0xFF0000FE)), np.uint8)
GREY = np.array(blend_over_clear(abgr8888(0x7F202122)), np.uint8)


def fields(cross):
    """The bump texture's two 16-bit fields, as the source bytes."""
    cols = [rgba8888(c) for c in BUMP_COLORS[cross]]
    yy, xx = np.mgrid[0:TEX, 0:TEX]
    idx = (yy >= 2).astype(int) * 2 + (xx >= 2).astype(int)
    hi = np.zeros((TEX, TEX))
    lo = np.zeros((TEX, TEX))
    for i, c in enumerate(cols):
        hi[idx == i] = c[0]   # R -> R16, the texel's high half
        lo[idx == i] = c[2]   # B -> B16, the low half
    return hi, lo


def bilerp(plane, x, y):
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    c = lambda v: np.clip(v, 0, TEX - 1)
    x0c, x1c, y0c, y1c = c(x0), c(x0 + 1), c(y0), c(y0 + 1)
    return ((plane[y0c, x0c] * (1 - fx) + plane[y0c, x1c] * fx) * (1 - fy) +
            (plane[y1c, x0c] * (1 - fx) + plane[y1c, x1c] * fx) * fy)


def read_field(byte_plane, bx, by, flagged, model, sign):
    """Return one HILO field in the dot product's units, 0..1 over 0xffff."""
    v16 = byte_plane * 257.0
    if flagged and sign != "none":
        s = np.where(v16 >= 32768.0, v16 - 65536.0, v16)
        f = bilerp(s, bx, by)
        if sign == "wrap":
            # filtered signed, then read back as an unsigned 16-bit value
            return np.mod(f, 65536.0) / 65535.0
        if sign == "clamp0":
            return np.maximum(f, 0.0) / 65535.0
        if sign == "snorm":
            return f / 32767.0
        raise SystemExit("unknown --sign")
    if model == "byte8":
        # psh.c's `dotmap_hilo_1`, the eight-bit reconstruction: filter,
        # truncate the eight-bit view of each channel to a byte, rebuild
        # hi = b<<8|b.  Right for a four-byte texel, wrong for this one.
        b = np.floor(bilerp(byte_plane, bx, by))
        return (b * 256.0 + b) / 65535.0
    if model == "full16":
        # psh.c's `dotmap_hilo_1_16`: the field read whole off the sampler.
        return bilerp(v16, bx, by) / 65535.0
    raise SystemExit("unknown --model")


def checker(s, t, wrap):
    if wrap == "clamp":
        tx = np.clip(np.floor(s * TEX), 0, TEX - 1).astype(np.int64)
        ty = np.clip(np.floor(t * TEX), 0, TEX - 1).astype(np.int64)
    else:
        tx = np.floor(np.mod(s, 1.0) * TEX).astype(np.int64) % TEX
        ty = np.floor(np.mod(t, 1.0) * TEX).astype(np.int64) % TEX
    return np.where((((tx // 8) + (ty // 8)) % 2 == 0)[..., None], RED, GREY)


def render(cross, model, sign, wrap="clamp"):
    hi_p, lo_p = fields(cross)
    frame = np.zeros((FB_H, FB_W, 4), np.uint8)
    cov = np.zeros((FB_H, FB_W), bool)
    for ysigned, xsigned in itertools.product((0, 1), (0, 1)):
        left = ORIGIN_X + xsigned * STRIDE
        top = ORIGIN_Y + ysigned * STRIDE
        u = (np.arange(QUAD) + 0.5) / QUAD
        U, V = np.meshgrid(u, u)
        bx, by = 0.5 + 2.0 * U, 0.5 + 2.0 * V
        # ASIGNED = ysigned flags the hi field, GSIGNED = xsigned the lo one.
        H = read_field(hi_p, bx, by, bool(ysigned), model, sign)
        L = read_field(lo_p, bx, by, bool(xsigned), model, sign)
        frame[top:top + QUAD, left:left + QUAD] = checker(
            10.0 * H + U, 15.0 * L + V, wrap)
        cov[top:top + QUAD, left:left + QUAD] = True
    return frame, cov


def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), np.int16)


def score(ref_png, cross, model, sign, wrap):
    g = load(ref_png)
    frame, cov = render(cross, model, sign, wrap)
    out = []
    for ysigned, xsigned in itertools.product((0, 1), (0, 1)):
        l = ORIGIN_X + xsigned * STRIDE
        t = ORIGIN_Y + ysigned * STRIDE
        gg = g[t:t + QUAD, l:l + QUAD]
        ff = frame[t:t + QUAD, l:l + QUAD].astype(np.int16)
        white = (gg[..., :3] >= 250).all(axis=2)
        d = (np.abs(gg - ff).max(axis=2) > 1) & ~white
        out.append(int(d.sum()))
    white = (g[..., :3] >= 250).all(axis=2)
    m = cov & ~white
    return out, int(m.sum())


TESTS = (("BumpMap_R16B16", False), ("BumpMap_R16B16_B", True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", default=GOLD)
    ap.add_argument("--cap", help="score against this run's captures instead")
    ap.add_argument("--rivals", action="store_true")
    ap.add_argument("--model", default="full16")
    ap.add_argument("--sign", default="wrap")
    ap.add_argument("--wrap", default="clamp")
    a = ap.parse_args()

    models = ("byte8", "full16") if a.rivals else (a.model,)
    signs = ("none", "wrap", "clamp0", "snorm") if a.rivals else (a.sign,)
    wraps = ("clamp", "repeat") if a.rivals else (a.wrap,)

    for test, cross in TESTS:
        if a.cap:
            ref = captures.find(a.cap, "Bump_map", test)
            if not ref:
                print(f"{test}: MISSING from {a.cap}")
                continue
        else:
            ref = os.path.join(a.goldens, "Bump_map", test + ".png")
        print(f"=== {test}   quads (ys,xs) = (0,0) (0,1) (1,0) (1,1);"
              f" ASIGNED=ys GSIGNED=xs")
        rows = []
        for model in models:
            for sign in signs:
                for wrap in wraps:
                    q, n = score(ref, cross, model, sign, wrap)
                    rows.append((sum(q), model, sign, wrap, q, n))
        for tot, model, sign, wrap, q, n in sorted(rows):
            print(f"  {model:8} sign={sign:7} {wrap:7} "
                  f"{str(q):32} total {tot:7}  of {n}")


if __name__ == "__main__":
    main()
