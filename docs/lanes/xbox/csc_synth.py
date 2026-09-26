"""Synthetic captures for csc_score.py mutation tests.

    csc_synth.py <out root> '<world json>'

Renders every test of the Color space conversion suite under a planted
model (the world's switches), so each csc_score.py leg can be shown to fail
when its model is wrong. csc-run.md lists the eight worlds and outcomes.
"""
import math, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csc_score as S

W, H = 640, 480

def blank():
    a = np.zeros((H, W, 4), np.uint8); a[..., 3] = 255; return a

def conv_fn(world, stage):
    if world.get("no_csc") or (stage in world.get("unconverted_stages", ())):
        return None
    kr = world.get("kr", 128)
    if world.get("swap"):
        return lambda r, g, b: S.csc(r, b, g, kr)
    return lambda r, g, b: S.csc(r, g, b, kr)

def palette_img(variant, fn, shift=0, lum=None):
    a = blank()
    for py in range(72, 456):
        ty = int(math.floor((py + 0.5 - 72) / 1.5))
        for px in range(128, 512):
            tx = int(math.floor((px + 0.5 - 128) / 1.5))
            i, j = min(15, (tx // 16 + shift)), ty // 16
            r, g, b, al = S.texel(i, j, variant)
            if lum:
                r, g, b = lum(r, g, b)
            elif fn:
                r, g, b = fn(r, g, b)
            a[py, px] = (r, g, b, al)
    return a

def yuv_img(fmt, world, csc_on):
    a = blank()
    for py in range(72, 456):
        ty = int(math.floor((py + 0.5 - 72) * 256 / 384))
        for px in range(64, 576):
            tx = int(math.floor((px + 0.5 - 64) / 2))
            y0, u, y1, v = S.YUV[(ty // 64) * 8 + tx // 32]
            y = y0 if tx % 2 == 0 else y1
            if csc_on or world.get("yuv_always_decoded"):
                r, g, b = S.csc(y, u, v, world.get("kr", 128)); al = 255
            else:
                r, g, b, al = v, y, u, 255          # hypothetical raw slots
            a[py, px] = (r, g, b, al)
    return a

def bump_img(vertical, delta):
    a = blank()
    for k in range(256):                      # reference: texel k at pixel k
        col = (k, 128, 128, 255)
        if vertical: a[96 + k, 48:304] = col
        else: a[96:352, 48 + k] = col
    for k in range(256):
        t = int(math.floor(64 + (k + 0.5) / 2 + delta))
        col = (t, 128, 128, 255)
        if vertical: a[96 + k, 336:592] = col
        else: a[96:352, 336 + k] = col
    return a

def render(root, world):
    d = os.path.join(root, S.SUITE); os.makedirs(d, exist_ok=True)
    save = lambda name, arr: Image.fromarray(arr, "RGBA").save(os.path.join(d, name + ".png"))
    save("CSC_Palette_Off", palette_img(0, None, shift=world.get("pal_shift", 0)))
    save("CSC_Palette_On", palette_img(0, conv_fn(world, 0)))
    for st, var in (("Tex0", 0), ("Tex1", 1), ("Tex3", 3)):
        save("CSC_Stages_%s_On" % st, palette_img(var, conv_fn(world, var)))
    save("CSC_Stages_Tex1_Off", palette_img(1, None))
    for fmt in ("YUY2", "UYVY"):
        save("CSC_%s_Off" % fmt, yuv_img(fmt, world, False))
        save("CSC_%s_On" % fmt, yuv_img(fmt, world, True))
    save("CSC_BumpS_Off", bump_img(False, world.get("dS_off", -16.0)))
    save("CSC_BumpT_Off", bump_img(True, world.get("dT_off", 16.0)))
    save("CSC_BumpS_On", bump_img(False, world.get("dS_on", -16.0)))
    save("CSC_BumpT_On", bump_img(True, world.get("dT_on", 16.0)))
    L = 160 / 255
    tr = lambda r, g, b: (math.floor(r * L), math.floor(g * L), math.floor(b * L))
    save("CSC_Lum_Off", palette_img(0, None, lum=tr))
    f0 = conv_fn(world, 1) or (lambda r, g, b: (r, g, b))
    save("CSC_Lum_On", palette_img(0, None, lum=lambda r, g, b: f0(*tr(r, g, b))))
    for fn in world.get("delete", ()):
        os.remove(os.path.join(d, fn + ".png"))

if __name__ == "__main__":
    import json
    render(sys.argv[1], json.loads(sys.argv[2]))
