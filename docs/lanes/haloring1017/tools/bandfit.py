"""Does a ring surface turn ON SCREEN? Fit each frame's texture offset from the dumped image (#939, M2).

usage: bandfit.py DUMP.jsonl RAM.bin OUT.tsv [every=N] [px=N] [draws=n4,n5] [images=MAP.tsv]

The ring turns by scrolling texture u (oT0.x = c13.x*u + c13.y*v + c13.w; M1).
The guest's c13.w is in the dump; what reaches the screen is in the dump's image
of the same frame. Per frame and per draw this:

  1. runs the draw's vertex program (the hull's, shared by n4 and n5; from
     x1port1012's swr.py) on the draw's 32-byte records in RAM.bin, with the
     frame's replayed constants, and rasterises n4 and n5 together with a
     z-buffer, so each pixel knows which surface it shows;
  2. takes, for that draw's pixels, the per-pixel texture coordinate WITHOUT
     the scroll: a = c13.x*u + c13.y*v, and b = oT0.y in full;
  3. scans an offset d and correlates the image's luminance with the luminance
     of the draw's stage-0 texture (read from RAM.bin) at (a + d, b);
  4. reports d*, the best offset, beside the dump's c13.w.

A surface that turns on screen has d* - c13.w constant across the frames (the
fit follows the guest's scroll). A static one has d* constant while c13.w moves.
n5, the hull, rotates on every build (the owner, 10-16); it is the control that
says the fit can see a scroll at all. Pixels are the 640x480 framebuffer's.

Assumptions this rests on, each checkable in the output: the strips (n5 at
0x3dc8f8, 1456 indices; n4 is 0..289) are those M1 read; and a draw's detail
is dominated by its stage-0 texture (r* says how well). The cull is the
dump's own state for both draws: SETUPRASTER 0x10400000 is cull enabled, cull
BACK, FRONTFACE clear, which hakuX maps to VK_FRONT_FACE_CLOCKWISE
(draw.c:7309). In y-down screen space Vulkan's a = -1/2 sum(x_i y_i+1 -
x_i+1 y_i), so a clockwise front face is area > 0 in this file's
(xb-xa)(yc-ya)-(xc-xa)(yb-ya), and the back faces culled are area < 0: "neg".
cull4=/cull5= override it; dbg=DIR writes image | surface map | predicted
texture panels per frame.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

dump, ramf, outf = sys.argv[1], sys.argv[2], sys.argv[3]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
EVERY = int(opt.get("every", 3))
NPX = int(opt.get("px", 12000))
WANT = opt.get("draws", "n4,n5").split(",")
ram = open(ramf, "rb").read()
W, H = 640, 480

# draw name -> (index count in the dump, vertex records, nvert, strip, stage-0 texture (off, w, h, levels))
DRAWS = {
    "n4": (864, 0x3d6840, 290, list(range(290)), (0x02ad4000, 2048, 128, 5)),
    "n5": (4362, 0x3cfb80, 870, list(struct.unpack_from("<1456H", ram, 0x3dc8f8)), (0x02b34000, 1024, 512, 9)),
}


# ---------- DXT1 (x1port1012 swr.py) ----------
def c565(c):
    r = ((c >> 11) & 31) * 255 // 31
    gg = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, gg, b], -1).astype(np.int32)


def dxt1(buf, w, h):
    bw, bh = max(1, w // 4), max(1, h // 4)
    n = bw * bh
    blk = np.frombuffer(buf[:n * 8], dtype=np.uint8).reshape(n, 8)
    c0 = blk[:, 0].astype(np.int32) | (blk[:, 1].astype(np.int32) << 8)
    c1 = blk[:, 2].astype(np.int32) | (blk[:, 3].astype(np.int32) << 8)
    idx = (blk[:, 4].astype(np.uint32) | (blk[:, 5].astype(np.uint32) << 8) |
           (blk[:, 6].astype(np.uint32) << 16) | (blk[:, 7].astype(np.uint32) << 24))
    p0, p1 = c565(c0), c565(c1)
    four = (c0 > c1)[:, None]
    p2 = np.where(four, (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four, (p0 + 2 * p1) // 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)
    sel = np.stack([(idx >> (2 * i)) & 3 for i in range(16)], 1).astype(np.int64)
    rgb = np.take_along_axis(pal, sel[:, :, None].repeat(3, 2), 1)
    img = rgb.reshape(bh, bw, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 3)
    return img[:h, :w].astype(np.float64) / 255.0, n * 8


def mips(off, w, h, levels):
    out, o = [], off
    for _ in range(levels):
        img, used = dxt1(ram[o:], w, h)
        out.append(img @ np.array([0.299, 0.587, 0.114]))
        o += used
        w, h = max(1, w // 2), max(1, h // 2)
    return out


def bilinear(img, u, v):
    hh, ww = img.shape
    x = u * ww - 0.5
    y = v * hh - 0.5
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    xa, xb, ya, yb = x0 % ww, (x0 + 1) % ww, y0 % hh, (y0 + 1) % hh
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) +
            img[yb, xa] * (1 - fx) * fy + img[yb, xb] * fx * fy)


# ---------- vertex records ----------
REC = np.dtype([("p", "<f4", 3), ("n", "<i4"), ("b", "<i4"), ("t", "<i4"),
                ("uv", "<i2", 2), ("bi", "u1", 2), ("bw", "<i2")])


def verts(addr, nv):
    rec = np.frombuffer(ram[addr:addr + nv * 32], dtype=REC)
    V0 = np.concatenate([rec["p"].astype(np.float64), np.ones((nv, 1))], 1)
    V4 = np.concatenate([np.maximum(rec["uv"] / 32767.0, -1), np.zeros((nv, 1)), np.ones((nv, 1))], 1)
    return V0, V4, rec["bi"].astype(np.float64), np.maximum(rec["bw"] / 32767.0, -1)


def tris_of(strip):
    t = []
    for k in range(len(strip) - 2):
        a, b, c = strip[k], strip[k + 1], strip[k + 2]
        if a == b or b == c or a == c:
            continue
        t.append((a, b, c) if k % 2 == 0 else (b, a, c))
    return np.array(t)


def vp(C, V0, V4, V5, V6):
    """The hull program's position and texcoord 0 (hull_vsh.glsl; swr.py)."""
    a0 = np.floor(V5[:, 0] * C[7, 3]).astype(int)
    a1 = np.floor(V5[:, 1] * C[7, 3]).astype(int)
    a1 = np.where(a1 + 62 < 192, a1, 0)
    w0, w1 = V6[:, None], (1 - V6)[:, None]
    rows = [w0 * C[a0 + 60 + k] + w1 * C[a1 + 60 + k] for k in range(3)]
    R10 = np.stack([np.sum(V0 * r, 1) for r in rows], 1)
    P = np.stack([np.sum(np.concatenate([R10, np.ones((len(V0), 1))], 1) * C[k], 1) for k in range(4)], 1)
    SX = P[:, 0] / P[:, 3] * C[58, 0] + C[59, 0]
    SY = P[:, 1] / P[:, 3] * C[58, 1] + C[59, 1]
    SZ = P[:, 2] / P[:, 3] * C[58, 2] + C[59, 2]
    A = V4[:, 0] * C[13, 0] + V4[:, 1] * C[13, 1]        # oT0.x without the scroll c13.w
    B = np.sum(V4 * C[14], 1)                            # oT0.y in full
    return SX, SY, SZ, P[:, 3], np.stack([A, B], 1)


