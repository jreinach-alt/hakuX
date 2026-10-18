"""Software render of the main-menu ring's hull (n5) and band (n4), term by term (#939, (a)).

usage: hullsw.py DUMP.jsonl RAM.bin FRAME OUTDIR [image=PPM] [tag=NAME]

The two draws share one vertex program and one 8-stage combiner. This file is
both, in numpy, from the frame's own replayed state:

  - the vertex program as the generated GLSL has it (vsh_48c74844.glsl,
    slots 0-44): two-bone blend from c60+, world normal from the CMP
    normal, oD0 = max(N.-c23,0)*c24 + max(N.-c25,0)*c26 + c27 (.w = v4.z),
    oD1 = (normalize(c4-P).N)*c15 + c16, oT0 = oT2 = (DPH(v4,c13),
    DPH(v4,c14)), oT1 = oT0*c12.xy, oT3 = c4.w*(E.N)N - E;
  - n4 then n5 rasterised with a z-buffer and the dump's cull (bandfit.py),
    every varying interpolated perspective-correct;
  - the four textures read from RAM.bin at the stage offsets the dump names
    (DXT1, or swizzled X8R8G8B8), trilinear with the LOD from each pixel's
    screen footprint; stage 3 a cube (6 faces, face stride from the key);
  - the combiner as psh_48c74844.glsl lines 362-403 computes it, with the
    stage constants read from COMBINEFACTOR0/1 and SPECFOGFACTOR0 of the
    frame. The register words are checked against the ones this
    transcription was written from; a draw with other words is refused.

Writes OUTDIR/<tag>.npz (per pixel: layer, and each term: t0..t3, oD0,
oD1, the diffuse 2*t0*t1*v0, the reflection t3*v1*t2.r*v1.a, the final
colour) and OUTDIR/<tag>.png (final | the dump's image when given | terms).
A layer is -1 off the ring, 0 for n4 and 1 for n5.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

W, H = 640, 480
NAMES = {864: "n4", 4362: "n5"}
# draw -> (vertex records, nvert, strip): as M1 read them (bandfit.py)
GEOM = {"n4": (0x3d6840, 290, None), "n5": (0x3cfb80, 870, (0x3dc8f8, 1456))}
# the combiner words this transcription is of: COLORI/O, ALPHAI/O 0-7, COMBINECTL,
# SPECFOG0/1 (combwords.py on run 13 f543, n4 and n5 alike)
WORDS = {
    0x1900: [0x0a020a01, 0x04200c01, 0x3c201c01, 0x00a02009, 0x0b05040c, 0x022014e1, 0x08090809, 0x08040b1d],
    0x1920: [0x000030cd, 0x00000400, 0x00000c00, 0x00000900, 0x000000b4, 0x00000d00, 0x00000800, 0x00000c00],
    0x18C0: [0x0a200000, 0x1c200000, 0x0c200d15, 0, 0, 0, 0, 0],
    0x18E0: [0x000000c0, 0x00000090, 0x000000cd, 0, 0, 0, 0, 0],
}
SINGLE = {0x1940: 0x00011008, 0x1944: 0x340f010d, 0x1948: 0x0c111800}


def argb(u):
    return np.array([(u >> 16) & 255, (u >> 8) & 255, u & 255, (u >> 24) & 255], dtype=np.float64) / 255.0


# ---------- textures ----------
def c565(c):
    r = ((c >> 11) & 31) * 255 // 31
    gg = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, gg, b], -1).astype(np.int32)


def dxt1(buf, w, h):
    """RGBA in [0,1]; the 3-colour mode's index 3 is transparent black."""
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
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
    alpha = np.stack([np.full(n, 255), np.full(n, 255), np.full(n, 255),
                      np.where(four[:, 0], 255, 0)], 1)
    pal = np.concatenate([pal, alpha[:, :, None]], 2)
    sel = np.stack([(idx >> (2 * i)) & 3 for i in range(16)], 1).astype(np.int64)
    rgba = np.take_along_axis(pal, sel[:, :, None].repeat(4, 2), 1)
    img = rgba.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return img[:h, :w].astype(np.float64) / 255.0, n * 8


