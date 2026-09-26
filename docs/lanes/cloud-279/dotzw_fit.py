#!/usr/bin/env python3
"""#279: decode the DotZW golden's depth and score candidate DOT_ZW rules.

TestDotZW (nxdk_pgraph_tests pixel_shader_tests.cpp:453) draws a 256x256
quad at (192,112) with STAGE_2D_PROJECTIVE / DOT_PRODUCT / DOT_ZW, all
stages reading tex0 (water_bump_map, 128x128 A8R8G8B8 linear, texcoord0
0..128), then copies the Z16 buffer under the quad into an R5G6B5 texture
and draws it back over the quad.  So each golden pixel IS the 16-bit depth
word: D = (R>>3)<<11 | (G>>2)<<5 | (B>>3), exactly.

The candidate rule is the one texm3x2depth documents:
    z = texcoord1.xyz . map(tex0.rgb),  w = texcoord2.xyz . map(tex0.rgb)
    depth = z / w
The script scores several readings of "map", filtering, interpolation and
the depth scale against the decoded golden, per pixel and per 8x8 block.

Usage: dotzw_fit.py GOLDEN BUMPMAP [CAPTURE ...]
"""
import sys

import numpy as np
from PIL import Image

X0, Y0, N = 192, 112, 256
TEX = 128

# (texcoord1.xyzw, texcoord2.xyzw) per vertex, in draw order v0..v3
# (TL, TR, BR, BL) -- pixel_shader_tests.cpp:484-496.
ROW0 = np.array([[1000, 1000, 1000], [100, 100, 40000],
                 [10, 100, 1000], [100, 100, 100]], dtype=np.float64)
ROW1 = np.array([[0.1, 0.1, 0.1], [1, 1, 0],
                 [1, 0, 0], [0, 0, 1]], dtype=np.float64)
UV0 = np.array([[0, 0], [TEX, 0], [TEX, TEX], [0, TEX]], dtype=np.float64)
POS = np.array([[0, 0], [N, 0], [N, N], [0, N]], dtype=np.float64)


def decode_depth(path):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int64)
    q = a[Y0:Y0 + N, X0:X0 + N]
    return ((q[..., 0] >> 3) << 11) | ((q[..., 1] >> 2) << 5) | (q[..., 2] >> 3)


def interp(attr, mode, off=0.5):
    """Interpolate a per-vertex attribute over the quad at pixel + off.

    'tri': the quad as two triangles (v0,v1,v2) and (v0,v2,v3), which is
    how NV2A splits QUADS; 'bilinear' as a control.  off=0.5 evaluates at
    pixel centres, off=0 at the pixel's top-left corner."""
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float64) + off
    u, v = xs / N, ys / N
    if mode == "bilinear":
        top = attr[0] * (1 - u)[..., None] + attr[1] * u[..., None]
        bot = attr[3] * (1 - u)[..., None] + attr[2] * u[..., None]
        return top * (1 - v)[..., None] + bot * v[..., None]
    out = np.empty((N, N, attr.shape[1]))
    upper = u >= v  # triangle (v0,v1,v2): TL, TR, BR
    # barycentrics in the unit square
    b1 = u - v
    b2 = v
    b0 = 1 - u
    t1 = attr[0] * b0[..., None] + attr[1] * b1[..., None] + attr[2] * b2[..., None]
    # (v0,v2,v3): TL, BR, BL
    c2 = u
    c3 = v - u
    c0 = 1 - v
    t2 = attr[0] * c0[..., None] + attr[2] * c2[..., None] + attr[3] * c3[..., None]
    out[upper] = t1[upper]
    out[~upper] = t2[~upper]
    return out


def sample(img, uv, filt):
    """Sample an unnormalised-coordinate linear texture, clamp to edge."""
    s, t = uv[..., 0], uv[..., 1]
    if filt == "point":
        i = np.clip(np.floor(s).astype(int), 0, TEX - 1)
        j = np.clip(np.floor(t).astype(int), 0, TEX - 1)
        return img[j, i]
    s, t = s - 0.5, t - 0.5
    i0 = np.floor(s).astype(int)
    j0 = np.floor(t).astype(int)
    fs, ft = (s - i0)[..., None], (t - j0)[..., None]

    def g(j, i):
        return img[np.clip(j, 0, TEX - 1), np.clip(i, 0, TEX - 1)]
    return ((g(j0, i0) * (1 - fs) + g(j0, i0 + 1) * fs) * (1 - ft)
            + (g(j0 + 1, i0) * (1 - fs) + g(j0 + 1, i0 + 1) * fs) * ft)


