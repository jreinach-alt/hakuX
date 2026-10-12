"""Run the projection's per-pixel depth rebuild (shader 7f12c419's VS and FS
arithmetic, float32) on a dumped consumer and compare it with fdread cover's
ideal depth and with zpre.  usage: fsz.py DUMP F N [F N ...]"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdread  # noqa: E402

f32 = np.float32


def r32(x):
    return np.asarray(x, dtype=np.float64).astype(np.float32)


def fma(a, b, c):
    # float32 operands: a*b is exact in float64; one rounding to float32 after
    return r32(a.astype(np.float64) * b.astype(np.float64) + c.astype(np.float64))


def kahan(ax, ay, bx, by):
    cd = ay * bx
    err = fma(-ay, bx, cd)
    return fma(ax, by, -cd) + err


def area(px, py, b, c):
    return kahan(f32(b[0]) - px, f32(b[1]) - py, f32(c[0]) - px, f32(c[1]) - py)


def clamp_w(t):
    t = f32(t)
    if t > 0 or t == 0:
        return f32(min(max(t, 2.0 ** -64), 2.0 ** 64))
    return f32(max(min(t, -(2.0 ** -64)), -(2.0 ** 64)))


def rtz32(x):
    y = np.float32(x)
    if abs(float(y)) > abs(x):
        y = np.nextafter(y, np.float32(0))
    return y


def vtx(p, C, off):
    p32 = [f32(v) for v in p]
    o = []
    for j in range(4):
        acc = f32(0)
        for i in range(4):
            acc = f32(acc + f32(p32[i] * f32(C[j][i])))
        o.append(acc)
    w = clamp_w(o[3])
    scr = [f32(o[0] / w + f32(off[0])), f32(o[1] / w + f32(off[1]))]
    xy = [f32(np.trunc(f32(s * f32(16))) / f32(16)) for s in scr]
    zx = sum(float(p32[i]) * float(C[2][i]) for i in range(4))
    wx = sum(float(p32[i]) * float(C[3][i]) for i in range(4))
    z = rtz32(zx / wx)
    return np.array([xy[0], xy[1], z, w], dtype=np.float32), scr


def fs_depth(V, X, Y):
    v0, v1, v2 = V
    px, py = f32(X), f32(Y)
    bc0 = area(px, py, v1, v2)
    bc1 = area(px, py, v2, v0)
    bc2 = area(px, py, v0, v1)
    bcsum = (bc0 + bc1) + bc2
    bu1, bu2 = bc1, bc2
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        inv = f32(1) / (bc0 + bc1 + bc2)
    inv = np.where(np.isinf(inv), f32(0), inv)
    bc1 = bc1 * inv
    bc2 = bc2 * inv
    z0, z1, z2 = f32(v0[2]), f32(v1[2]), f32(v2[2])
    zhi = np.floor(z0)
    zd1 = z1 - z0
    zd2 = z2 - z0

    def two(a, b):
        va = f32(4097) * a
        ah = va - (va - a)
        al = a - ah
        vb = f32(4097) * b
        bh = vb - (vb - b)
        bl = b - bh
        p = a * b
        return p, (((ah * bh - p) + ah * bl) + al * bh) + al * bl

    with np.errstate(all="ignore"):
        zp1, zt1 = two(bu1, f32(zd1))
        zp2, zt2 = two(bu2, f32(zd2))
        znh = zp1 + zp2
        zbv = znh - zp1
        zav = znh - zbv
        znt = ((zp1 - zav) + (zp2 - zbv)) + (zt1 + zt2)
        zdh = np.where(inv == 0, f32(0), znh / bcsum)
        qp, qe = two(zdh, bcsum)
        zrn = ((znh - qp) - qe) + znt
        zdt = np.where(inv == 0, f32(0), zrn / bcsum)
        zdn = np.floor(zdh)
        zbase = zhi + zdn
        zrem = ((z0 - zhi) + (zdh - zdn)) + zdt
        zlo = (z0 - zhi) + (bc1 * (z1 - z0) + bc2 * (z2 - z0))
        zvalue = zhi + zlo
        zfloor = zbase + np.floor(zrem)
    return zvalue.astype(np.float64), zfloor.astype(np.float64)


def run(path, fsel, nsel, draws):
    d = next(x for x in draws if x["f"] == fsel and x["n"] == nsel)
    cm = [[fdread.hf(x) for x in r.split()] for r in d["cm"]]
    C = cm[0:4]
    off = cm[5][:2]
    zmax = fdread.hf(d["rs"]["zmax"])
    zmin = fdread.hf(d["rs"]["zmin"])
    W, H = d["color"]["w"], d["color"]["h"]
    base = os.path.dirname(path)
    rbs = {(e["k"], e["s"]): e for e in d.get("rb", [])}
    zp = fdread.load_depth(base, rbs.get(("zpre", -1)))
    zp = np.array(zp[0]).reshape(H, W) * 16777216.0 if zp else None
    Xc, Yc = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    M = np.array(C, dtype=np.float64)
    verts = []
    for e in d["v"]:
        pos = [fdread.hf(x) for x in e[1].split()]
        while len(pos) < 3:
            pos.append(0.0)
        verts.append(pos[:3] + [1.0])
    tot = dict(cov=0, disc=0, ideal_pass=0, fs_pass=0, big=0)
    for t in range(len(verts) // 3):
        tri = verts[3 * t:3 * t + 3]
        c = np.array([M @ np.array(v) for v in tri])
        A = np.array([c[:, 0], c[:, 1], c[:, 3]])
        Ai = np.linalg.inv(A)
        X, Y = Xc - off[0], Yc - off[1]
        lam = [Ai[i, 0] * X + Ai[i, 1] * Y + Ai[i, 2] for i in range(3)]
        inside = (lam[0] >= 0) & (lam[1] >= 0) & (lam[2] >= 0)
        z = lam[0] * c[0, 2] + lam[1] * c[1, 2] + lam[2] * c[2, 2]
        inside &= (z >= zmin) & (z <= zmax)
        n = int(inside.sum())
        V, S = zip(*[vtx(v, C, off) for v in tri])
        ws = "".join("-" if v[3] < 0 else "+" for v in V)
        print("  f%d n%d tri %d %s: vtxPos %s" % (fsel, nsel, t, ws, "; ".join(
            "(%.6g, %.6g, %.8g, %.4g)" % tuple(float(a) for a in v) for v in V)))
        if not n:
            print("    covers 0 px")
            continue
        zv, zf = fs_depth(V, Xc[inside], Yc[inside])
        zi = z[inside]
        disc = (zv < zmin) | (zv > zmax) | ~np.isfinite(zv)
        dz = (zf - zi)[~disc]
        line = "    covers %d px: FS discards %d (clipRange); FS z - ideal z med %+.1f max|.| %.1f" % (
            n, int(disc.sum()), np.median(dz) if dz.size else np.nan,
            np.abs(dz).max() if dz.size else np.nan)
        tot["cov"] += n
        tot["disc"] += int(disc.sum())
        if zp is not None:
            zz = zp[inside]
            ip = zi <= zz + 2
            fp = (~disc) & (np.minimum(zf, 16777215.0) <= zz)
            line += "; LEQUAL vs zpre: ideal %d, FS %d" % (int(ip.sum()), int(fp.sum()))
            tot["ideal_pass"] += int(ip.sum())
            tot["fs_pass"] += int(fp.sum())
        tot["big"] += int((np.abs(dz) > 64).sum())
        print(line)
    print("f%d n%d total: %s" % (fsel, nsel, tot))


def main():
    path = sys.argv[1]
    _, draws, _, _ = fdread.load(path)
    a = sys.argv[2:]
    for i in range(0, len(a), 2):
        run(path, int(a[i]), int(a[i + 1]), draws)


if __name__ == "__main__":
    main()
