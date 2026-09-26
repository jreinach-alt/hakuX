"""Per vertex: which candidate value does silicon's fitted depth match?"""
import os
import sys
from fractions import Fraction as F
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from dbff import render, zeta_word, GOLD, primitives  # noqa: E402
from model import rnd, C22, C32  # noqa: E402
from vfit import fit, RTZ  # noqa: E402


def ulp_of(x, bits=24):
    return rnd(x, 'rtz', bits) - rnd(x * (1 - F(1, 2 ** 40)), 'rtz', bits) if x else 0


def cands(z):
    z = F(float(z))
    p = rnd(z * C22, 'rtz')
    zc = rnd(p + C32, 'rtz')
    w = rnd(z + 7, 'rtz')
    r = rnd(1 / w, 'rtz')
    ur = r - rnd(r * (1 - F(1, 2 ** 30)), 'rtz')  # one ulp of r
    q0 = rnd(zc * r, 'rtz')
    q_r1 = rnd(zc * (r - ur), 'rtz')
    uq = q0 - rnd(q0 * (1 - F(1, 2 ** 30)), 'rtz')
    q_f1 = q0 - uq
    return dict(q0=q0, q_r1=q_r1, q_f1=q_f1, rrem=float((1 / w - r) / ur), w=w,
                qrem=float((zc * r - q0) / uq))


names = sys.argv[1:] or ["z24_Cn_FZn_Mffffff_ZB", "z24_Cy_FZn_Mffffff_ZB"]
prims = primitives()
acc = {}
for name in names:
    cutoff = int(name.split("_M")[1].split("_")[0], 16)
    g = zeta_word(os.path.join(GOLD, name + ".png"))
    _, pid = render(RTZ, cutoff, tag=True)
    for n, za, zb, a, b, nk in fit(g, pid, prims):
        for z, v in ((za, a), (zb, b)):
            acc.setdefault(float(z), []).append(v)
rows = []
for z, vs in sorted(acc.items()):
    c = cands(z)
    v = float(np.median(vs))
    rows.append((float(c['w']), v - float(c['q0']), v - float(c['q_r1']), v - float(c['q_f1']),
                 c['rrem'], c['qrem'], float(c['q0'])))
rows = np.array(rows)
tol = 0.35
m0 = np.abs(rows[:, 1]) < tol
mr = np.abs(rows[:, 2]) < tol
mf = np.abs(rows[:, 3]) < tol
print("n=%d  match q0 %d, r-1ulp %d, q-1ulp %d, none %d" % (
    len(rows), m0.sum(), mr.sum(), mf.sum(), (~m0 & ~mr & ~mf).sum()))
print("where q0 fails but r-1ulp matches: rrem median %.3f (all %.3f); r-1ulp differs from q0 there by %.2f" % (
    np.median(rows[~m0 & mr, 4]) if (~m0 & mr).any() else -1, np.median(rows[:, 4]),
    np.median(rows[~m0 & mr, 2] - rows[~m0 & mr, 1]) if (~m0 & mr).any() else 0))
# rrem histogram split by match
for lo in np.arange(0, 1.0, 0.1):
    s = (rows[:, 4] >= lo) & (rows[:, 4] < lo + 0.1)
    print("rrem [%.1f,%.1f): n=%3d  q0-match %.2f  r1-match %.2f  mean(v-q0) %.2f" % (
        lo, lo + 0.1, s.sum(), m0[s].mean() if s.any() else 0, mr[s].mean() if s.any() else 0,
        rows[s, 1].mean() if s.any() else 0))
nm = ~m0 & ~mr & ~mf
print("unexplained:")
for r in rows[nm][:30]:
    print("  w=%9.4f v-q0=%6.2f v-qr1=%6.2f v-qf1=%6.2f rrem=%.3f qrem=%.3f q=%.1f" % tuple(r))
