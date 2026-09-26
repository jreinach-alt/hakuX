#!/usr/bin/env python3
"""#10 YUV class: score readings of BumpMap_YUY2_L / _UYVY_L against silicon.

Built on bump_oracle.py (docs/testing, geometry validated to the cell period
and the blend colours, 80.4% pixel-exact on BumpMap_A8R8G8B8). Two questions,
scored separately because the geometry is not pixel-exact:

  colours  does the model emit exactly the golden's colour set?
  layout   does its red/grey cell map agree with the golden's as well as the
           stock A8R8G8B8 model agrees with its own golden?

Stage 0: the harness's YUY2/UYVY bytes (pbkitplusplus texture_stage.cpp:178,
float coefficients, truncating casts, chroma from the pair's odd pixel), then
a reading of those bytes into the RGB the bump stage consumes.
TEX1:   the checker texel, optionally through the NV2A YCbCr->RGB converter
        (hakuX util.h convert_ycbcr_to_rgb, red-term rounding constant kr).
"""
import itertools
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import bump_oracle as bo

def clip(x): return 0 if x < 0 else 255 if x > 255 else x

def csc(Y, Cb, Cr, kr=128):
    c, d, e = Y - 16, Cb - 128, Cr - 128
    luma = (298 * c - 96) >> 8
    return (clip(luma + 2 * ((409 * e + kr) >> 9)),
            clip(luma + 2 * ((-50 * d + 254) >> 8) + 2 * ((-104 * e + 248) >> 8) + 1),
            clip(luma + ((516 * d) >> 8)))

def f32(x): return np.float32(x)

def harness_yuv_pair(p0, p1):
    """pbkitplusplus texture_stage.cpp:185-190, float32 then uint8 truncation."""
    R0, G0, B0 = (f32(v) for v in p0)
    R1, G1, B1 = (f32(v) for v in p1)
    Y0 = int(f32(0.257) * R0 + f32(0.504) * G0 + f32(0.098) * B0 + f32(16))
    U = int(-(f32(0.148) * R1) - (f32(0.291) * G1) + (f32(0.439) * B1) + f32(128))
    Y1 = int(f32(0.257) * R1 + f32(0.504) * G1 + f32(0.098) * B1 + f32(16))
    V = int(f32(0.439) * R1 - (f32(0.368) * G1) - (f32(0.071) * B1) + f32(128))
    return Y0, U, Y1, V

def stage0_planes(reading, cross=False):
    """Return a (TEX,TEX,4) float plane of what the bump stage reads."""
    src = bo.bump_texture("Bump_map", cross)          # RGBA bytes per texel
    out = np.zeros_like(src)
    for y in range(bo.TEX):
        for x in range(0, bo.TEX, 2):
            p0 = tuple(int(v) for v in src[y, x, :3])
            p1 = tuple(int(v) for v in src[y, x + 1, :3])
            Y0, U, Y1, V = harness_yuv_pair(p0, p1)
            for k, Yk in ((0, Y0), (1, Y1)):
                if reading == "csc":            # hardware decode, as hakuX does at upload
                    r, g, b = csc(Yk, U, V, 128)
                    out[y, x + k] = (r, g, b, 255)
                elif reading.startswith("raw:"):  # raw bytes into R,G,B in the named order
                    m = {"Y": Yk, "U": U, "V": V}
                    out[y, x + k] = tuple(m[c] for c in reading[4:]) + (255,)
    return out

