#!/usr/bin/env python3
"""What the wide-line fix can reach, given the rasteriser's subpixel grid.

line_extent_phase.py derives the RULE silicon follows and shows it reproduces
the goldens' lit runs exactly.  This asks the next question, which is about the
IMPLEMENTATION rather than the rule: the geometry stage emits the footprint as
a parallelogram, and a GPU cannot place that parallelogram's corners more
finely than 1/2^subPixelPrecisionBits of a device pixel.  How much of the rule
survives that?

The answer decides how to read the arm.  A reading of 99.7% instead of 100% is
either "the phase is wrong" -- the near-miss values line-extent-phase-exact.json
registered in advance, 93.8 to 99.4 -- or "the phase is right and the device
cannot express it", and those call for opposite actions.

WHAT IS MODELLED, in the order the pipeline applies it:

  1. roundScreenCoords() in glsl/vsh.c truncates the endpoints to 1/16 px.
  2. emit_line() in glsl/geom.c offsets each corner by

         n = (w/2) * (max + min/2) / |d|^2 * (-dy, dx)

     which is the minor-axis extent E = w(max + min/2)/max resolved
     perpendicular to the edge, and adds the tie bias along the minor axis.
  3. The rasteriser quantises every emitted coordinate.  Because the endpoints
     are already on a 1/16 grid and the SAME offset is added at both ends, this
     TRANSLATES both long edges of the parallelogram by one constant vector
     rather than shearing them -- quantising p0 + n and p1 + n floors the same
     n.  So the band moves bodily by up to one quantum, and that is why the
     effect is a clean few-tenths-of-a-percent rather than noise.
  4. Coverage: pixel centre inside, under the named fill rule.

and the result is compared against the goldens' own observed runs, cut by cut,
exactly as line_extent_phase.py --vs-goldens will on the device.

MEASURED (defaults, against ~/goldens/results):

    subpixel grid       fit-set (of 8,890)    all widths (of 20,946)
    none (exact)        8,890  100.0000%      20,945  99.9952%
    1/4096 (12 bits)    8,890  100.0000%      20,945  99.9952%
    1/256  (8 bits)     8,868   99.7525%      20,903  99.7947%   closed rule
    1/256  (8 bits)     8,863   99.6963%      20,898  99.7708%   top-left rule
    1/16   (4 bits)     8,438    94.9%

so 100.0000% is NOT reachable at the 8 bits every device in this fleet reports,
and the shortfall is 166 of the goldens' 41,892 band edges that sit within
1/256 of a pixel centre without being on one.

AND THE BIAS HAS TO BE EXACTLY ONE QUANTUM, which --bias shows.  Below one the
rasteriser's own quantisation swallows it and the 1,888 band edges that land
EXACTLY on a pixel centre -- 4.507% of them -- go back to being decided by the
device's fill rule, which Vulkan does not specify: 1/512 scores 93.75% and
1/1024 scores 93.64%, against 93.41% for no bias at all.  Above one it starts
moving band edges that were right: 1/128 scores 99.28% and 1/64 scores 97.93%.

  --grid        the table above: every subpixel precision, both fill rules
  --bias        the bias sweep, at one precision
  --gaps        the distribution the whole thing turns on -- how close a band
                edge gets to a pixel centre without being on one
  --reconstruct whole-capture coverage for the emitted quad, against the
                derived rule and against the perpendicular rectangle
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import line_priority as lp
import line_extent_phase as lep

EPS = 1e-9


def corner_offsets(w, dx, dy, bias, q, mode):
    """The two corner offsets the shader emits, as the rasteriser stores them.

    Returns ((+n).major, (+n).minor, (-n).major, (-n).minor).
    """
    l2 = dx * dx + dy * dy
    adx, ady = abs(dx), abs(dy)
    k = (0.5 * w) * (max(adx, ady) + 0.5 * min(adx, ady)) / l2
    nx, ny = k * -dy, k * dx
    xmaj = adx >= ady
    nmaj, nmin = (nx, ny) if xmaj else (ny, nx)
    vals = [nmaj, nmin + bias, -nmaj, -nmin + bias]
    if q:
        f = np.floor if mode == "floor" else np.round
        vals = [float(f(v / q) * q) for v in vals]
    return vals


def band_at(row, w, bias, q, mode):
    """The two band edges at this cut's scanline, and the observed run."""
    (_t, _w, i, xmaj, line, a, b) = row
    (ax, ay), (bx, by) = lp.EDGES[i][3][0], lp.EDGES[i][4][0]
    ax, ay = lep.snap(ax), lep.snap(ay)
    bx, by = lep.snap(bx), lep.snap(by)
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return None
    pmaj, pmin, mmaj, mmin = corner_offsets(w, dx, dy, bias, q, mode)
    M = line + 0.5
    if xmaj:
        s = dy / dx
        e1 = (ay + pmin) + s * (M - (ax + pmaj))
        e2 = (ay + mmin) + s * (M - (ax + mmaj))
    else:
        s = dx / dy
        e1 = (ax + pmin) + s * (M - (ay + pmaj))
        e2 = (ax + mmin) + s * (M - (ay + mmaj))
    return (e1, e2) if e1 <= e2 else (e2, e1)


