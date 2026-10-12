"""For each projection consumer: of the lit covered pixels that FAIL LEQUAL
against zpre, how far behind are they (units of 2^-24), and where.
usage: litfail.py DUMP [outdir]"""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdread
hf = fdread.hf
path = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else None
base = os.path.dirname(path)
_, draws, frames, _ = fdread.load(path)
for d in draws:
    if not d.get("shader", "").startswith("7f12c419") or d.get("prim") != 5:
        continue
    rbs = {(e["k"], e["s"]): e for e in d.get("rb", [])}
    if ("zpre", -1) not in rbs:
        continue
    cm = [[hf(x) for x in r.split()] for r in d["cm"]]
    M = np.array(cm[0:4]); off = cm[5][:2]
    W, H = d["color"]["w"], d["color"]["h"]
    verts = []
    for e in d["v"]:
        pos = [hf(x) for x in e[1].split()]
        uv = [hf(x) for x in e[3].split()]
        verts.append((np.array(pos[:3] + [1.0]), uv[:2]))
    X, Y = np.meshgrid(np.arange(W) + 0.5 - off[0], np.arange(H) + 0.5 - off[1])
    cov = np.zeros((H, W), bool); zexp = np.full((H, W), np.nan)
    U = np.full((H, W), np.nan); V = np.full((H, W), np.nan)
    for t in range(len(verts) // 3):
        tri = verts[3 * t:3 * t + 3]
        c = np.array([M @ v[0] for v in tri])
        A = np.array([c[:, 0], c[:, 1], c[:, 3]])
        if abs(np.linalg.det(A)) < 1e-12:
            continue
        Ai = np.linalg.inv(A)
        lam = [Ai[i, 0] * X + Ai[i, 1] * Y + Ai[i, 2] for i in range(3)]
        inside = (lam[0] >= 0) & (lam[1] >= 0) & (lam[2] >= 0)
        z = lam[0] * c[0, 2] + lam[1] * c[1, 2] + lam[2] * c[2, 2]
        s = lam[0] + lam[1] + lam[2]
        new = inside & ~cov
        cov |= inside
        zexp[new] = z[new]
        U[new] = (sum(lam[i] * tri[i][1][0] for i in range(3)) / s)[new]
        V[new] = (sum(lam[i] * tri[i][1][1] for i in range(3)) / s)[new]
    ta = np.asarray(fdread.load_rgba(base, rbs[("tex", 0)]).convert("RGB"), dtype=np.int32)
    th, tw = ta.shape[:2]
    tx = np.clip(np.floor(np.nan_to_num(U) * tw), 0, tw - 1).astype(int)
    ty = np.clip(np.floor(np.nan_to_num(V) * th), 0, th - 1).astype(int)
    tv = ta[ty, tx].max(axis=2)
    lit = cov & (tv > 8)
    zv, zw, zh = fdread.load_depth(base, rbs[("zpre", -1)])
    zp = np.array(zv).reshape(zh, zw) * 16777216.0
    dz = zexp - zp                        # >0: behind what is there
    fail = lit & (dz > 2)
    pas = lit & ~fail
    w = lambda m: (tv[m].astype(float)).sum()   # texel-weighted (how much shadow)
    f = dz[fail]
    bins = [(2, 64), (64, 1024), (1024, 16384), (16384, 1e9)]
    hist = " ".join("%d-%s:%d" % (a, "inf" if b > 1e8 else "%d" % b, int(((f > a) & (f <= b)).sum())) for a, b in bins)
    print("f%-2d n%d lit %5d pass %5d (%.0f%% of texel weight)  fail dz %s" % (
        d["f"], d["n"], int(lit.sum()), int(pas.sum()), 100 * w(pas) / max(w(lit), 1), hist))
    if out:
        os.makedirs(out, exist_ok=True)
        pre = np.asarray(fdread.load_rgba(base, rbs[("pre", -1)]).convert("RGB"), dtype=np.uint8).copy()
        img = (pre * 0.5).astype(np.uint8)
        img[pas] = (0, 220, 0)
        img[fail & (dz <= 1024)] = (255, 255, 0)
        img[fail & (dz > 1024) & (dz <= 16384)] = (255, 128, 0)
        img[fail & (dz > 16384)] = (255, 0, 0)
        Image.fromarray(img).save(os.path.join(out, "lf_f%03d.png" % d["f"]))
