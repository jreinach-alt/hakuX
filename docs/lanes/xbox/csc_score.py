#!/usr/bin/env python3
"""Score the #10 colour-space-conversion run (csc-run.md) on one captures root.

    csc_score.py <captures root> [--controls <reference root>]

<captures root> is a console run's `console/` (Suite/Test.png) or a dispatcher
result's `captures1/` (Suite::Test.png). --controls names a root holding the
reference captures for leg K3 (PR #340's console run). Writes nothing.

Every test forces NV097_SET_CONTROL0's COLOR_SPACE_CONVERT field (CRYCB_TO_RGB)
on or off after PrepareDraw. The models are fixed here, before any data:

  csc()      hakuX util.h convert_ycbcr_to_rgb(), fitted on the texture-format
             goldens, with the red term's rounding constant kr = 128 (the #10
             Bump_map golden's (254,0,0) cell needs it; 127 and 128 differ only
             at Cr = 0).
  raw bump   psh.c's unflagged read: dS from B, dT from G, two's complement
             over 128, times the bump matrix (0.125) times 256 texels.

Legs (see csc-run.md for what each settles):
  K1  Palette_Off: all 256 cells are their texel, RGBA, exactly (the readout).
  K2  Stages_Tex1_Off: all cells are palette variant 1 exactly (four stages
      each sample their own texture).
  K3  (--controls) BumpMap_YUY2_L and BumpEnvLum_YUY2_L are pixel-identical to
      the reference console captures.
  K4  BumpS_Off / BumpT_Off: the displacement is the raw prediction, -16 / +16
      texels, within 1 (the offset readout).
  A1  Palette_On: exactly one Cb/Cr assignment reproduces every in-range cell
      (Y 42..209, Cb and Cr 17..238) exactly, alpha unchanged; and cell
      (254, 0, 0) reads (72, 255, 18).
  B1  Stages_Tex0/Tex1/Tex3_On: each is its own stage's palette, converted
      with A1's assignment (in-range cells exact).
  Q   reported, not predicted: the out-of-range cells; the raw YUY2/UYVY
      channel slots with the field off; YUY2/UYVY_On against hakuX's decode;
      the displacement with the field on (raw or converted source); the
      luminance model with the field on and off.
Exit 0 only if every K leg and A1 and B1 hold.
"""
import argparse
import itertools
import math
import os
import sys

import numpy as np
from PIL import Image

SUITE = "Color_space_conversion"

# --- the suite's literals (color_space_conversion_tests.cpp) ----------------
PAL_R = [0, 8, 16, 17, 32, 64, 96, 127, 128, 160, 192, 224, 235, 240, 254, 255]
PAL_GB = [(128, 128), (0, 0), (255, 255), (0, 255), (255, 0), (128, 0), (0, 128), (128, 255),
          (255, 128), (16, 240), (240, 16), (17, 238), (238, 17), (64, 192), (192, 64), (100, 150)]
PAL_A = [255, 191, 127, 64]
YUV = [(200, 60, 200, 130), (60, 130, 60, 200), (130, 200, 130, 60), (16, 128, 16, 128), (235, 128, 235, 128),
       (128, 128, 128, 128), (81, 90, 81, 240), (145, 54, 145, 34), (41, 240, 41, 110), (50, 90, 220, 170),
       (220, 170, 50, 90), (0, 0, 0, 0), (255, 255, 255, 255), (255, 0, 255, 0), (0, 255, 0, 255),
       (128, 0, 128, 255), (128, 255, 128, 0), (17, 238, 17, 17), (238, 17, 238, 238), (100, 150, 100, 50),
       (150, 50, 150, 150), (64, 192, 64, 64), (192, 64, 192, 192), (32, 96, 160, 224), (224, 160, 96, 32),
       (10, 20, 30, 40), (250, 240, 230, 220), (90, 128, 180, 128), (180, 128, 90, 128), (128, 16, 128, 128),
       (128, 128, 128, 16), (128, 240, 128, 240)]
BUMP_SRC = (128, 64, 192)          # kBumpSource 0xFF8040C0, (R, G, B)
LUM_SRC = (160, 96, 224)           # kLumSource 0xFFA060E0
BUMP_MAT = 0.125
PAL_LEFT, PAL_TOP, PAL_CELL = 128, 72, 24
YUV_LEFT, YUV_TOP = 64, 72
REF_LEFT, BUMP_LEFT, RAMP_TOP, RAMP = 48, 336, 96, 256