def covered(lo, hi, rule):
    if rule == "closed":
        return np.ceil(lo - 0.5 - EPS), np.floor(hi - 0.5 + EPS)
    if rule == "topleft":               # low edge in, high edge out
        return np.ceil(lo - 0.5 - EPS), np.ceil(hi - 0.5 - EPS) - 1
    raise ValueError(rule)


def score(rows, bias, rule, bits, scale=1, mode="floor"):
    q = (1.0 / (2 ** bits) / scale) if bits else 0.0
    ok = 0
    for row in rows:
        band = band_at(row, row[1], bias, q, mode)
        if band is None:
            continue
        pa, pb = covered(band[0], band[1], rule)
        if pa == row[5] and pb == row[6]:
            ok += 1
    return ok


def quantum(bits, scale=1):
    return 1.0 / (2 ** bits) / scale


def shader_mask(e, w, bits, scale=1, mode="floor"):
    """The pixels the emitted quad covers, for whole-capture coverage."""
    H, Wd = lp.H, lp.W
    q = quantum(bits, scale) if bits else 0.0
    (ax, ay), (bx, by) = e[3][0], e[4][0]
    ax, ay = lep.snap(ax), lep.snap(ay)
    bx, by = lep.snap(bx), lep.snap(by)
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return np.zeros((H, Wd), bool)
    pmaj, pmin, mmaj, mmin = corner_offsets(w, dx, dy, q, q, mode)
    if abs(dx) >= abs(dy):
        op, om = (pmaj, pmin), (mmaj, mmin)
    else:
        op, om = (pmin, pmaj), (mmin, mmaj)
    c = [(ax + op[0], ay + op[1]), (ax + om[0], ay + om[1]),
         (bx + op[0], by + op[1]), (bx + om[0], by + om[1])]

    CX, CY = lp.PX + 0.5, lp.PY + 0.5

    def band(p, r, s):
        ux, uy = r[0] - p[0], r[1] - p[1]
        L = float(np.hypot(ux, uy))
        if L == 0.0:
            return None
        nx, ny = -uy / L, ux / L
        d = (CX - p[0]) * nx + (CY - p[1]) * ny
        ds = (s[0] - p[0]) * nx + (s[1] - p[1]) * ny
        lo, hi = (0.0, ds) if ds >= 0 else (ds, 0.0)
        return (d >= lo) & (d <= hi)

    b1 = band(c[0], c[2], c[1])
    b2 = band(c[0], c[1], c[2])
    if b1 is None or b2 is None:
        return np.zeros((H, Wd), bool)
    return b1 & b2


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    ap.add_argument("--bits", type=int, default=8,
                    help="subPixelPrecisionBits the device reports")
    ap.add_argument("--scale", type=int, default=1,
                    help="surface_scale_factor; one guest px is this many "
                         "device px, so it divides the quantum")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--bias", action="store_true")
    ap.add_argument("--gaps", action="store_true")
    ap.add_argument("--reconstruct", action="store_true")
    a = ap.parse_args()

    if a.reconstruct:
        H, Wd = lp.H, lp.W
        tot = {"emitted quad": 0, "derived rule": 0, "perp rectangle": 0}
        n_ink = n_cap = n_exact = 0
        print(f"{'test':<14}{'w':>8}{'gold ink':>10}{'emitted':>10}"
              f"{'derived':>10}{'ours':>10}")
        for test, w, g in lp.captures(a.goldens, 0.125, 999.0):
            if test in lep.VOID:
                continue
            lit, valid = lep.ink(g)
            n_ink += int((lit & valid).sum())
            s = np.zeros((H, Wd), bool)
            u = np.zeros((H, Wd), bool)
            v = np.zeros((H, Wd), bool)
            for e in lp.EDGES:
                s |= shader_mask(e, w, a.bits, a.scale)
                u |= lep.edge_mask(e, w)
                v |= lep.ours_mask(e, w)
            sm = int(((s ^ lit) & valid).sum())
            d = int(((u ^ lit) & valid).sum())
            o = int(((v ^ lit) & valid).sum())
            tot["emitted quad"] += sm
            tot["derived rule"] += d
            tot["perp rectangle"] += o
            n_exact += (sm == 0)
            n_cap += 1
            print(f"{test:<14}{w:>8.3f}{int((lit & valid).sum()):>10}"
                  f"{sm:>10}{d:>10}{o:>10}")
        print(f"\n{n_cap} captures, {n_ink} golden ink px, {n_exact} "
              f"pixel-exact under the emitted quad at 1/{2 ** a.bits} subpixel")
        for k, v in tot.items():
            print(f"  {k:<16}{v:>8} mismatched px = {100 * v / n_ink:.4f}%")
        return

    fit = lep.cuts(a.goldens, 6.0, 999.0)
    allc = lep.cuts(a.goldens, 0.125, 999.0)
    print(f"fit-set cuts (widths 6-48): {len(fit)}   all widths: {len(allc)}")

    if a.gaps:
        T = lep.tabulate(allc)
        E, xm, ln, p, q_, _oa, _ob = T
        c = p + q_ * (ln + 0.5)
        d = np.concatenate([np.abs((c - E / 2 - 0.5) - np.round(c - E / 2 - 0.5)),
                            np.abs((c + E / 2 - 0.5) - np.round(c + E / 2 - 0.5))])
        # float noise around an exact tie is an exact tie
        tie = d < 1e-9
        print(f"\n{len(d)} band edges over {len(allc)} cuts")
        print(f"  exactly ON a pixel centre : {int(tie.sum())}  "
              f"({100 * tie.mean():.3f}%)  -- these need the low-open "
              f"tie-break, and no fill rule Vulkan permits gives it")
        nz = d[~tie]
        for name, thr in (("1/2048", 1 / 2048), ("1/1024", 1 / 1024),
                          ("1/512", 1 / 512), ("1/256", 1 / 256),
                          ("1/128", 1 / 128), ("1/64", 1 / 64),
                          ("1/32", 1 / 32)):
            n = int((nz < thr).sum())
            print(f"  non-zero gap < {name:<7}   : {n:6d}  "
                  f"({100 * n / len(d):.4f}%)  -- at risk from a quantum, or "
                  f"a bias, of this size")
        return

    if a.bias:
        q = quantum(a.bits, a.scale)
        print(f"\nbias sweep at subPixelPrecisionBits={a.bits}, "
              f"scale={a.scale} (one quantum = 1/{int(1 / q)} guest px)")
        print(f"{'bias':<10}{'rule':<10}{'fit %':>11}{'all %':>11}")
        for name, b in (("0", 0.0), ("q/4", q / 4), ("q/2", q / 2),
                        ("q", q), ("2q", 2 * q), ("4q", 4 * q),
                        ("16q", 16 * q)):
            for rule in ("closed", "topleft"):
                f = score(fit, b, rule, a.bits, a.scale)
                al = score(allc, b, rule, a.bits, a.scale)
                print(f"{name:<10}{rule:<10}{100 * f / len(fit):>10.4f}%"
                      f"{100 * al / len(allc):>10.4f}%")
        return

    # --grid, and the default
    print(f"\n{'subpixel':<12}{'rule':<10}{'fit %':>11}{'all %':>11}   "
          f"(bias = one quantum)")
    for bits in (0, 4, 8, 12, 16):
        q = quantum(bits, a.scale) if bits else 0.0
        # with no quantisation the bias only has to be smaller than the
        # smallest real gap; 1/2048 is well inside it
        b = q if bits else 1.0 / 2048
        for rule in ("closed", "topleft"):
            f = score(fit, b, rule, bits, a.scale)
            al = score(allc, b, rule, bits, a.scale)
            label = "exact" if not bits else f"1/{2 ** bits}"
            print(f"{label:<12}{rule:<10}{100 * f / len(fit):>10.4f}%"
                  f"{100 * al / len(allc):>10.4f}%")


if __name__ == "__main__":
    main()