ZSIGN = -1.0 if opt.get("zfunc", "less") == "greater" else 1.0
CULL = {"n4": opt.get("cull4", "neg"), "n5": opt.get("cull5", "neg")}


def raster(layers):
    """layers: [(id, tris, SX, SY, SZ, PW, attr, cull)]. Returns per-pixel layer id, triangle, barycentrics."""
    zbuf = np.full((H, W), np.inf)
    lid = np.full((H, W), -1)
    tid = np.full((H, W), -1)
    bary = np.zeros((H, W, 3))
    for L, tris, SX, SY, SZ, PW, _, cull in layers:
        SZ = SZ * ZSIGN
        for t, (a, b, c) in enumerate(tris):
            if min(PW[a], PW[b], PW[c]) <= 0:
                continue
            xa, ya, xb, yb, xc, yc = SX[a], SY[a], SX[b], SY[b], SX[c], SY[c]
            area = (xb - xa) * (yc - ya) - (xc - xa) * (yb - ya)
            if area == 0 or (cull == "pos" and area > 0) or (cull == "neg" and area < 0):
                continue
            x0, x1 = max(int(np.floor(min(xa, xb, xc))), 0), min(int(np.ceil(max(xa, xb, xc))), W - 1)
            y0, y1 = max(int(np.floor(min(ya, yb, yc))), 0), min(int(np.ceil(max(ya, yb, yc))), H - 1)
            if x0 > x1 or y0 > y1:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            l0 = ((xb - gx) * (yc - gy) - (xc - gx) * (yb - gy)) / area
            l1 = ((xc - gx) * (ya - gy) - (xa - gx) * (yc - gy)) / area
            l2 = 1 - l0 - l1
            inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not inside.any():
                continue
            z = l0 * SZ[a] + l1 * SZ[b] + l2 * SZ[c]
            sub = zbuf[y0:y1 + 1, x0:x1 + 1]
            m = inside & (z <= sub)
            sub[m] = z[m]
            lid[y0:y1 + 1, x0:x1 + 1][m] = L
            tid[y0:y1 + 1, x0:x1 + 1][m] = t
            bary[y0:y1 + 1, x0:x1 + 1][m] = np.stack([l0[m], l1[m], l2[m]], -1)
    return lid, tid, bary