def predict(bump, filt, dotmap, interp_mode, scale, rnd, off=0.5):
    uv = interp(UV0, interp_mode, off)
    tex = sample(bump, uv, filt)  # 0..255 floats
    if dotmap == "zero_to_one":
        m = tex / 255.0
    elif dotmap == "minus1_to_1_d3d":
        m = (tex - 128.0) / 127.0
    else:
        raise ValueError(dotmap)
    r0 = interp(ROW0, interp_mode, off)
    r1 = interp(ROW1, interp_mode, off)
    z = np.sum(r0 * m, axis=-1)
    w = np.sum(r1 * m, axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = z / w * scale
    d = np.where(np.isfinite(d), d, 65535.0)
    d = np.clip(d, 0, 65535)
    if rnd == "none":
        return d
    return np.floor(d) if rnd == "floor" else np.rint(d)


def block_means(a, b=8):
    return a.reshape(N // b, b, N // b, b).mean(axis=(1, 3))


def score(name, pred, gold):
    diff = pred.astype(np.int64) - gold
    exact = np.mean(diff == 0) * 100
    within1 = np.mean(np.abs(diff) <= 1) * 100
    within64 = np.mean(np.abs(diff) <= 64) * 100
    bm = np.abs(block_means(pred.astype(float)) - block_means(gold.astype(float)))
    print(f"{name:58s} exact {exact:6.2f}%  |d|<=1 {within1:6.2f}%  "
          f"|d|<=64 {within64:6.2f}%  block|d| med {np.median(bm):8.1f} "
          f"p90 {np.percentile(bm, 90):8.1f}")
    return diff


def main():
    gold = decode_depth(sys.argv[1])
    bump = np.asarray(Image.open(sys.argv[2]).convert("RGB"), dtype=np.float64)
    print(f"golden depth: min {gold.min()} max {gold.max()} "
          f"distinct {len(np.unique(gold))}  TL {gold[0,0]} TR {gold[0,-1]} "
          f"BR {gold[-1,-1]} BL {gold[-1,0]}")
    for cap in sys.argv[3:]:
        c = decode_depth(cap)
        print(f"capture {cap}: distinct {len(np.unique(c))} value(s) "
              f"{np.unique(c)[:4]}")
        score("  capture vs golden", c, gold)
    print("\n-- structure: which quantity, map, filter, interpolation, scale")
    for interp_mode in ("tri", "bilinear"):
        for filt in ("point", "linear"):
            for dotmap in ("zero_to_one", "minus1_to_1_d3d"):
                for scale in (1.0, 65535.0):
                    p = predict(bump, filt, dotmap, interp_mode, scale, "rint")
                    score(f"{interp_mode}/{filt}/{dotmap}/x{scale:g}", p, gold)
    print("\n-- refinement of tri/point/zero_to_one/x1: sample offset, rounding")
    best = None
    for off in (0.5, 0.25, 0.0):
        for rnd in ("floor", "rint"):
            p = predict(bump, "point", "zero_to_one", "tri", 1.0, rnd, off)
            name = f"tri/point/zero_to_one/x1/{rnd}/off={off:g}"
            d = score(name, p, gold)
            e = np.mean(d == 0)
            if best is None or e > best[0]:
                best = (e, name, d)
    e, name, d = best
    print(f"\nbest: {name} exact {e*100:.2f}%")
    ad = np.abs(d)
    for lo, hi in ((0, 0), (1, 1), (2, 4), (5, 64), (65, 1024), (1025, 65535)):
        print(f"  |d| in [{lo},{hi}]: {np.sum((ad >= lo) & (ad <= hi))} px")

if __name__ == "__main__":
    main()
