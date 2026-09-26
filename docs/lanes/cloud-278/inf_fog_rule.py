#!/usr/bin/env python3
"""#278: score silicon's INF/NaN fog-coordinate rule per quad against the goldens
and against our captures.

The INF-/NaN-FogExc tests (nxdk_pgraph_tests fog_exceptional_value_tests.cpp,
TestParams) draw 24 quads, 4 bias rows {-1, 1, 1.5, 1000} x 6 multiplier columns
{Lin, Exp, Exp2, 1, 0, -1000}, with the fog coordinate held at +INF (0x7F800000)
or +qNaN (0x7FC00000). Fog colour is pure red, so a quad is either fogged
(f = 0 -> #FF0000) or unfogged (f = 1 -> the diffuse gradient).

Models scored, per quad:
  current  -- psh.c today: any INF/NaN coordinate -> fixed special
              (linear, linear_abs, exp: 1; exp_abs, exp2, exp2_abs: 0).
  rule278  -- silicon: NaN -> the same special. INF -> the same special, EXCEPT
              in the four exp modes when the multiplier is exactly 0, where
              0 * INF = 0 and the ordinary formula runs on x = bias - 1.5.

Usage: inf_fog_rule.py [CAPTURE_DIR ...]   (dirs holding Fog_exceptional_value::*.png)
"""
import os
import sys

from PIL import Image

GOLD = os.environ.get("GOLDENS", "/home/justin/goldens/results") + "/Fog_exceptional_value"
XS = [48, 136, 224, 312, 400, 488]
YS = [70, 172, 274, 376]
BIAS = [-1.0, 1.0, 1.5, 1000.0]
MULT = [-1.0 / 199.0, -0.025 / (2 * 5.5452), -0.025 / (2 * 2.3548), 1.0, 0.0, -1000.0]
MODES = ["linear", "linear_abs", "exp", "exp_abs", "exp2", "exp2_abs"]
GENS = ["planar", "abs_planar", "fog_x", "spec_alpha"]
SPECIAL = {"linear": 1, "linear_abs": 1, "exp": 1, "exp_abs": 0, "exp2": 0, "exp2_abs": 0}


def exp_factor(mode, x):
    if mode == "exp":
        e = 16 * x
    elif mode == "exp_abs":
        e = -16 * abs(x)
    else:
        e = -32 * x * x
    e = max(min(e, 64.0), -1000.0)
    return min(max(2.0 ** e, 0.0), 1.0)


def model(name, kind, mode, bias, m):
    if name == "current" or kind == "NaN" or mode.startswith("linear") or m != 0.0:
        return SPECIAL[mode]
    f = exp_factor(mode, bias - 1.5)  # 0 * INF = 0
    # A class, not a value: f is 0, 1 or 2^-8 here (see NOTES for the 2^-8 cell).
    return 1 if f >= 0.5 else 0


def cls(im, x, y):
    ps = [im.getpixel((x + a, y + b))[:3] for a in (8, 32, 56) for b in (8, 32, 56)]
    if all(p == (255, 0, 0) for p in ps):
        return 0
    if all(p[1] + p[2] > 100 for p in ps):
        return 1
    return None


def structural(a, b, box):
    x0, y0, x1, y1 = box
    pa, pb = a.load(), b.load()
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if max(abs(i - j) for i, j in zip(pa[x, y], pb[x, y])) > 1:
                n += 1
    return n


def grid_str(gc):
    return " ".join("".join("u" if v == 1 else "F" if v == 0 else "?" for v in row) for row in gc)


def main():
    print("== goldens vs models (24 quads per capture; rows bias -1,1,1.5,1k; cols m Lin,Exp,Exp2,1,0,-1k) ==")
    for kind in ["INF", "NaN"]:
        for mode in MODES:
            for gen in GENS:
                g = Image.open("%s/%s-FogExc-%s-%s.png" % (GOLD, kind, mode, gen)).convert("RGB")
                gc = [[cls(g, x, y) for x in XS] for y in YS]
                sc = {}
                for mdl in ["current", "rule278"]:
                    sc[mdl] = sum(gc[r][c] == model(mdl, kind, mode, BIAS[r], MULT[c])
                                  for r in range(4) for c in range(6))
                print("%s %-10s %-10s golden %s  current %2d/24  rule278 %2d/24"
                      % (kind, mode, gen, grid_str(gc), sc["current"], sc["rule278"]))
    for cap in sys.argv[1:]:
        print("\n== captures: %s ==" % cap)
        tot_all = tot_fixed = 0
        for kind in ["INF", "NaN"]:
            for mode in MODES:
                for gen in GENS:
                    fn = "%s/Fog_exceptional_value::%s-FogExc-%s-%s.png" % (cap, kind, mode, gen)
                    if not os.path.exists(fn):
                        continue
                    g = Image.open("%s/%s-FogExc-%s-%s.png" % (GOLD, kind, mode, gen)).convert("RGB")
                    o = Image.open(fn).convert("RGB")
                    whole = structural(g, o, (0, 0, 640, 480))
                    oc = [[cls(o, x, y) for x in XS] for y in YS]
                    ours_ok = sum(oc[r][c] == model("current", kind, mode, BIAS[r], MULT[c])
                                  for r in range(4) for c in range(6))
                    moved, fixed_px = [], 0
                    for r in range(4):
                        for c in range(6):
                            if model("current", kind, mode, BIAS[r], MULT[c]) != model("rule278", kind, mode, BIAS[r], MULT[c]):
                                px = structural(g, o, (XS[c], YS[r], XS[c] + 64, YS[r] + 64))
                                moved.append("b%g/m0:%d" % (BIAS[r], px))
                                fixed_px += px
                    print("%s %-10s %-10s structural %6d  ours %s (==current model %2d/24)  flipped: %s  residual %d"
                          % (kind, mode, gen, whole, grid_str(oc), ours_ok, " ".join(moved) or "-", whole - fixed_px))
                    if kind == "INF" and not mode.startswith("linear"):
                        tot_all += whole
                        tot_fixed += fixed_px
        print("INF exp-family: structural %d, inside rule278's flipped quads %d, residual %d"
              % (tot_all, tot_fixed, tot_all - tot_fixed))


if __name__ == "__main__":
    main()
