"""Do the ring's decoded vertex normals agree with its own geometry? (#939, (a), M7)

usage: normcheck.py DUMP.jsonl RAM.bin FRAME

M7's first check (unit length for every array) cannot see a normal decoded
with its two 11-bit fields swapped, or one field's sign flipped: those keep
the length. This compares each vertex's decoded normal v1 (the CMP word,
hullsw.cmp) with the area-weighted mean of the face normals of the triangles
that use the vertex, in object space, for the decode as hakuX does it and for
every signed permutation of its components. A right decode puts most vertices
at a dot near +1 (or near -1 throughout, if the winding is reversed); a wrong
one scatters. It also prints the per-vertex |R| (R = c4.w (E.N) N - E) and
how far R turns between the two ends of each edge, which is what the
rasteriser interpolates.
"""
import itertools
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, frame = sys.argv[1], sys.argv[2], int(sys.argv[3])
ram = open(ramf, "rb").read()
S = {}
hs.render(dump, ram, frame, state=S)
for L, p in S.items():
    name = p["name"]
    addr, nv, strip = hs.GEOM[name]
    rec = np.frombuffer(ram[addr:addr + nv * 32], dtype=hs.REC)
    pos = rec["p"].astype(np.float64)
    tris = p["tris"]
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    fn = np.cross(b - a, c - a)                       # area-weighted, winding as drawn
    vn = np.zeros_like(pos)
    for k in range(3):
        np.add.at(vn, tris[:, k], fn)
    ok = np.linalg.norm(vn, axis=1) > 1e-12
    vn[ok] /= np.linalg.norm(vn[ok], axis=1)[:, None]
    n = hs.cmp(rec["n"])[:, :3]
    print(f"== {name}: {nv} vertices, {len(tris)} triangles, {ok.sum()} with a face normal")
    rows = []
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            m = n[:, perm] * np.array(sg)
            d = np.sum(m[ok] * vn[ok], 1)
            rows.append((np.median(d), np.mean(d > 0.8), np.mean(d < -0.8), perm, sg))
    rows.sort(key=lambda r: -abs(r[0]))
    for med, hi, lo, perm, sg in rows[:6]:
        tag = "  <- hakuX's decode" if perm == (0, 1, 2) and sg == (1, 1, 1) else ""
        print(f"   v1[{perm}] * {sg}: dot with face normal median {med:+.3f}, > 0.8 {hi:.1%}, < -0.8 {lo:.1%}{tag}")
    ident = [r for r in rows if r[3] == (0, 1, 2) and r[4] == (1, 1, 1)][0]
    print(f"   hakuX's decode: median {ident[0]:+.3f}, > 0.8 {ident[1]:.1%}, < -0.8 {ident[2]:.1%}")
    # R per vertex and its turn along edges
    C = p["C"]
    var = p["var"]
    R = var[:, 14:17]
    lr = np.linalg.norm(R, axis=1)
    Rn = R / np.maximum(lr, 1e-12)[:, None]
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    ang = np.degrees(np.arccos(np.clip(np.sum(Rn[e[:, 0]] * Rn[e[:, 1]], 1), -1, 1)))
    print(f"   |R| per vertex p10/50/90 {np.percentile(lr, [10, 50, 90]).round(2)}; "
          f"R turns along an edge p50/90/99 {np.percentile(ang, [50, 90, 99]).round(1)} deg")
    nn = n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    angn = np.degrees(np.arccos(np.clip(np.sum(nn[e[:, 0]] * nn[e[:, 1]], 1), -1, 1)))
    print(f"   v1 turns along an edge p50/90/99 {np.percentile(angn, [50, 90, 99]).round(1)} deg; "
          f"face normals' own turn across shared edges is the mesh's curvature")