# --- models -----------------------------------------------------------------
def clip(x):
    return 0 if x < 0 else 255 if x > 255 else x


def csc(y, cb, cr, kr=128):
    c, d, e = y - 16, cb - 128, cr - 128
    luma = (298 * c - 96) >> 8
    return (clip(luma + 2 * ((409 * e + kr) >> 9)),
            clip(luma + 2 * ((-50 * d + 254) >> 8) + 2 * ((-104 * e + 248) >> 8) + 1),
            clip(luma + ((516 * d) >> 8)))


ASSIGN = {"Cb=G,Cr=B": lambda r, g, b: csc(r, g, b), "Cb=B,Cr=G": lambda r, g, b: csc(r, b, g)}


def texel(i, j, variant):
    if variant & 1:
        i = 15 - i
    if variant & 2:
        j = 15 - j
    g, b = PAL_GB[j]
    return (PAL_R[i], g, b, PAL_A[(i + j) & 3])


def in_range(r, g, b):
    return 42 <= r <= 209 and 17 <= g <= 238 and 17 <= b <= 238


def signed_offset(byte):
    return (byte - 256 if byte >= 128 else byte) / 128.0


# --- readout ----------------------------------------------------------------
def load(root, test, suite=SUITE):
    for p in (os.path.join(root, suite, test + ".png"), os.path.join(root, suite + "::" + test + ".png")):
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert("RGBA")).astype(int)
    return None


def block(img, x0, y0, x1, y1):
    """The block's value if every pixel in it is identical, else None."""
    b = img[y0:y1, x0:x1].reshape(-1, 4)
    return tuple(int(v) for v in b[0]) if (b == b[0]).all() else None


def palette_cells(img):
    out = {}
    for i, j in itertools.product(range(16), range(16)):
        cx, cy = PAL_LEFT + PAL_CELL * i + 12, PAL_TOP + PAL_CELL * j + 12
        out[(i, j)] = block(img, cx - 6, cy - 6, cx + 6, cy + 6)
    return out


def yuv_cells(img):
    out = {}
    for ci, cj in itertools.product(range(8), range(4)):
        ye, yo = YUV_TOP + 96 * cj + 28, YUV_TOP + 96 * cj + 68
        xe = YUV_LEFT + 64 * ci + 28      # texel 32ci + 14 (even): pixels xe, xe + 1
        out[(ci, cj)] = (block(img, xe, ye, xe + 2, yo), block(img, xe + 2, ye, xe + 4, yo))
    return out