def ppm(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    img = np.frombuffer(parts[3][:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(np.float64) / 255
    return img @ np.array([0.299, 0.587, 0.114])


session, draws, frames, skips, shaders = g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
fimg = {int(f): r.get("image") for f, r in frames.items()}
base = os.path.dirname(os.path.abspath(dump))
if "images" in opt:
    # pixels from elsewhere: vidmap.py's map.tsv (frame, t_video, video_frame, ppm), a
    # video frame per dump frame. The video's FPS counter (top left) is kept out of the fit.
    fimg = {}
    for line in open(opt["images"]).read().splitlines()[1:]:
        p = line.split("\t")
        fimg[int(p[0])] = os.path.abspath(p[3])
want_f = sorted(f for f in fimg if fimg[f] and f % EVERY == 0)
st = g.replay(draws, set(want_f))

geo = {k: verts(v[1], v[2]) for k, v in DRAWS.items()}
tris = {k: tris_of(v[3]) for k, v in DRAWS.items()}
tex = {k: mips(*v[4]) for k, v in DRAWS.items()}
rng = np.random.default_rng(939)

# The scan window per draw: the dump's c13.w over the frames, padded.
cw = {k: {} for k in DRAWS}
for f in want_f:
    for d in draws:
        if d["f"] == f:
            for k, v in DRAWS.items():
                if d["count"] == v[0]:
                    C = np.array([g.f32(w) for w in st[(f, d["n"])]["c"]], dtype=np.float64).reshape(192, 4)
                    cw[k][f] = C
out = open(outf, "w")
out.write("frame\tdraw\tpixels\tc13w\td_best\tr_best\td_minus_c13w\tr_at_c13w\tr_at_first_c13w\tlod\n")
for k in WANT:
    ws = [cw[k][f][13, 3] for f in cw[k]]
    lo, hi = min(ws), max(ws)
    pad = 0.01 if k == "n4" else 0.03
    step = 0.00005 if k == "n4" else 0.0002
    grid_d = np.arange(lo - pad, hi + pad, step)
    first = cw[k][min(cw[k])][13, 3]
    for f in sorted(cw[k]):
        layers = []
        for L, name in enumerate(DRAWS):
            if f not in cw[name]:
                continue
            SX, SY, SZ, PW, AT = vp(cw[name][f], *geo[name])
            layers.append((L, tris[name], SX, SY, SZ, PW, AT, CULL[name]))
        lid, tid, bary = raster(layers)
        L = list(DRAWS).index(k)
        ys, xs = np.nonzero(lid == L)
        if "images" in opt:
            keep = ~((ys < 23) & (xs < 65))
            ys, xs = ys[keep], xs[keep]
        if len(ys) < 200:
            out.write(f"{f}\t{k}\t{len(ys)}\t{cw[k][f][13, 3]:.6f}\t\t\t\t\t\t\n")
            continue
        lay = [x for x in layers if x[0] == L][0]
        vi = lay[1][tid[ys, xs]]
        pw = bary[ys, xs] / lay[5][vi]
        pw /= pw.sum(1, keepdims=True)
        ab = np.einsum("nk,nkc->nc", pw, lay[6][vi])
        # LOD from the screen footprint of a (texels per pixel along u), median over the draw
        agrid = np.full((H, W), np.nan)
        agrid[ys, xs] = ab[:, 0]
        du = np.abs(np.diff(agrid, axis=1))
        dv = np.abs(np.diff(agrid, axis=0))
        tw = DRAWS[k][4][1]
        rho = np.nanmedian(np.concatenate([du[np.isfinite(du)], dv[np.isfinite(dv)]])) * tw
        lod = int(np.clip(np.round(np.log2(max(rho, 1e-6))), 0, len(tex[k]) - 1))
        img = ppm(fimg[f] if "images" in opt else os.path.join(base, os.path.basename(fimg[f])))
        sel = rng.choice(len(ys), size=min(NPX, len(ys)), replace=False)
        lum = img[ys[sel], xs[sel]]
        lum = (lum - lum.mean()) / (lum.std() + 1e-9)
        a, b = ab[sel, 0], ab[sel, 1]
        T = tex[k][lod]
        rs = np.empty(len(grid_d))
        for i, dd in enumerate(grid_d):
            p = bilinear(T, a + dd, b)
            p = (p - p.mean()) / (p.std() + 1e-9)
            rs[i] = np.mean(p * lum)
        ib = int(np.argmax(rs))

        def r_at(dd):
            p = bilinear(T, a + dd, b)
            p = (p - p.mean()) / (p.std() + 1e-9)
            return np.mean(p * lum)
        c = cw[k][f][13, 3]
        if "dbg" in opt:
            from PIL import Image
            os.makedirs(opt["dbg"], exist_ok=True)
            pred = np.full((H, W), np.nan)
            pred[ys, xs] = bilinear(T, ab[:, 0] + c, ab[:, 1])
            pan = np.zeros((H, W * 3, 3))
            pan[:, :W] = img[:, :, None]
            pan[:, W:2 * W] = np.array([[0, 0, 0], [1, .3, .3], [.3, 1, .3]])[lid + 1] * (0.4 + 0.6 * img[:, :, None])
            pan[:, 2 * W:] = np.nan_to_num(pred)[:, :, None]
            Image.fromarray((np.clip(pan, 0, 1) * 255).astype(np.uint8)).save(f"{opt['dbg']}/f{f:03d}_{k}.png")
        out.write(f"{f}\t{k}\t{len(ys)}\t{c:.6f}\t{grid_d[ib]:.6f}\t{rs[ib]:.3f}\t{grid_d[ib] - c:+.6f}"
                  f"\t{r_at(c):.3f}\t{r_at(first):.3f}\t{lod}\n")
        out.flush()
        print(f"f{f} {k} px {len(ys)} c13w {c:.5f} d* {grid_d[ib]:.5f} r* {rs[ib]:.3f} "
              f"d*-c13w {grid_d[ib] - c:+.5f} r(c13w) {r_at(c):.3f} r(first) {r_at(first):.3f} lod {lod}", flush=True)
