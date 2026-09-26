"""#10 YUV bump captures under the rules measured on silicon 2026-09-26 (csc10;
docs/testing/xbox-csc-2026-09-26.md):
stage-0 YUV unpacks raw (R,G,B,A) = (Y, Cb, Cr, 255); the texture shader reads raw values
(dS from B, dT from G, L from R); the stage output is converted after the luminance multiply
(csc Cb=G, Cr=B, kr 128); bump words land s += w0 dS + w3 dT, t += w1 dS + w2 dT; stage 1
wraps CLAMP_TO_EDGE (TestSuite::Initialize)."""
import itertools, math, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import bump_oracle as bo
from yuv_bump_oracle import csc, harness_yuv_pair

def yuv_raw_planes(colors):
    t = np.zeros((256, 256, 4))
    yy, xx = np.mgrid[0:256, 0:256]
    src = np.zeros((256, 256, 3), int)
    idx = (yy >= 2).astype(int) * 2 + (xx >= 2).astype(int)
    for i, c in enumerate(colors):
        r, g, b, a = bo.rgba8888(c)
        src[idx == i] = (r, g, b)
    for y in range(256):
        for x in range(0, 256, 2):
            Y0, U, Y1, V = harness_yuv_pair(tuple(src[y, x]), tuple(src[y, x + 1]))
            t[y, x] = (Y0, U, V, 255); t[y, x + 1] = (Y1, U, V, 255)
    return t

def render(suite, colors, mat, lum):
    bump = yuv_raw_planes(colors)
    red = bo.checker_red("Bump_map")
    red_t = bo.abgr8888(0xFF0000FE if suite == "Bump_map" else 0x7F0000FE)
    grey_t = bo.abgr8888(0x7F202122)
    w0, w1, w2, w3 = mat
    frame = np.zeros((bo.FB_H, bo.FB_W, 4), np.uint8); cov = np.zeros((bo.FB_H, bo.FB_W), bool)
    for ys, xs in itertools.product((0, 1), (0, 1)):
        left, top = bo.ORIGIN_X + xs * bo.STRIDE, bo.ORIGIN_Y + ys * bo.STRIDE
        if suite == "Bump_map":
            flag = {0: False, 1: bool(ys), 2: bool(xs), 3: False}
        else:  # bump_env_lum_tests.cpp: rsigned = bsigned
            flag = {0: bool(xs), 1: bool(ys), 2: bool(xs), 3: False}
        u = (np.arange(left, left + bo.QUAD) + 0.5 - left) / bo.QUAD
        v = (np.arange(top, top + bo.QUAD) + 0.5 - top) / bo.QUAD
        U, V = np.meshgrid(u, v); bx, by = 0.5 + 2 * U, 0.5 + 2 * V
        dS = bo.read_channel(bump[..., 2], bx, by, flag[2], "hw")
        dT = bo.read_channel(bump[..., 1], bx, by, flag[1], "hw")
        s1 = np.clip(U + w0 * dS + w3 * dT, 0, 1 - 1e-9); t1 = np.clip(V + w1 * dS + w2 * dT, 0, 1 - 1e-9)
        tx = np.floor(s1 * 256).astype(int); ty = np.floor(t1 * 256).astype(int)
        is_red = red[ty, tx]
        if lum:
            Lraw = bo.bilerp(bump[..., 0], bx, by)          # L from R = Y, unsigned read
            scale = 0.7 * np.round(Lraw) / 255.0 + 0.3
        out = np.zeros(is_red.shape + (4,), np.uint8)
        for cell, tex in ((True, red_t), (False, grey_t)):
            m = is_red == cell
            if lum:
                for sc in np.unique(scale[m]):
                    mm = m & (scale == sc)
                    rgb = csc(*(int(math.floor(c * sc)) for c in tex[:3]))
                    out[mm] = bo.blend_over_clear(tuple(rgb) + (tex[3],))
            else:
                out[m] = bo.blend_over_clear(tuple(csc(*tex[:3])) + (tex[3],))
        frame[top:top + bo.QUAD, left:left + bo.QUAD] = out
        cov[top:top + bo.QUAD, left:left + bo.QUAD] = True
    return frame, cov

cases = [("Bump_map", "BumpMap_YUY2_L", [0x007F4500, 0x00804500, 0x007F4500, 0x00804500], (0.3, 0.0, 0.0, 0.5), False),
         ("Bump_map", "BumpMap_UYVY_L", [0x007F4500, 0x00804500, 0x007F4500, 0x00804500], (0.3, 0.0, 0.0, 0.5), False),
         ("Bump_env_lum", "BumpEnvLum_YUY2_L", [0x7F014500, 0x80034500, 0x7F014500, 0x80034500], (0.3, 0.0, 0.0, 5.0), True),
         ("Bump_env_lum", "BumpEnvLum_UYVY_L", [0x7F014500, 0x80034500, 0x7F014500, 0x80034500], (0.3, 0.0, 0.0, 5.0), True)]
for suite, test, colors, mat, lum in cases:
    g = np.asarray(Image.open(f"{bo.GOLD}/{suite}/{test}.png").convert("RGBA")).astype(int)
    f, cov = render(suite, colors, mat, lum)
    white = (g[..., :3] >= 250).all(axis=2); m = cov & ~white
    d = np.abs(g[m] - f[m].astype(int)).max(axis=1)
    print(f"{test:20} measured-rules model: {(d == 0).mean()*100:6.2f}% exact, {(d <= 1).mean()*100:6.2f}% within 1, of {m.sum()} quad px; wrong {int((d > 1).sum())}")
