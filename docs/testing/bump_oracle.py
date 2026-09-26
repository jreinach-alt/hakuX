#!/usr/bin/env python3
"""An offline oracle for the generic `Bump map` BUMPENVMAP path, for scoring
rival readings of the bump channels against the hardware goldens without a
device.

Everything the path depends on is a literal in the test source, so the
expected framebuffer can be computed on the host. Constants are from
nxdk_pgraph_tests @33e7c6b (src/tests/bump_map_tests.cpp,
pbkitplusplus/src/texture_generator.cpp, src/main.cpp).

The pipeline modelled, per quad:

  u,v      position in the 168x168 quad, from the pixel centre
  bump st  texels 1..3 of a 256x256 bump texture, so the quad straddles the
           x=2 seam where the G byte steps 0x7f -> 0x80 (the "signed sweep")
  dS,dT    bump texture channels, read as two's complement offsets
  ds',dt'  u' = u + m00*dS + m10*dT ;  v' = v + m01*dS + m11*dT
  tex1     (u+ds', v+dt') sampled NEAREST from a 256x256 checkerboard of
           8-texel cells, red 0xFF0000FE / grey 0x7F202122
  output   that texel, SRC_ALPHA/ONE_MINUS_SRC_ALPHA over a 0xFE202020 clear

Validation gates, both met before any rival is believed:
  1. the integer blend reproduces the only two colours the Bump_map goldens
     hold, (254,0,0,255) and (33,32,32,191);
  2. the checker cell period comes out at 168/32 = 5.25 px, matching the 5 px
     median measured by bump_edge_shift.py.

Usage:
  bump_oracle.py --test BumpMap_A8R8G8B8 --rivals
"""
import argparse
import itertools

import numpy as np
from PIL import Image

GOLD = "/home/justin/goldens/results"
FB_W, FB_H = 640, 480
TEX = 256
QUAD, STRIDE = 168, 180
ORIGIN_X, ORIGIN_Y = 146, 66

# bump_map_tests.cpp:76 / bump_env_lum_tests.cpp:74 -- RGBA8888 words, so the
# bytes are R,G,B,A in that order.
BUMP_COLORS = {
    ("Bump_map", False): [0x007F4500, 0x00804500, 0x007F4500, 0x00804500],
    ("Bump_map", True): [0x00457F00, 0x00457F00, 0x00458000, 0x00458000],
}
CHECKER = {"Bump_map": (0xFF0000FE, 0x7F202122)}
CLEAR_ARGB = (0xFE, 0x20, 0x20, 0x20)
# SetBumpEnv(mat00, mat01, mat10, mat11)
BUMPMAT = {("Bump_map", False): (0.3, 0.0, 0.0, 0.5),
           ("Bump_map", True): (0.0, -0.1, 0.3, 0.0)}


def rgba8888(w):
    return ((w >> 24) & 0xFF, (w >> 16) & 0xFF, (w >> 8) & 0xFF, w & 0xFF)


def abgr8888(w):
    return (w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 0xFF)


def bump_texture(suite, cross):
    cols = [rgba8888(c) for c in BUMP_COLORS[(suite, cross)]]
    t = np.zeros((TEX, TEX, 4))
    yy, xx = np.mgrid[0:TEX, 0:TEX]
    idx = (yy >= 2).astype(int) * 2 + (xx >= 2).astype(int)
    for i, c in enumerate(cols):
        t[idx == i] = c
    return t