def morton(w, h):
    """Linear index of each (y, x) in an NV2A swizzled (Morton) w x h surface."""
    ys, xs = np.mgrid[0:h, 0:w]
    out = np.zeros((h, w), dtype=np.int64)
    bit, sx, sy = 0, 1, 1
    while sx < w or sy < h:
        if sx < w:
            out |= ((xs // sx) & 1) << bit
            bit += 1
            sx *= 2
        if sy < h:
            out |= ((ys // sy) & 1) << bit
            bit += 1
            sy *= 2
    return out


def level(ram, off, fmtc, w, h):
    if fmtc == 0x0C:
        return dxt1(ram[off:], w, h)
    if fmtc in (0x06, 0x07):
        px = np.frombuffer(ram[off:off + w * h * 4], dtype=np.uint8).reshape(-1, 4)
        img = px[morton(w, h)].astype(np.float64) / 255.0       # B G R A
        rgba = img[..., [2, 1, 0, 3]]
        if fmtc == 0x07:
            rgba[..., 3] = 1.0
        return rgba, w * h * 4
    raise SystemExit(f"texture format {fmtc:#x} not handled")


def load_tex(ram, s):
    w, h, levels, fmtc, size = s["key"]
    off = int(s["off"], 16)
    cube = (int(s["fmt"], 16) >> 2) & 1

    def chain(o):
        out, ww, hh = [], w, h
        for _ in range(levels):
            img, used = level(ram, o, fmtc, ww, hh)
            out.append(img)
            o += used
            if ww == 1 and hh == 1:
                break
            ww, hh = max(1, ww // 2), max(1, hh // 2)
        return out
    if cube:
        return [chain(off + k * (size // 6)) for k in range(6)]
    return chain(off)


def bilinear(img, u, v, wrap):
    hh, ww = img.shape[:2]
    x = u * ww - 0.5
    y = v * hh - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    if wrap:
        xa, xb, ya, yb = x0 % ww, (x0 + 1) % ww, y0 % hh, (y0 + 1) % hh
    else:
        xa, xb = np.clip(x0, 0, ww - 1), np.clip(x0 + 1, 0, ww - 1)
        ya, yb = np.clip(y0, 0, hh - 1), np.clip(y0 + 1, 0, hh - 1)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) +
            img[yb, xa] * (1 - fx) * fy + img[yb, xb] * fx * fy)


def trilinear(chain, u, v, lod, wrap=True):
    lod = np.clip(np.nan_to_num(lod, nan=0.0), 0, len(chain) - 1)
    l0 = np.floor(lod).astype(int)
    fr = (lod - l0)[:, None]
    l1 = np.minimum(l0 + 1, len(chain) - 1)
    out = np.zeros((len(u), 4))
    for lv in np.unique(np.concatenate([l0, l1])):
        a = l0 == lv
        if a.any():
            out[a] += bilinear(chain[lv], u[a], v[a], wrap) * (1 - fr[a])
        b = l1 == lv
        if b.any():
            out[b] += bilinear(chain[lv], u[b], v[b], wrap) * fr[b]
    return out


def cube_face(R):
    """GL/D3D convention: faces +x -x +y -y +z -z; (s, t) in [0, 1]."""
    ax = np.abs(R)
    face = np.where((ax[:, 0] >= ax[:, 1]) & (ax[:, 0] >= ax[:, 2]), np.where(R[:, 0] >= 0, 0, 1),
                    np.where(ax[:, 1] >= ax[:, 2], np.where(R[:, 1] >= 0, 2, 3), np.where(R[:, 2] >= 0, 4, 5)))
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    sc = np.choose(face, [-z, z, x, x, x, -x])
    tc = np.choose(face, [-y, -y, z, -z, -y, -y])
    ma = np.choose(face, [ax[:, 0], ax[:, 0], ax[:, 1], ax[:, 1], ax[:, 2], ax[:, 2]])
    ma = np.maximum(ma, 1e-12)
    return face, (sc / ma + 1) / 2, (tc / ma + 1) / 2


# ---------- vertex program ----------
REC = np.dtype([("p", "<f4", 3), ("n", "<i4"), ("b", "<i4"), ("t", "<i4"),
                ("uv", "<i2", 2), ("bi", "u1", 2), ("bw", "<i2")])


def cmp(v):
    v = v.astype(np.int32)
    return np.stack([((v << 21) >> 21) / 1023.0, ((v << 10) >> 21) / 1023.0,
                     (v >> 22) / 511.0, np.ones(len(v))], 1)


def tris_of(strip):
    t = []
    for k in range(len(strip) - 2):
        a, b, c = strip[k], strip[k + 1], strip[k + 2]
        if a == b or b == c or a == c:
            continue
        t.append((a, b, c) if k % 2 == 0 else (b, a, c))
    return np.array(t)


def program(C, rec, v4z=0.0):
    """vsh_48c74844.glsl slots 0-44. Returns screen x, y, z, w and the varyings (N, 17):
    oD0 rgba, oD1 rgba, oT0 xy, oT1 xy, oT2 xy, oT3 xyz."""
    n = len(rec)
    v0 = np.concatenate([rec["p"].astype(np.float64), np.ones((n, 1))], 1)
    v1 = cmp(rec["n"])
    v4 = np.stack([np.maximum(rec["uv"][:, 0] / 32767.0, -1), np.maximum(rec["uv"][:, 1] / 32767.0, -1),
                   np.full(n, v4z), np.ones(n)], 1)
    v5 = rec["bi"].astype(np.float64) / 255.0
    v6x = np.maximum(rec["bw"] / 32767.0, -1)
    a0 = np.floor(v5[:, 0] * C[7, 3]).astype(int)
    a1 = np.floor(v5[:, 1] * C[7, 3]).astype(int)
    a0 = np.where(a0 + 62 < 192, a0, 0)
    a1 = np.where(a1 + 62 < 192, a1, 0)
    rows = [v6x[:, None] * C[a0 + 60 + k] + (1 - v6x)[:, None] * C[a1 + 60 + k] for k in range(3)]
    R10 = np.stack([np.sum(v0 * r, 1) for r in rows], 1)                       # DPH, v0.w = 1
    R11 = np.stack([np.sum(v1[:, :3] * r[:, :3], 1) for r in rows], 1)         # DP3
    E = C[4, :3] - R10                                                          # R2
    N = R11 * C[12, 3]                                                          # R0
    EN = np.sum(E * N, 1)
    oT3 = EN[:, None] * N * C[4, 3] - E
    R6x = N @ -C[23, :3]
    R8y = N @ -C[25, :3]
    R8x = np.maximum(R6x, -R6x * C[14, 2])
    R9x, R9y = np.maximum(R8x, v4[:, 2]), np.maximum(R8y, v4[:, 2])
    oD0 = np.concatenate([R9x[:, None] * C[24, :3] + R9y[:, None] * C[26, :3] + C[27, :3], v4[:, 2:3]], 1)
    En = E / np.sqrt(np.maximum(np.sum(E * E, 1), 1e-30))[:, None]
    oD1 = np.sum(En * N, 1)[:, None] * C[15] + C[16]
    oT0 = np.stack([v4 @ C[13], v4 @ C[14]], 1)                                 # DPH, v4.w = 1
    oT1 = oT0 * C[12, :2]
    P = np.concatenate([R10, np.ones((n, 1))], 1) @ C[0:4].T
    SX = P[:, 0] / P[:, 3] * C[58, 0] + C[59, 0]
    SY = P[:, 1] / P[:, 3] * C[58, 1] + C[59, 1]
    SZ = P[:, 2] / P[:, 3] * C[58, 2] + C[59, 2]
    var = np.concatenate([np.clip(oD0, 0, 1), np.clip(oD1, 0, 1), oT0, oT1, oT0, oT3], 1)
    return SX, SY, SZ, P[:, 3], var


def raster(layers):
    """layers: [(id, tris, SX, SY, SZ, PW)], drawn in order, cull 'neg', depth less-equal."""
    zbuf = np.full((H, W), np.inf)
    lid = np.full((H, W), -1)
    tid = np.full((H, W), -1)
    bary = np.zeros((H, W, 3))
    for L, tris, SX, SY, SZ, PW in layers:
        for t, (a, b, c) in enumerate(tris):
            if min(PW[a], PW[b], PW[c]) <= 0:
                continue
            xa, ya, xb, yb, xc, yc = SX[a], SY[a], SX[b], SY[b], SX[c], SY[c]
            area = (xb - xa) * (yc - ya) - (xc - xa) * (yb - ya)
            if area <= 0:
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


def footprint(ys, xs, U, V, tw, th):
    """Per-pixel LOD: log2 of the larger screen-axis footprint in texels (forward
    difference, backward where the forward neighbour is off the surface)."""
    gu = np.full((H + 2, W + 2), np.nan)
    gv = np.full((H + 2, W + 2), np.nan)
    gu[ys + 1, xs + 1] = U
    gv[ys + 1, xs + 1] = V

    def d(gr, dy, dx):
        f = gr[ys + 1 + dy, xs + 1 + dx] - gr[ys + 1, xs + 1]
        b = gr[ys + 1, xs + 1] - gr[ys + 1 - dy, xs + 1 - dx]
        return np.where(np.isfinite(f), f, b)
    ux, vx, uy, vy = d(gu, 0, 1), d(gv, 0, 1), d(gu, 1, 0), d(gv, 1, 0)
    rho = np.maximum(np.hypot(ux * tw, vx * th), np.hypot(uy * tw, vy * th))
    return np.log2(np.maximum(np.nan_to_num(rho, nan=1.0), 1e-6))


def combine(t0, t1, t2, t3, v0, v1, c0, c1, cf, v0a=None):
    """psh_48c74844.glsl 362-403. Arrays (N, 4); c0/c1 the 8 stage constants, cf SPECFOGFACTOR0."""
    pos = lambda x: np.maximum(x, 0)  # noqa: E731
    cl = lambda x: np.clip(x, -1, 1)  # noqa: E731
    sat = lambda x: np.clip(x, 0, 1)  # noqa: E731
    t0, t1, t2, t3, v0, v1 = (x.copy() for x in (t0, t1, t2, t3, v0, v1))
    if v0a is not None:
        v0[:, 3] = v0a
    n = len(t0)
    r0 = np.zeros((n, 4))
    r0[:, 3] = t0[:, 3]
    r1 = np.zeros((n, 4))
    # stage 0
    ab = cl(pos(t2[:, :3]) @ pos(c1[0][:3]))
    cd = cl(pos(t2[:, :3]) @ pos(c0[0][:3]))
    r0[:, :3], r1[:, :3], r0[:, 3] = ab[:, None], cd[:, None], cl(pos(t2[:, 2]))
    # stage 1
    v0[:, :3] = cl(pos(v0[:, :3]) + pos(r0[:, :3]) * pos(c0[1][:3]))
    t1[:, 3] = cl(pos(r0[:, 3]))
    # stage 2
    r0a, r0b, r1b = r0[:, 3].copy(), r0[:, 2].copy(), r1[:, 2].copy()
    r0[:, :3] = cl((1 - sat(r0a))[:, None] + pos(r0a)[:, None] * pos(c0[2][:3]))
    r0[:, 3] = cl(pos(r0b))
    r1[:, 3] = cl(pos(r1b) * pos(v1[:, 3]))
    # stage 3
    t1[:, :3] = cl(pos(t1[:, :3]))
    # stage 4
    t3n = cl(pos(t3[:, :3]) * pos(v1[:, :3]))
    v0[:, :3] = cl(pos(v0[:, :3]) * pos(r0[:, :3]))
    t3[:, :3] = t3n
    # stage 5
    r1[:, :3] = cl(pos(c1[5][:3]) + pos(v0[:, 3:4]) * -c0[5][:3])
    # stage 6
    t0[:, :3] = cl(2 * pos(t0[:, :3]) * pos(t1[:, :3]))
    # stage 7
    r0[:, :3] = cl(pos(t0[:, :3]) * pos(v0[:, :3]) + pos(t3[:, :3]) * pos(r1[:, 3:4]))
    # final
    k = (1 - sat(v0[:, 3]))[:, None]
    rgb = pos(r1[:, :3]) + pos(cf[:3]) * (1 - k) + pos(r0[:, :3] * pos(cf[3])) * k
    return rgb, {"diffuse": t0[:, :3] * v0[:, :3], "refl": t3[:, :3] * r1[:, 3:4], "v0lit": v0[:, :3]}


def ppm_rgb(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    return np.frombuffer(parts[3][:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(np.float64) / 255


def render(dump, ram, frame, v4z=0.0, loaded=None, state=None):
    """Everything per pixel for one frame. Returns a dict of full-screen arrays.
    A dict passed as state gets each layer's constants and decoded textures, by layer id."""
    session, draws, frames, skips, shaders = loaded or g.load(dump)
    for d in draws:
        for k in ("f", "n", "count"):
            d[k] = int(d[k])
    fd = {NAMES[d["count"]]: d for d in draws if d["f"] == frame and d["count"] in NAMES}
    st = g.replay(draws, {frame})
    layers, per = [], {}
    for L, name in enumerate(("n4", "n5")):
        if name not in fd:
            continue
        d = fd[name]
        s = st[(frame, d["n"])]
        r = s["r"]
        for base, words in WORDS.items():
            got = [r[base + 4 * i] for i in range(8)]
            if got != words:
                raise SystemExit(f"f{frame} {name}: combiner words at {base:#x} are {[hex(x) for x in got]}")
        for reg, word in SINGLE.items():
            if r[reg] != word:
                raise SystemExit(f"f{frame} {name}: {reg:#x} is {r[reg]:#010x}, not {word:#010x}")
        C =np.array([g.f32(w) for w in s["c"]], dtype=np.float64).reshape(192, 4)
        addr, nv, strip = GEOM[name]
        rec = np.frombuffer(ram[addr:addr + nv * 32], dtype=REC)
        idx = list(struct.unpack_from(f"<{strip[1]}H", ram, strip[0])) if strip else list(range(nv))
        SX, SY, SZ, PW, var = program(C, rec, v4z)
        tris = tris_of(idx)
        layers.append((L, tris, SX, SY, SZ, PW))
        tex = {t["s"]: t for t in d.get("tex", []) if t.get("en")}
        per[L] = dict(name=name, var=var, PW=PW, tris=tris, C=C,
                      c0=[argb(r[0x1880 + 4 * i]) for i in range(8)],
                      c1=[argb(r[0x18A0 + 4 * i]) for i in range(8)],
                      tex={k: (load_tex(ram, t), t["key"]) for k, t in tex.items()})
    lid, tid, bary = raster(layers)
    out = {"lid": lid}
    fields = {"t0": 4, "t1": 4, "t2": 4, "t3": 4, "oD0": 4, "oD1": 4, "final": 3, "diffuse": 3, "refl": 3,
              "v0lit": 3, "lod0": 1, "lod1": 1, "lod3": 1, "face": 1, "R": 3, "T0": 2}
    for k, c in fields.items():
        out[k] = np.full((H, W, c), np.nan)
    for L, p in per.items():
        ys, xs = np.nonzero(lid == L)
        if len(ys) == 0:
            continue
        vi = p["tris"][tid[ys, xs]]
        w = bary[ys, xs] / p["PW"][vi]
        w /= w.sum(1, keepdims=True)
        V = np.einsum("nk,nkc->nc", w, p["var"][vi])
        oD0, oD1, T0, T1, T2, T3 = V[:, 0:4], V[:, 4:8], V[:, 8:10], V[:, 10:12], V[:, 12:14], V[:, 14:17]
        ts = []
        for s, T in enumerate((T0, T1, T2)):
            chain, key = p["tex"][s]
            lod = footprint(ys, xs, T[:, 0], T[:, 1], key[0], key[1])
            ts.append(trilinear(chain, T[:, 0], T[:, 1], lod))
            if s in (0, 1):
                out[f"lod{s}"][ys, xs, 0] = lod
        faces, key3 = p["tex"][3]
        face, sc, tc = cube_face(T3)
        lod3 = footprint(ys, xs, face * 4.0 + sc, face * 4.0 + tc, key3[0] / 1.0, key3[1] / 1.0)
        lod3 = np.clip(lod3, 0, len(faces[0]) - 1)
        t3 = np.zeros((len(ys), 4))
        for f in range(6):
            m = face == f
            if m.any():
                t3[m] = trilinear(faces[f], sc[m], tc[m], lod3[m], wrap=False)
        cf = argb(st[(frame, fd[p["name"]]["n"])]["r"][0x19AC])           # SPECFOGFACTOR0
        rgb, terms = combine(ts[0], ts[1], ts[2], t3, oD0, oD1, p["c0"], p["c1"], cf)
        for k, v in (("t0", ts[0]), ("t1", ts[1]), ("t2", ts[2]), ("t3", t3), ("oD0", oD0), ("oD1", oD1),
                     ("final", rgb), ("R", T3), ("T0", T0)):
            out[k][ys, xs] = v
        for k, v in terms.items():
            out[k][ys, xs] = v
        out["lod3"][ys, xs, 0] = lod3
        out["face"][ys, xs, 0] = face
        p["cf"] = cf
    if state is not None:
        state.update(per)
    return out


def main():
    dump, ramf, frame, outdir = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    opt = dict(a.split("=", 1) for a in sys.argv[5:])
    ram = open(ramf, "rb").read()
    out = render(dump, ram, frame, float(opt.get("v4z", 0.0)))
    tag = opt.get("tag", f"f{frame:03d}")
    os.makedirs(outdir, exist_ok=True)
    np.savez_compressed(os.path.join(outdir, tag + ".npz"), **out)
    from PIL import Image
    pan = [np.nan_to_num(out["final"])]
    if "image" in opt:
        img = ppm_rgb(opt["image"])
        pan.append(img)
        ring = out["lid"] >= 0
        for L in (0, 1):
            m = out["lid"] == L
            if m.sum() < 50:
                continue
            a, b = out["final"][m], img[m]
            r = [np.corrcoef(a[:, c], b[:, c])[0, 1] for c in range(3)]
            print(f"f{frame} layer {L}: px {m.sum()} mean sw {a.mean(0).round(3)} img {b.mean(0).round(3)} "
                  f"MAE {np.abs(a - b).mean():.4f} r {np.round(r, 3)}")
        diff = np.zeros((H, W, 3))
        diff[ring] = 0.5 + 2 * (out["final"][ring] - img[ring])
        pan.append(diff)
    for k in ("t0", "t1", "t3", "diffuse", "refl"):
        pan.append(np.nan_to_num(out[k][:, :, :3]))
    rows = [np.concatenate(pan[i:i + 4] + [np.zeros((H, W, 3))] * (4 - len(pan[i:i + 4])), 1)
            for i in range(0, len(pan), 4)]
    Image.fromarray((np.clip(np.concatenate(rows, 0), 0, 1) * 255).astype(np.uint8)).save(
        os.path.join(outdir, tag + ".png"))


if __name__ == "__main__":
    main()