def displacement(img, vertical):
    """Mean displacement, in texels, of the bumped quad against the ramp table."""
    line = lambda left, k: img[RAMP_TOP + k, left + RAMP // 2] if vertical else img[RAMP_TOP + RAMP // 2, left + k]
    table = {}
    for k in range(RAMP):
        table.setdefault(tuple(line(REF_LEFT, k)), []).append(k)
    shifts = []
    for k in range(RAMP):
        idx = table.get(tuple(line(BUMP_LEFT, k)))
        if not idx or len(idx) != 1:
            return None, "bumped pixel %d reads a colour the ramp holds %s times" % (k, len(idx or []))
        shifts.append(idx[0] + 0.5 - (64 + (k + 0.5) / 2))
    return float(np.mean(shifts)), "spread %.2f..%.2f" % (min(shifts), max(shifts))


# --- legs -------------------------------------------------------------------
def check_palette(cells, variant, fn, only_in_range=False):
    bad = []
    for (i, j), got in cells.items():
        r, g, b, a = texel(i, j, variant)
        if only_in_range and not in_range(r, g, b):
            continue
        want = (fn(r, g, b) if fn else (r, g, b)) + (a,)
        if got != want:
            bad.append(((i, j), (r, g, b, a), got, want))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--controls")
    a = ap.parse_args()
    ok = {}

    def img(test):
        m = load(a.root, test)
        if m is None:
            print("MISSING %s -- the run is void" % test)
            sys.exit(2)
        return m

    # K1
    pal_off = palette_cells(img("CSC_Palette_Off"))
    bad = check_palette(pal_off, 0, None)
    ok["K1"] = not bad
    print("K1 Palette_Off is the texels: %s" % ("holds" if ok["K1"] else "FAILS, %d of 256 cells, e.g. %s" % (len(bad), bad[:3])))

    # K2
    bad = check_palette(palette_cells(img("CSC_Stages_Tex1_Off")), 1, None)
    ok["K2"] = not bad
    print("K2 Stages_Tex1_Off is variant 1: %s" % ("holds" if ok["K2"] else "FAILS, %d cells, e.g. %s" % (len(bad), bad[:3])))

    # K3
    if a.controls:
        k3 = True
        for suite, test in (("Bump_map", "BumpMap_YUY2_L"), ("Bump_env_lum", "BumpEnvLum_YUY2_L")):
            got, ref = load(a.root, test, suite), load(a.controls, test, suite)
            same = got is not None and ref is not None and got.shape == ref.shape and (got == ref).all()
            diff = "missing" if got is None or ref is None else int((got != ref).any(axis=2).sum())
            print("K3 %s identical to the reference: %s" % (test, "holds" if same else "FAILS (%s px)" % diff))
            k3 = k3 and same
        ok["K3"] = k3

    # K4 and the displacement question
    raw = {False: 256 * BUMP_MAT * signed_offset(BUMP_SRC[2]), True: 256 * BUMP_MAT * signed_offset(BUMP_SRC[1])}
    conv = {name: fn(*BUMP_SRC) for name, fn in ASSIGN.items()}
    k4 = True
    for vertical, axis in ((False, "S"), (True, "T")):
        d_off, note = displacement(img("CSC_Bump%s_Off" % axis), vertical)
        holds = d_off is not None and abs(d_off - raw[vertical]) <= 1.0
        k4 = k4 and holds
        print("K4 Bump%s_Off displacement %s texels (%s), raw prediction %+.1f: %s" % (
            axis, "%+.2f" % d_off if d_off is not None else "unreadable", note, raw[vertical],
            "holds" if holds else "FAILS"))
        d_on, note = displacement(img("CSC_Bump%s_On" % axis), vertical)
        rivals = {"raw": raw[vertical]}
        for name, (r2, g2, b2) in conv.items():
            rivals["converted " + name] = 256 * BUMP_MAT * signed_offset(g2 if vertical else b2)
        fits = [k for k, v in rivals.items() if d_on is not None and abs(d_on - v) <= 1.0]
        print("Q  Bump%s_On displacement %s texels (%s); rivals %s -> fits: %s" % (
            axis, "%+.2f" % d_on if d_on is not None else "unreadable", note,
            {k: round(v, 2) for k, v in rivals.items()}, fits or "none"))
    ok["K4"] = k4

    # A1
    pal_on = palette_cells(img("CSC_Palette_On"))
    fitting = []
    for name, fn in ASSIGN.items():
        bad = check_palette(pal_on, 0, fn, only_in_range=True)
        n = sum(1 for (i, j) in pal_on if in_range(*texel(i, j, 0)[:3]))
        print("A1 Palette_On, %s: %d of %d in-range cells exact%s" % (name, n - len(bad), n, "" if not bad else ", e.g. %s" % bad[:2]))
        if not bad:
            fitting.append(name)
    cell = pal_on.get((14, 1))
    a1_cell = cell is not None and cell[:3] == (72, 255, 18)
    ok["A1"] = len(fitting) == 1 and a1_cell
    print("A1 cell (254,0,0) reads %s, predicted (72, 255, 18); one assignment fits: %s -> %s" % (
        cell, fitting or "none", "holds" if ok["A1"] else "FAILS"))
    assign = fitting[0] if len(fitting) == 1 else None
    fn = ASSIGN[assign] if assign else None

    # Q: every cell of Palette_On under the fitting assignment, kr 127 against 128
    if fn:
        for kr in (127, 128):
            f = (lambda r, g, b, kr=kr: csc(r, g, b, kr)) if assign == "Cb=G,Cr=B" else (lambda r, g, b, kr=kr: csc(r, b, g, kr))
            bad = check_palette(pal_on, 0, f)
            print("Q  Palette_On, all 256 cells, %s kr=%d: %d exact; off cells e.g. %s" % (assign, kr, 256 - len(bad), bad[:4]))
    bad_id = check_palette(pal_on, 0, None)
    print("Q  Palette_On cells equal to the unconverted texel: %d of 256" % (256 - len(bad_id)))

    # B1
    b1 = fn is not None
    for out_stage, variant in (("Tex0", 0), ("Tex1", 1), ("Tex3", 3)):
        cells = palette_cells(img("CSC_Stages_%s_On" % out_stage))
        n = sum(1 for (i, j) in cells if in_range(*texel(i, j, variant)[:3]))
        if fn:
            bad = check_palette(cells, variant, fn, only_in_range=True)
            holds = not bad
        else:
            bad, holds = [], False
        ident = 256 - len(check_palette(cells, variant, None))
        b1 = b1 and holds
        print("B1 Stages_%s_On: %s in-range cells converted (%s); %d of 256 cells unconverted" % (
            out_stage, "%d of %d" % (n - len(bad), n) if fn else "no assignment from A1", "holds" if holds else "FAILS", ident))
    ok["B1"] = b1

    # Q: YUV slots
    for fmt in ("YUY2", "UYVY"):
        off, on = yuv_cells(img("CSC_%s_Off" % fmt)), yuv_cells(img("CSC_%s_On" % fmt))
        unreadable = [k for k, v in off.items() if None in v] + [k for k, v in on.items() if None in v]
        if unreadable:
            print("Q  %s: non-uniform cells %s" % (fmt, unreadable[:6]))
        slots = {}
        for ch, chn in enumerate("RGBA"):
            cands = []
            for cand in ("Y", "U", "V", "Y0", "Y1", "0", "255"):
                good = True
                for (ci, cj), (even, odd) in off.items():
                    y0, u, y1, v = YUV[cj * 8 + ci]
                    for par, px in ((0, even), (1, odd)):
                        if px is None:
                            good = False
                            continue
                        want = {"Y": y0 if par == 0 else y1, "U": u, "V": v, "Y0": y0, "Y1": y1, "0": 0, "255": 255}[cand]
                        good = good and px[ch] == want
                if good:
                    cands.append(cand)
            slots[chn] = cands or ["other"]
        print("Q  %s_Off raw slots: %s" % (fmt, slots))
        same = all(off[k] == on[k] for k in off)
        print("Q  %s_Off equals %s_On in every cell: %s" % (fmt, fmt, same))
        for kr in (127, 128):
            exact = inr = inr_exact = 0
            for (ci, cj), (even, odd) in on.items():
                y0, u, y1, v = YUV[cj * 8 + ci]
                for y, px in ((y0, even), (y1, odd)):
                    want = csc(y, u, v, kr)
                    hit = px is not None and px[:3] == want
                    exact += hit
                    if 42 <= y <= 209 and 17 <= u <= 238 and 17 <= v <= 238:
                        inr += 1
                        inr_exact += hit
            print("Q  %s_On against hakuX's decode, kr=%d: %d of 64 texels exact (%d of %d in range)" % (fmt, kr, exact, inr_exact, inr))

    # Q: luminance
    for test in ("CSC_Lum_Off", "CSC_Lum_On"):
        cells = palette_cells(img(test))
        srcs = {"raw R": LUM_SRC[0], "raw G": LUM_SRC[1], "raw B": LUM_SRC[2]}
        for name, fnc in ASSIGN.items():
            r2, g2, b2 = fnc(*LUM_SRC)
            srcs.update({"conv R " + name: r2, "conv G " + name: g2, "conv B " + name: b2})
        quants = {"trunc": math.floor, "round": lambda x: int(math.floor(x + 0.5))}
        orders = {"none": None}
        orders.update({"convert after multiply " + k: ("after", f) for k, f in ASSIGN.items()})
        orders.update({"convert before multiply " + k: ("before", f) for k, f in ASSIGN.items()})
        results = []
        for (sname, L), (qname, q), den, (oname, order) in itertools.product(srcs.items(), quants.items(), (255, 256), orders.items()):
            s = L / den
            exact = 0
            for (i, j), got in cells.items():
                r, g, b, a_ = texel(i, j, 0)
                if order is None:
                    want = (q(r * s), q(g * s), q(b * s))
                elif order[0] == "after":
                    want = order[1](q(r * s), q(g * s), q(b * s))
                else:
                    c = order[1](r, g, b)
                    want = (q(c[0] * s), q(c[1] * s), q(c[2] * s))
                exact += got is not None and got[:3] == tuple(want) and got[3] == a_
            results.append((exact, sname, qname, den, oname))
        results.sort(reverse=True)
        print("Q  %s best luminance models (cells exact of 256): %s" % (test, [(e, s, q, "/%d" % d, o) for e, s, q, d, o in results[:4]]))

    verdict = all(ok.values())
    print("VERDICT: %s  (%s)" % ("all registered legs hold" if verdict else "a registered leg failed",
                                 ", ".join("%s %s" % (k, "ok" if v else "FAIL") for k, v in ok.items())))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
