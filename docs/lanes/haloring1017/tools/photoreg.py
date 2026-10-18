"""Register a console photo of the Halo menu to the 640x480 framebuffer (#939, (a)).

usage: photoreg.py PHOTO.jpg TEMPLATE.ppm OUT.npz [init=x0,y0,sx,sy] [rects=...] [save=PNG]

The menu's 2D overlays (the HALO logo, the menu text) are drawn the same by
the console and by hakuX, wherever the 3D ring is. So the photo is fitted to
a hakuX frame of the same menu (TEMPLATE, 640x480) on the overlay
rectangles only, where the template's edges are strong:

  photo(X, Y) ~ a * template(x, y) + b,  X, Y quadratic in x, y (12 terms),

by Gauss-Newton (forward-additive Lucas-Kanade) from a coarse blur to a fine
one. The photo is read at half its resolution. init is the affine start, in
those half-resolution photo pixels: X = x0 + sx*(x - 248), Y = y0 + sy*(y - 252)
(frame (248, 252) is CAMPAIGN's top left). Writes the warp, the photo
resampled to frame pixels (RGB, 480x640x3, the photo's own values) and the
fit's residual figures. save= writes template | warped photo | |difference|.
"""
import sys

import numpy as np
from PIL import Image

photo_f, tmpl_f, out_f = sys.argv[1], sys.argv[2], sys.argv[3]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
W, H = 640, 480
LUM = np.array([0.299, 0.587, 0.114])


def ppm_rgb(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    return np.frombuffer(parts[3][:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(np.float64) / 255


def blur(img, r):
    """Three passes of a (2r+1) box: close to a Gaussian of sigma ~ r."""
    if r < 1:
        return img
    out = img
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(out.ndim)], mode="edge"),
                          axis=ax)
            n = out.shape[ax]
            hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax)
            lo = np.take(c, np.arange(0, n), axis=ax)
            out = (hi - lo) / (2 * r + 1)
    return out


def sample(img, X, Y):
    hh, ww = img.shape[:2]
    X = np.clip(X, 0, ww - 1.001)
    Y = np.clip(Y, 0, hh - 1.001)
    x0, y0 = np.floor(X).astype(int), np.floor(Y).astype(int)
    fx, fy = X - x0, Y - y0
    if img.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) +
            img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


def basis(x, y):
    u, v = (x - 320) / 320, (y - 240) / 240
    return np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], 1)


ph = Image.open(photo_f).convert("RGB")
ph = ph.resize((ph.width // 2, ph.height // 2), Image.BOX)
P = np.asarray(ph, dtype=np.float64) / 255
PL = P @ LUM
if tmpl_f.endswith(".ppm"):
    T = ppm_rgb(tmpl_f) @ LUM
else:
    # e.g. the per-pixel minimum over a clip's frames: the overlays alone, on black
    T = np.asarray(Image.open(tmpl_f).convert("L"), dtype=np.float64) / 255

x0, y0, sx, sy = (float(v) for v in opt.get("init", "424.5,645,1.59,1.14").split(","))
# start: X = x0 + sx*(x - 248) in basis terms (u = (x-320)/320)
p = np.zeros(6)
q = np.zeros(6)
p[0], p[1] = x0 + sx * (320 - 248), sx * 320
q[0], q[2] = y0 + sy * (240 - 252), sy * 240
if "initfrom" in opt:
    # another photo's fitted warp: a better start where the ring or the planet covers the menu text
    _r = np.load(opt["initfrom"])
    p, q = _r["p"].copy(), _r["q"].copy()

mask = np.zeros((H, W), bool)
for rect in opt.get("rects", "40,100,600,210;215,240,440,392").split(";"):
    a, b, c, d = (int(v) for v in rect.split(","))
    mask[b:d, a:c] = True

levels = [int(v) for v in opt.get("levels", "8,4,2,1").split(",")]
for r in levels:
    Tb = blur(T, r)
    gy, gx = np.gradient(Tb)
    gm = np.hypot(gx, gy)
    m = mask & (gm >= np.quantile(gm[mask], float(opt.get("q", 0.6))))
    ys, xs = np.nonzero(m)
    B = basis(xs + 0.5, ys + 0.5)
    t = Tb[ys, xs]
    # the photo is ~1.6 x 1.1 the frame's scale: blur it by the matching photo radius
    Pb = blur(PL, max(1, int(round(r * 1.4))))
    Gy, Gx = np.gradient(Pb)
    for it in range(30):
        X, Y = B @ p, B @ q
        i = sample(Pb, X, Y)
        ix, iy = sample(Gx, X, Y), sample(Gy, X, Y)
        A1 = np.stack([i, np.ones_like(i)], 1)
        ab, *_ = np.linalg.lstsq(A1, t, rcond=None)
        res = ab[0] * i + ab[1] - t
        J = np.concatenate([ab[0] * ix[:, None] * B, ab[0] * iy[:, None] * B], 1)
        dp, *_ = np.linalg.lstsq(J, -res, rcond=None)
        p += dp[:6]
        q += dp[6:]
        if np.abs(dp).max() < 1e-3:
            break
    X, Y = B @ p, B @ q
    i = sample(Pb, X, Y)
    ncc = np.corrcoef(i, t)[0, 1]
    print(f"blur {r}: px {len(t)} iters {it + 1} ncc {ncc:.3f} "
          f"X = {p.round(2)} Y = {q.round(2)}", flush=True)

gy_, gx_ = np.mgrid[0:H, 0:W]
Bf = basis(gx_.ravel() + 0.5, gy_.ravel() + 0.5)
Xf, Yf = Bf @ p, Bf @ q
warped = sample(P, Xf, Yf).reshape(H, W, 3)
# per-rectangle check at the finest level: ncc of the warped photo with the template
for rect in opt.get("rects", "40,100,600,210;215,240,440,392").split(";"):
    a, b, c, d = (int(v) for v in rect.split(","))
    w_ = warped[b:d, a:c] @ LUM
    t_ = T[b:d, a:c]
    print(f"rect {rect}: ncc {np.corrcoef(w_.ravel(), t_.ravel())[0, 1]:.3f}")
np.savez_compressed(out_f, p=p, q=q, warped=warped)
if "save" in opt:
    wl = warped @ LUM
    lo, hi = np.percentile(wl, [1, 99])
    wn = np.clip((wl - lo) / (hi - lo), 0, 1)
    tn = np.clip((T - np.percentile(T, 1)) / (np.percentile(T, 99) - np.percentile(T, 1)), 0, 1)
    pan = np.concatenate([tn, wn, np.abs(wn - tn)], 1)
    Image.fromarray((pan * 255).astype(np.uint8)).save(opt["save"])
