"""#315: per-pixel model of the Texture_BRDF wedge against the goldens.

Rasterises draw 0's faces over the golden's wedge pixels (perspective-correct,
nearest depth wins), samples the two spherical-coordinate cube maps the test
generates, and scores candidate BRDF (s, t, r) rules against the golden's
decoded volume texel (x, y, z) = (R, G, B) * 63 / 255.

Usage: python3 brdf_fit.py [golden_dir]
"""
import itertools
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import brdf_geom as G  # noqa: E402

GOLDEN = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/goldens/results/Texture_BRDF"
TESTS = ["BRDF_e0_l0", "BRDF_e0_l1", "BRDF_e1_l0"]


def wedge_mask(img):
    ink = np.abs(img[..., :3].astype(int) - 18).sum(-1) > 0
    ink[:400] = False
    ink[:, :500] = False
    return ink


def face_texel(d):
    """Cube-map texel (theta16, phi16) the test's generator stores for direction d, nearest."""
    ax = np.argmax(np.abs(d))
    m = d[ax]
    x, y, z = d / abs(m)
    if ax == 0:
        sc, tc = (-z, -y) if m > 0 else (z, -y)
    elif ax == 1:
        sc, tc = (x, z) if m > 0 else (x, -z)
    else:
        sc, tc = (x, -y) if m > 0 else (-x, -y)
    i = min(63, max(0, int(np.floor((sc + 1) / 2 * 64))))
    j = min(63, max(0, int(np.floor((tc + 1) / 2 * 64))))
    # regenerate the texel's own direction exactly as texture_brdf_tests.cpp does
    fx = (0.5 + i) * (2 / 64) - 1
    fy = (0.5 + j) * (2 / 64) - 1
    face = ax * 2 + (0 if m > 0 else 1)
    v = {0: (1, -fy, -fx), 1: (-1, -fy, fx), 2: (fx, 1, fy), 3: (fx, -1, -fy),
         4: (fx, -fy, 1), 5: (-fx, -fy, -1)}[face]
    v = np.array(v, float)
    theta = np.arccos(v[2] / np.linalg.norm(v))
    phi = np.arctan2(v[1], v[0])
    if phi < 0:
        phi += 2 * np.pi
    return int(theta / np.pi * 65535 + 0.5), int(phi / (2 * np.pi) * 65535 + 0.5), face


def raster_attrs(px, py, d=G.DRAWS[0]):
    """Return (face_name, tex0 xyz, tex1 xyz, depth) of the nearest face covering pixel centre."""
    clip = G.clip_positions(d)
    best = None
    for name, idx in G.FACES:
        for tri in ([idx[0], idx[1], idx[2]], [idx[0], idx[2], idx[3]]):
            c = clip[tri]
            sx = c[:, 0] / c[:, 3] + G.OFF
            sy = c[:, 1] / c[:, 3] + G.OFF
            den = (sy[1] - sy[2]) * (sx[0] - sx[2]) + (sx[2] - sx[1]) * (sy[0] - sy[2])
            if abs(den) < 1e-12:
                continue
            l0 = ((sy[1] - sy[2]) * (px - sx[2]) + (sx[2] - sx[1]) * (py - sy[2])) / den
            l1 = ((sy[2] - sy[0]) * (px - sx[2]) + (sx[0] - sx[2]) * (py - sy[2])) / den
            lam = np.array([l0, l1, 1 - l0 - l1])
            if (lam < -1e-9).any():
                continue
            iw = lam / c[:, 3]
            pc = iw / iw.sum()
            z = (lam * c[:, 2] / c[:, 3]).sum()
            t0 = pc @ G.PTS[tri]
            lz = np.array([-1.0 if v in G.FRONT else 1.0 for v in tri])
            t1 = np.array([0.1, 0.05, pc @ lz])
            if best is None or z < best[3]:
                best = (name, t0, t1, z)
    return best


def main():
    img = np.array(Image.open(f"{GOLDEN}/{TESTS[0]}.png"))
    for t in TESTS[1:]:
        o = np.array(Image.open(f"{GOLDEN}/{t}.png"))
        assert (wedge_mask(o) == wedge_mask(img)).all() and (o[wedge_mask(o)] == img[wedge_mask(img)]).all(), t
    m = wedge_mask(img)
    ys, xs = np.nonzero(m)
    gold = np.rint(img[m][:, :3].astype(float) * 63 / 255).astype(int)  # (x, y, z) texel index
    rows = []
    faces = {}
    keep = []
    for px, py in zip(xs, ys):
        hit = raster_attrs(px + 0.5, py + 0.5)
        keep.append(hit is not None)
        if hit is None:  # edge-rule ties the model does not reproduce
            continue
        f, t0, t1, _ = hit
        faces[f] = faces.get(f, 0) + 1
        te, pe, fe = face_texel(t0)
        tl, pl, fl = face_texel(t1)
        rows.append((te, pe, tl, pl))
    rows = np.array(rows, float) / 65536.0
    gold = gold[np.array(keep)]
    print("faces covering the wedge:", faces, " modelled pixels:", len(gold), "of", len(xs))
    names = ["theta_e", "phi_e", "theta_l", "phi_l"]
    cand = {n: rows[:, i] for i, n in enumerate(names)}
    cand["phi_e-phi_l"] = (rows[:, 1] - rows[:, 3]) % 1.0
    cand["phi_l-phi_e"] = (rows[:, 3] - rows[:, 1]) % 1.0
    cand["phi_e+phi_l"] = (rows[:, 1] + rows[:, 3]) % 1.0
    for ch, cname in enumerate("xyz"):
        print(f"volume {cname} (golden idx {sorted(set(gold[:, ch]))}):")
        for n, v in cand.items():
            idx = np.floor(v * 64).astype(int) % 64
            print(f"   {n:12s} exact {np.mean(idx == gold[:, ch]) * 100:5.1f}%  within1 "
                  f"{np.mean(abs(idx - gold[:, ch]) <= 1) * 100:5.1f}%  range {idx.min()}..{idx.max()}")
    return rows, gold


def exact_sph(d):
    """Unquantised (theta, phi) / full turn of direction d: what a filtered sample tends to."""
    theta = np.arccos(d[2] / np.linalg.norm(d)) / np.pi
    phi = (np.arctan2(d[1], d[0]) / (2 * np.pi)) % 1.0
    return theta, phi


def price(rows, gold):
    """Pixels whose whole texel (x, y, z) the fitted rule reproduces."""
    rule = np.stack([rows[:, 0], rows[:, 2], (rows[:, 3] - rows[:, 1]) % 1.0], 1)
    idx = np.floor(rule * 64).astype(int) % 64
    return int((idx == gold).all(1).sum())


if __name__ == "__main__":
    rows, gold = main()
    print(f"PRICE nearest-texel inputs: {price(rows, gold)} / {len(gold)} wedge px whole-texel exact")
    img = np.array(Image.open(f"{GOLDEN}/{TESTS[0]}.png"))
    m = wedge_mask(img)
    ys, xs = np.nonzero(m)
    cont = []
    for px, py in zip(xs, ys):
        hit = raster_attrs(px + 0.5, py + 0.5)
        if hit is None:
            continue
        te, pe = exact_sph(hit[1])
        tl, pl = exact_sph(hit[2])
        cont.append((te, pe, tl, pl))
    print(f"PRICE continuous inputs:    {price(np.array(cont), gold)} / {len(gold)} wedge px whole-texel exact")