def checker_red(suite):
    yy, xx = np.mgrid[0:TEX, 0:TEX]
    return ((xx // 8) + (yy // 8)) % 2 == 0


def blend_over_clear(rgba):
    r, g, b, a = rgba
    As = a / 255.0
    ca, cr, cg, cb = CLEAR_ARGB
    return tuple([int(round(s * As + d * (1 - As)))
                  for s, d in ((r, cr), (g, cg), (b, cb))] +
                 [int(round(a * As + ca * (1 - As)))])


def bilerp(plane, x, y):
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    c = lambda v: np.clip(v, 0, TEX - 1)
    x0c, x1c, y0c, y1c = c(x0), c(x0 + 1), c(y0), c(y0 + 1)
    return ((plane[y0c, x0c] * (1 - fx) + plane[y0c, x1c] * fx) * (1 - fy) +
            (plane[y1c, x0c] * (1 - fx) + plane[y1c, x1c] * fx) * fy)


# ------------------------------------------------------------- channel reading
def read_channel(plane, bx, by, flagged, mode):
    """Return the bump offset in roughly [-1,1] for one channel.

    `plane` holds raw bytes 0..255. `flagged` is the TEXFILTER signed bit for
    this channel, which on this hardware controls whether the *sampler* signs
    each texel before filtering -- not whether the offset is signed, which it
    always is. That asymmetry is what psh.c's bump_signed/bump_snorm split
    encodes (derived in 5b380c3); `mode` selects rivals to it.
    """
    if flagged:
        # sampler signs per texel over 127 (-128 clamps to -1), filters, and
        # the stage reads the filtered value back as an 8-bit quantity.
        snorm = np.where(plane >= 128.0, plane - 256.0, plane)
        snorm = np.maximum(snorm / 127.0, -1.0)
        v = bilerp(snorm, bx, by)
        if mode == "no_round":
            return v * 127.0 / 128.0
        return np.round(v * 127.0) / 128.0
    # unflagged: filter the raw bytes, round back to a byte, then read the
    # byte as two's complement.
    b = bilerp(plane, bx, by)
    if mode != "no_round":
        b = np.round(b)
    den = 127.0 if mode == "over127" else 128.0
    return np.where(b >= 128.0, b - 256.0, b) / den


def render(suite, cross, rot, mode, chan):
    bump = bump_texture(suite, cross)
    red = checker_red(suite)
    red_out = blend_over_clear(abgr8888(CHECKER[suite][0]))
    grey_out = blend_over_clear(abgr8888(CHECKER[suite][1]))
    m00, m01, m10, m11 = BUMPMAT[(suite, rot)]
    cS, cT = chan

    frame = np.zeros((FB_H, FB_W, 4), dtype=np.uint8)
    cov = np.zeros((FB_H, FB_W), dtype=bool)
    for ysigned, xsigned in itertools.product((0, 1), (0, 1)):
        left = ORIGIN_X + xsigned * STRIDE
        top = ORIGIN_Y + ysigned * STRIDE
        # bump_map_tests.cpp:167, x_channel 'B' y_channel 'G':
        #   gsigned = ysigned, bsigned = xsigned, rsigned = asigned = false
        flag = {0: False, 1: bool(ysigned), 2: bool(xsigned), 3: False}

        u = (np.arange(left, left + QUAD) + 0.5 - left) / QUAD
        v = (np.arange(top, top + QUAD) + 0.5 - top) / QUAD
        U, V = np.meshgrid(u, v)
        bx, by = 0.5 + 2.0 * U, 0.5 + 2.0 * V

        dS = read_channel(bump[..., cS], bx, by, flag[cS], mode)
        dT = read_channel(bump[..., cT], bx, by, flag[cT], mode)

        s1 = U + m00 * dS + m10 * dT
        t1 = V + m01 * dS + m11 * dT
        tx = (np.floor(np.mod(s1, 1.0) * TEX).astype(int)) % TEX
        ty = (np.floor(np.mod(t1, 1.0) * TEX).astype(int)) % TEX
        is_red = red[ty, tx]
        frame[top:top + QUAD, left:left + QUAD] = np.where(
            is_red[..., None], np.array(red_out, np.uint8),
            np.array(grey_out, np.uint8))
        cov[top:top + QUAD, left:left + QUAD] = True
    return frame, cov


def score(suite, test, mode, chan, cross, rot):
    g = np.asarray(Image.open(f"{GOLD}/{suite}/{test}.png").convert("RGBA"),
                   dtype=np.int16)
    frame, cov = render(suite, cross, rot, mode, chan)
    white = (g[..., :3] >= 250).all(axis=2)
    m = cov & ~white
    d = np.abs(g[m].astype(np.int16) - frame[m].astype(np.int16)).max(axis=1)
    return int((d > 1).sum()), int(m.sum())


MODES = ["hw", "over127", "no_round"]
CHANS = {"dS=B dT=G (psh.c)": (2, 1), "dS=R dT=G (pixel_shader_tests.h)": (0, 1),
         "dS=G dT=B": (1, 2), "dS=G dT=R": (1, 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="BumpMap_A8R8G8B8")
    ap.add_argument("--suite", default="Bump_map")
    ap.add_argument("--rivals", action="store_true")
    a = ap.parse_args()
    cross = a.test.endswith("_B") or "_B_" in a.test
    rot = a.test.endswith("_R90")
    print(f"{a.suite}::{a.test}  cross_on_blue={cross} rotate90={rot}")
    print(f"{'channels':34}{'rounding':>10}{'wrong':>9}{'of':>9}{'%exact':>9}")
    chans = CHANS if a.rivals else {"dS=B dT=G (psh.c)": (2, 1)}
    modes = MODES if a.rivals else ["hw"]
    out = []
    for cname, chan in chans.items():
        for mode in modes:
            w, t = score(a.suite, a.test, mode, chan, cross, rot)
            out.append((w, cname, mode, t))
    for w, cname, mode, t in sorted(out):
        print(f"{cname:34}{mode:>10}{w:9}{t:9}{(1-w/t)*100:8.2f}%")


if __name__ == "__main__":
    main()