def render(reading, tex1_csc, cross=False, rot=False, chan=(2, 1), mode="hw"):
    bump = stage0_planes(reading, cross)
    red = bo.checker_red("Bump_map")
    red_t = bo.abgr8888(bo.CHECKER["Bump_map"][0])
    grey_t = bo.abgr8888(bo.CHECKER["Bump_map"][1])
    if tex1_csc:
        red_t = csc(*red_t[:3]) + (red_t[3],)
        grey_t = csc(*grey_t[:3]) + (grey_t[3],)
    red_out, grey_out = bo.blend_over_clear(red_t), bo.blend_over_clear(grey_t)
    m00, m01, m10, m11 = bo.BUMPMAT[("Bump_map", rot)]
    cS, cT = chan
    frame = np.zeros((bo.FB_H, bo.FB_W, 4), dtype=np.uint8)
    cls = np.full((bo.FB_H, bo.FB_W), -1, dtype=np.int8)
    for ysigned, xsigned in itertools.product((0, 1), (0, 1)):
        left = bo.ORIGIN_X + xsigned * bo.STRIDE
        top = bo.ORIGIN_Y + ysigned * bo.STRIDE
        flag = {0: False, 1: bool(ysigned), 2: bool(xsigned), 3: False}
        u = (np.arange(left, left + bo.QUAD) + 0.5 - left) / bo.QUAD
        v = (np.arange(top, top + bo.QUAD) + 0.5 - top) / bo.QUAD
        U, V = np.meshgrid(u, v)
        bx, by = 0.5 + 2.0 * U, 0.5 + 2.0 * V
        dS = bo.read_channel(bump[..., cS], bx, by, flag[cS], mode)
        dT = bo.read_channel(bump[..., cT], bx, by, flag[cT], mode)
        s1 = U + m00 * dS + m10 * dT
        t1 = V + m01 * dS + m11 * dT
        tx = (np.floor(np.mod(s1, 1.0) * bo.TEX).astype(int)) % bo.TEX
        ty = (np.floor(np.mod(t1, 1.0) * bo.TEX).astype(int)) % bo.TEX
        is_red = red[ty, tx]
        frame[top:top + bo.QUAD, left:left + bo.QUAD] = np.where(
            is_red[..., None], np.array(red_out, np.uint8), np.array(grey_out, np.uint8))
        cls[top:top + bo.QUAD, left:left + bo.QUAD] = is_red.astype(np.int8)
    return frame, cls, red_out, grey_out

def golden_classes(test, red_col, grey_col):
    g = np.asarray(Image.open(f"{bo.GOLD}/Bump_map/{test}.png").convert("RGBA"))
    cls = np.full(g.shape[:2], -1, dtype=np.int8)
    cls[(g == np.array(red_col, np.uint8)).all(axis=2)] = 1
    cls[(g == np.array(grey_col, np.uint8)).all(axis=2)] = 0
    return g, cls

def colour_set(test):
    g = np.asarray(Image.open(f"{bo.GOLD}/Bump_map/{test}.png").convert("RGBA"))
    q = np.zeros(g.shape[:2], bool)
    for ys, xs in itertools.product((0, 1), (0, 1)):
        l, t = bo.ORIGIN_X + xs * bo.STRIDE, bo.ORIGIN_Y + ys * bo.STRIDE
        q[t:t + bo.QUAD, l:l + bo.QUAD] = True
    white = (g[..., :3] >= 250).all(axis=2)
    vals, counts = np.unique(g[q & ~white].reshape(-1, 4), axis=0, return_counts=True)
    return sorted(((int(c), tuple(int(x) for x in v)) for v, c in zip(vals, counts)), reverse=True)

def main():
    test = sys.argv[1] if len(sys.argv) > 1 else "BumpMap_YUY2_L"
    print(test, "golden colours in the quads:", colour_set(test)[:4])
    rows = []
    readings = ["csc"] + ["raw:" + "".join(p) for p in itertools.permutations("YUV")]
    for reading in readings:
        for tex1_csc in (False, True):
            frame, mcls, red_out, grey_out = render(reading, tex1_csc)
            g, gcls = golden_classes(test, red_out, grey_out)
            inq = mcls >= 0
            white = (g[..., :3] >= 250).all(axis=2)
            m = inq & ~white
            colour_ok = (gcls[m] >= 0).mean()          # golden pixel is one of the model's two colours
            both = m & (gcls >= 0)
            layout = (gcls[both] == mcls[both]).mean() if both.any() else float("nan")
            d = np.abs(g[m].astype(int) - frame[m].astype(int)).max(axis=1)
            rows.append((int((d > 1).sum()), reading, tex1_csc, colour_ok, layout, int(m.sum()), red_out, grey_out))
    print(f"{'stage-0 reading':12}{'TEX1 csc':>9}{'wrong px':>10}{'of':>8}{'colour-set':>11}{'layout':>8}   model colours")
    for w, reading, t1, cok, lay, tot, ro, go in sorted(rows, key=lambda r: r[0]):
        print(f"{reading:12}{str(t1):>9}{w:10}{tot:8}{cok*100:10.1f}%{lay*100:7.1f}%   red->{ro} grey->{go}")

if __name__ == "__main__":
    main()
