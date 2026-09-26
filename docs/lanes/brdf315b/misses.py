"""Where the bytes16 model misses the #315 arm capture, and what the corrected
patch (fields reading) predicts at those pixels and at (639, 479).

For each wedge pixel the model misses, search the eye cube texel's 3x3
neighbourhood for the texel whose bytes16 lookup reproduces the capture: that
is the texel the GPU actually sampled. Then price the fields rule on that
texel against the golden: that is what the corrected patch should render
there. Usage: python3 misses.py [fix_capture_dir]
"""
import sys

import numpy as np
from PIL import Image

FIX = (sys.argv[1] if len(sys.argv) > 1 else
       "/home/justin/hakux-work/dispatch/results/1790395945-arms-pshqueue-fix-1882785/captures1")
del sys.argv[1:]
sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/brdf315")
import brdf_fit as F  # noqa: E402


def idx(v):
    return int(np.floor(v * 64)) % 64


def bytes16(te, pe, tl, pl):
    return (idx((te & 255) / 255), idx((tl & 255) / 255), idx(((pl >> 8) - (pe >> 8)) / 255 % 1.0))


def fields(te, pe, tl, pl):
    return (idx(te / 65535), idx(tl / 65535), idx((pl / 65535 - pe / 65535) % 1.0))


def sph(v):
    theta = np.arccos(v[2] / np.linalg.norm(v))
    phi = np.arctan2(v[1], v[0]) % (2 * np.pi)
    return int(theta / np.pi * 65535 + 0.5), int(phi / (2 * np.pi) * 65535 + 0.5)


def neighbours(d):
    """(theta16, phi16) of the 3x3 texels around d's nearest texel on its face."""
    ax = np.argmax(np.abs(d))
    m = d[ax]
    x, y, z = d / abs(m)
    if ax == 0:
        sc, tc = (-z, -y) if m > 0 else (z, -y)
    elif ax == 1:
        sc, tc = (x, z) if m > 0 else (x, -z)
    else:
        sc, tc = (x, -y) if m > 0 else (-x, -y)
    i0 = int(np.floor((sc + 1) / 2 * 64))
    j0 = int(np.floor((tc + 1) / 2 * 64))
    face = ax * 2 + (0 if m > 0 else 1)
    for i in range(max(0, i0 - 1), min(64, i0 + 2)):
        for j in range(max(0, j0 - 1), min(64, j0 + 2)):
            fx = (0.5 + i) * (2 / 64) - 1
            fy = (0.5 + j) * (2 / 64) - 1
            v = {0: (1, -fy, -fx), 1: (-1, -fy, fx), 2: (fx, 1, fy), 3: (fx, -1, -fy),
                 4: (fx, -fy, 1), 5: (-fx, -fy, -1)}[face]
            yield (i - i0, j - j0), sph(np.array(v, float))


def main():
    gold_img = np.array(Image.open(f"{F.GOLDEN}/{F.TESTS[0]}.png").convert("RGBA")).astype(int)
    cap_img = np.array(Image.open(f"{FIX}/Texture_BRDF::{F.TESTS[0]}.png").convert("RGBA")).astype(int)
    m = F.wedge_mask(gold_img)
    ys, xs = np.nonzero(m)
    pred_fields_miss = 0
    unexplained = 0
    for px, py in zip(xs, ys):
        hit = F.raster_attrs(px + 0.5, py + 0.5)
        cap = tuple(int(round(c * 63 / 255)) for c in cap_img[py, px, :3])
        gold = tuple(int(round(c * 63 / 255)) for c in gold_img[py, px, :3])
        if hit is None:
            print(f"({px},{py}) unmodelled edge px: capture {cap} golden {gold}")
            continue
        te, pe, _ = F.face_texel(hit[1])
        tl, pl, _ = F.face_texel(hit[2])
        if (px, py) == (639, 479):
            print(f"(639,479): bytes16 {bytes16(te, pe, tl, pl)} capture {cap}; "
                  f"fields {fields(te, pe, tl, pl)} golden {gold} "
                  f"-> RGB {tuple(v * 255 // 63 for v in fields(te, pe, tl, pl))} vs {tuple(gold_img[py, px, :3])}")
        if bytes16(te, pe, tl, pl) == cap:
            pred_fields_miss += fields(te, pe, tl, pl) != gold
            continue
        found = [(off, t, p) for off, (t, p) in neighbours(hit[1]) if bytes16(t, p, tl, pl) == cap]
        if not found:
            unexplained += 1
            print(f"({px},{py}) miss, no neighbouring eye texel explains capture {cap}")
            continue
        off, t, p = found[0]
        f = fields(t, p, tl, pl)
        pred_fields_miss += f != gold
        print(f"({px},{py}) GPU took eye texel offset {off}: fields -> {f}, golden {gold}, "
              f"{'match' if f == gold else 'MISS'}")
    print(f"corrected patch, predicted misses over modelled px: {pred_fields_miss}; unexplained: {unexplained}")


if __name__ == "__main__":
    main()
