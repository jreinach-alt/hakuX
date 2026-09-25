"""Price #273 offline: model the Texgen-with-texture-matrix SphereMap quad with
a candidate for silicon's R channel, and score the model against the goldens.

The quad sits at one eye depth (all four vertices at eye z = -7 in the frame
whose S/T xemu reproduces exactly), so every per-vertex attribute is affine in
screen space. Texgen is per vertex, so S, T and R come from the corners, and the
texture-matrix product (q included) is interpolated before the per-pixel divide,
as the rasterizer does. Texture: GenerateSurface (red = row*255/128,
green = col*255/256, blue = 255 - red), bilinear, clamp to edge.

usage: python3 price.py GOLDEN_DIR [CAPTURE_DIR]
"""
import sys

import numpy as np
from PIL import Image

X0, X1, Y0, Y1 = 93, 547, 158, 446          # quad bounds in the golden
LEFT, RIGHT, TOP, BOTTOM = -2.75, 2.75, 1.0, -2.5   # CreateGeometry

# Column-vector form of the matrices the test prints (row i = output i).
MATS = {
    "Identity": np.eye(4),
    "Double": np.diag([2, 2, 2, 1.0]),
    "Half": np.diag([0.5, 0.5, 0.5, 1.0]),
    "ShiftHPlus": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0.5, 0, 0, 1.0]]),
    "ShiftHMinus": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [-0.5, 0, 0, 1.0]]),
    "ShiftVPlus": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0.5, 0, 1.0]]),
    "ShiftVMinus": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, -0.5, 0, 1.0]]),
    "RotateX": np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1.0]]),
    "RotateY": np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1.0]]),
    "RotateZ": np.array([[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]]),
    "Arbitrary": np.array([[0.7089392, 0, 0.515, 0], [0, 1.2603364, 0.49, 0],
                           [0, 0, 0, 0], [0, 0, 1.0, 0]]),
}
R_MODES = ("disabled", "reflect_z", "sphere_z")


def vertex(x, y, rmode):
    p = np.array([x, y, -7.0])
    u = p / np.linalg.norm(p)
    n = np.array([0, 0, 1.0])
    r = u - 2 * np.dot(n, u) * n
    inv_m = 1 / (2 * np.linalg.norm(r + [0, 0, 1]))
    s, t = r[0] * inv_m + 0.5, r[1] * inv_m + 0.5
    rr = {"disabled": 0.0,                        # xemu today: texcoord r = 0
          "reflect_z": r[2],                      # candidate: reflection-map z
          "sphere_z": r[2] * inv_m + 0.5}[rmode]  # candidate: sphere formula on z
    return np.array([s, t, rr, 1.0])              # Q disabled, texcoord w = 1


def texture():
    j, i = np.mgrid[0:128, 0:256]
    red = (j * 255.0 / 128).astype(int)
    grn = (i * 255.0 / 256).astype(int)
    return np.stack([red, grn, 255 - red], -1).astype(float)


def sample(tex, s, t):
    h, w = tex.shape[:2]
    x = np.clip(s * w - 0.5, 0, w - 1)
    y = np.clip(t * h - 0.5, 0, h - 1)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    return ((tex[y0, x0] * (1 - fx) + tex[y0, x1] * fx) * (1 - fy)
            + (tex[y1, x0] * (1 - fx) + tex[y1, x1] * fx) * fy)


def render(mat, rmode):
    corners = {"ul": (LEFT, TOP), "ur": (RIGHT, TOP), "ll": (LEFT, BOTTOM), "lr": (RIGHT, BOTTOM)}
    c = {k: mat @ vertex(*xy, rmode) for k, xy in corners.items()}
    ys, xs = np.mgrid[Y0:Y1 + 1, X0:X1 + 1]
    fx = ((xs + 0.5 - X0) / (X1 + 1 - X0))[..., None]
    fy = ((ys + 0.5 - Y0) / (Y1 + 1 - Y0))[..., None]
    v = (c["ul"] * (1 - fx) + c["ur"] * fx) * (1 - fy) + (c["ll"] * (1 - fx) + c["lr"] * fx) * fy
    q = v[..., 3]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.nan_to_num(v[..., 0] / q, nan=0, posinf=1e9, neginf=-1e9)
        t = np.nan_to_num(v[..., 1] / q, nan=0, posinf=1e9, neginf=-1e9)
    return sample(texture(), s, t)


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(float)[Y0:Y1 + 1, X0:X1 + 1]


def score(a, b):
    d = np.abs(a - b).max(-1)
    return (f"max {d.max():5.1f}  p99 {np.percentile(d, 99):5.1f}  "
            f">2: {int((d > 2).sum()):6d}/{d.size}")


def main():
    gdir = sys.argv[1]
    cdir = sys.argv[2] if len(sys.argv) > 2 else None
    for name, mat in MATS.items():
        g = load(f"{gdir}/SphereMap_{name}.png")
        for rmode in R_MODES:
            print(f"{name:9s} model R={rmode:9s} vs golden: {score(np.round(render(mat, rmode)), g)}")
        if cdir:
            cap = load(f"{cdir}/Texgen_with_texture_matrix::SphereMap_{name}.png")
            print(f"{name:9s} xemu capture       vs golden: {score(cap, g)}")


if __name__ == "__main__":
    main()
