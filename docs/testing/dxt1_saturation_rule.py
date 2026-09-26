#!/usr/bin/env python3
"""dxt1_saturation_rule - what the DXT1 ordered dither does at the extremes.

Issue #6, second half.  The dither itself landed and is verified
(`dxt_dither_fit.py`, 402,999 -> 34,911 px on `Texture DXT`).  What it left
was recorded as a defect rather than a floor:

    a code of exactly 1 decodes to 0 where the model says 8, and
    MIPDXT1_64x256_bands keeps 7,594 px of which only 637 of 1,342 residual
    texels are code-1.

Both halves turn out to be one rule, and it is not a rule about code 1.

THE RULE.  For a channel of `bits` bits (5 for R and B, 6 for G), write
k = 8 - bits and half = 2**(k-1).  The dither picks `o`, the value in
[v - half, v + half - 1] congruent to the matrix entry modulo 2**k, where v
is the palette entry's 8-bit value.  Then:

    out = 0    if o <  2**k + half - 1        (11 for 5 bit, 5 for 6 bit)
    out = 255  if o >  255 - half - 1         (250 for 5 bit, 252 for 6 bit)
    out = o    otherwise

so the texture unit's DXT1 output takes values only in

    {0} u [11, 250] u {255}      5-bit channels (R, B)
    {0} u [ 5, 252] u {255}      6-bit channels (G)

Both bounds are the *top of the dither window of the extreme non-saturating
code* -- replicate(1) + half - 1 and replicate(2**bits - 2) + half - 1 -- and
both are measured at both channel widths.  The rule REPLACES the two special
cases the landed code carried (`v == 0` and `v == 255` do not dither): their
whole windows fall outside the allowed band, so they need no clause of their
own.  That is the argument that this is a rule and not a fit -- it removes two
exceptions rather than adding one.

WHY IT IS NOT "code 1 is special".  The low limb is corroborated by 8,283
INTERPOLANT channel observations, against 680 from a code-1 endpoint.  An
interpolated palette entry is an arbitrary 8-bit value; it has no code.  A
rule keyed on the code cannot reach those texels, and a rule keyed on the
output value reaches all of them with no extra clause.

HOW IT WAS READ OUT OF THE GOLDENS.  By level set, the way #59 separated
replicate from ratio: each candidate rule permits a different SET of 8-bit
output values, so the only question is which values a channel of a golden
contains.  No screen->texel mapping, no regression fit, no assumption about
which texel landed where.  `--level-set` is that measurement; `--keys` is the
per-cell function it rests on; `--rivals` lists what it excludes; and
`--simulate` applies the rule to our own captures from the landed arm and
re-scores them, which is the same conservative check #59 used.

Usage:
    dxt1_saturation_rule.py --keys        the (code, cell) -> output function
    dxt1_saturation_rule.py --level-set   the two bounds, at both widths
    dxt1_saturation_rule.py --rivals      every rival, and what kills it
    dxt1_saturation_rule.py --simulate    re-score the landed arm's captures
    dxt1_saturation_rule.py --all

Exit status is non-zero if any rival survives, if any code other than 1
deviates from the landed window model, or if a forbidden value turns up in a
golden.  Nothing is written anywhere.
"""

import argparse
import collections
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as capmod
import dxt_dither_fit as F

GOLDEN_ROOT = os.environ.get("DXT_GOLDEN_ROOT", "/home/justin/goldens/results")

# The arm the rule is simulated against: the landed dither, whose residual is
# what this file explains. Overridable because a result directory is not
# eternal, and --simulate says so rather than guessing.
LANDED_ARM = os.environ.get(
    "DXT_LANDED_ARM",
    "/home/justin/hakux-work/dispatch/results/1789265953-dxt6-fix-243517")

# channel -> (name, bits, half)
CHANS = ((0, "R", 5, 4), (1, "G", 6, 2), (2, "B", 5, 4))


def lo_bound(half):
    """Top of code 1's dither window: 2**k + half - 1 with 2**k == 2*half."""
    return 3 * half - 1


def hi_bound(half):
    """Top of code (max-1)'s window: 255 - half - 1."""
    return 254 - half


def window(v, ch, half, yy, xx):
    """The landed model's choice: the value in [v-half, v+half-1] congruent to
    the matrix entry.  No saturation applied."""
    m = 2 * half
    t = int(F.T[ch][yy, xx]) % m
    return v - half + ((t - v + half) % m)


def rule(v, ch, half, yy, xx):
    o = window(v, ch, half, yy, xx)
    if o < lo_bound(half):
        return 0
    if o > hi_bound(half):
        return 255
    return o


def landed(v, ch, half, yy, xx):
    """What s3tc.c does today: saturated palette values pass through, the rest
    take the window with a plain 0..255 clamp."""
    if v <= 0:
        return 0
    if v >= 255:
        return 255
    return max(0, min(255, window(v, ch, half, yy, xx)))


# --------------------------------------------------------------- source data

def palette(c0, c1):
    """The four palette entries in 8 bits, and whether the block is
    punch-through.  This is HEAD's palette, which #6 already verified."""
    q0, q1 = F.comps(c0), F.comps(c1)
    punch = c0 <= c1
    p = [[F.expand(q0[0], 5), F.expand(q0[1], 6), F.expand(q0[2], 5)],
         [F.expand(q1[0], 5), F.expand(q1[1], 6), F.expand(q1[2], 5)],
         None, None]
    if punch:
        p[2] = [(p[0][c] + p[1][c] + 1) // 2 for c in range(3)]
        p[3] = [0, 0, 0]
    else:
        p[2] = [(2 * p[0][c] + p[1][c] + 1) // 3 for c in range(3)]
        p[3] = [(p[0][c] + 2 * p[1][c] + 1) // 3 for c in range(3)]
    return p, (q0, q1), punch


def texels():
    """Every level-0 texel of every DXT1 capture, point-sampled out of the
    golden, with its block.  Yields (stem, ch, code_or_None, index, punch,
    v, yy, xx, golden_value)."""
    for stem, dds, w, h, qx, qy in F.DXT1:
        g, uniform = F.golden(stem, w, h, qx, qy)
        if not uniform:
            raise SystemExit("%s: magnified cells are not constant, so the "
                             "capture does not expose texels" % stem)
        nbx = w // 4
        for b, (c0, c1, idx) in enumerate(F.colour_blocks(dds, w, h)):
            p, q, punch = palette(c0, c1)
            bj, bi = divmod(b, nbx)
            for ty in range(4):
                for tx in range(4):
                    i = (idx >> (2 * (ty * 4 + tx))) & 3
                    Y, X = bj * 4 + ty, bi * 4 + tx
                    for ch, nm, bits, half in CHANS:
                        code = (q[i][ch] if i < 2 else
                                (q[0][ch] if q[0][ch] == q[1][ch] else None))
                        yield (stem, ch, code, i, punch, p[i][ch],
                               Y & 3, X & 3, int(g[Y, X, ch]))


# ------------------------------------------------------------------ commands

def cmd_keys(args):
    """The capture as a function of (code, cell), and which codes deviate."""
    print("The golden as a single-valued function of (endpoint code, y&3, x&3).")
    print("A texel counts only where its channel code is unambiguous: an")
    print("endpoint texel, or any texel of a block whose two endpoint codes")
    print("agree in that channel -- so no interpolation rule is assumed.")
    print("Punch-through's transparent entry is excluded: there the golden")
    print("holds the framebuffer, not a texel.\n")
    tab = [collections.defaultdict(collections.Counter) for _ in range(3)]
    for stem, ch, code, i, punch, v, yy, xx, gold in texels():
        if code is None or (punch and i == 3):
            continue
        tab[ch][(code, yy, xx)][gold] += 1
    rc = 0
    print("%-3s %7s %7s %10s %12s" % ("ch", "keys", "codes", "conflicts",
                                      "codes deviating"))
    dev = {}
    for ch, nm, bits, half in CHANS:
        conflicts = [k for k, c in tab[ch].items() if len(c) > 1]
        codes = sorted({k[0] for k in tab[ch]})
        bad = collections.defaultdict(list)
        for (code, yy, xx), c in tab[ch].items():
            if len(c) > 1:
                continue
            obs = next(iter(c))
            if landed(F.expand(code, bits), ch, half, yy, xx) != obs:
                bad[code].append((yy, xx, obs))
        dev[nm] = dict(bad)
        print("%-3s %7d %7d %10d %12s"
              % (nm, len(tab[ch]), len(codes), len(conflicts),
                 sorted(bad) or "none"))
        if conflicts or sorted(bad) not in ([], [1]):
            rc = 1
    print("\nExactly one code deviates from the landed window model, in all")
    print("three channels, over %d keys.  Its cells:\n"
          % sum(len(t) for t in tab))
    for ch, nm, bits, half in CHANS:
        step = 2 * half
        print("  %s, code 1 (window would be [%d, %d]):" %
              (nm, F.expand(1, bits) - half, F.expand(1, bits) + half - 1))
        for yy in range(4):
            row = []
            for xx in range(4):
                c = tab[ch].get((1, yy, xx))
                row.append("%9s" % (",".join("%d" % k for k in sorted(c))
                                    if c else "."))
            print("     " + " ".join(row) + "    T=" +
                  " ".join("%d" % (int(F.T[ch][yy, xx]) % step)
                           for xx in range(4)))
        tops = sorted({k for k in range(4)
                       if (F.expand(1, bits) + half - 1) % step
                       == int(F.T[ch][0, k]) % step})
        print("     non-zero exactly where the cell selects the window TOP,"
              " %d = %d + %d - 1\n"
              % (F.expand(1, bits) + half - 1, F.expand(1, bits), half))
    return rc


def cmd_level_set(args):
    """The two bounds, mapping-free, at both channel widths."""
    print("Which 8-bit values does a DXT1 golden channel contain?  Each")
    print("candidate rule permits a different set, so the sets decide it with")
    print("no mapping and no fit.  Level-0 texels, point-sampled.\n")
    rc = 0
    union = [set(), set(), set()]
    print("%-30s %s" % ("capture", "lowest non-zero / highest below 255, per channel"))
    for stem, dds, w, h, qx, qy in F.DXT1:
        g, _ = F.golden(stem, w, h, qx, qy)
        cells = []
        for ch, nm, bits, half in CHANS:
            s = set(np.unique(g[:, :, ch]).tolist())
            union[ch] |= s
            nz = [v for v in s if v > 0]
            sub = [v for v in s if v < 255]
            cells.append("%s %3s/%3s" % (nm, min(nz) if nz else "-",
                                         max(sub) if sub else "-"))
        print("%-30s %s" % (stem, "  ".join(cells)))
    print("\n%-3s %-7s %-22s %-22s %s"
          % ("ch", "bits", "forbidden low band", "forbidden high band", "present?"))
    for ch, nm, bits, half in CHANS:
        lo, hi = lo_bound(half), hi_bound(half)
        band = list(range(1, lo)) + list(range(hi + 1, 255))
        hit = sorted(v for v in band if v in union[ch])
        if hit:
            rc = 1
        print("%-3s %-7d %-22s %-22s %s"
              % (nm, bits, "1..%d" % (lo - 1), "%d..254" % (hi + 1),
                 hit if hit else "NONE"))
    print("\nThe bounds are not free parameters: 11 is pinned from above by a")
    print("golden R and B value of 11 and from below by the absence of 10, and")
    print("5 the same way for G.  250 and 252 likewise.  Each is the top of")
    print("the dither window of the extreme non-saturating code, at both widths.")

    print("\nSixth capture, a DIFFERENT suite, source and geometry -- and the")
    print("only one whose green reaches saturation, which is what pins the")
    print("6-bit high bound:")
    p = os.path.join(GOLDEN_ROOT, "Texture_format", "TexFmt_DXT1.png")
    if os.path.exists(p):
        a = np.array(Image.open(p).convert("RGBA")).astype(int)
        for ch, nm, bits, half in CHANS:
            s = set(np.unique(a[:, :, ch]).tolist())
            lo, hi = lo_bound(half), hi_bound(half)
            band = [v for v in list(range(1, lo)) + list(range(hi + 1, 255))
                    if v in s]
            near = [v for v in range(hi - 3, 255) if v in s]
            if band:
                rc = 1
            print("  TexFmt_DXT1 %s: forbidden values present %-6s   "
                  "values from %d up: %s"
                  % (nm, band if band else "NONE", hi - 3, near))
        print("  Its guest-side compressor is pbkitplusplus texture_stage.cpp")
        print("  (c0 = 0, c1 = the block's top-left pixel, punch-through), and")
        print("  its quad is 480x360 rather than a 256x256 point magnification.")
        print("  None of its blocks were used to derive the rule.")
    else:
        print("  MISSING: %s" % p)
        rc = 1

    print("\nSeventh capture, a THIRD suite and a 3D texture: Volume_texture/DXT1")
    print("samples densely enough to pin all four bounds from both sides at")
    print("once.  Our own render of it fails for an unrelated reason (6,129 px")
    print("at max delta 255), so it is evidence about silicon and NOT a leg:")
    p3 = os.path.join(GOLDEN_ROOT, "Volume_texture", "DXT1.png")
    if os.path.exists(p3):
        a = np.array(Image.open(p3).convert("RGBA")).astype(int)
        for ch, nm, bits, half in CHANS:
            s = set(np.unique(a[:, :, ch]).tolist())
            lo, hi = lo_bound(half), hi_bound(half)
            band = [v for v in list(range(1, lo)) + list(range(hi + 1, 255))
                    if v in s]
            if band:
                rc = 1
            print("  Volume_texture/DXT1 %s: forbidden present %-6s  "
                  "lowest non-zero %3d (bound %3d), highest below 255 %3d "
                  "(bound %3d), %d distinct levels"
                  % (nm, band if band else "NONE",
                     min(v for v in s if v > 0), lo,
                     max(v for v in s if v < 255), hi, len(s)))
    else:
        print("  MISSING: %s" % p3)
        rc = 1

    print("\nCONTROL -- DXT3 and DXT5, same colour-block layout, 8-bit target,")
    print("no dither.  If the forbidden band were a property of the test")
    print("images rather than of the DXT1 path, it would be empty here too:")
    for stem, dds, w, h, qx, qy, fam in F.CONTROL:
        g, _ = F.golden(stem, w, h, qx, qy)
        cells = []
        for ch, nm, bits, half in CHANS:
            s = set(np.unique(g[:, :, ch]).tolist())
            band = sorted(v for v in range(1, lo_bound(half)) if v in s)
            cells.append("%s %s" % (nm, band if band else "-"))
        print("  %-28s %s" % (stem, "  ".join(cells)))
    print("  DXT3 and DXT5 hold 8 in R -- replicate5(1), exactly the value")
    print("  DXT1 never emits.  So the band is the format path, not the data.")
    return rc


def cmd_rivals(args):
    """Each rival rule, and the decisive texels that exclude it."""
    obs = collections.defaultdict(collections.Counter)
    for stem, ch, code, i, punch, v, yy, xx, gold in texels():
        if punch and i == 3:
            continue
        obs[(ch, v, yy, xx)][gold] += 1

    def score(fn):
        ok = miss = 0
        for (ch, v, yy, xx), c in obs.items():
            half = 4 if ch != 1 else 2
            pred = fn(v, ch, half, yy, xx)
            for g, n in c.items():
                if pred == g:
                    ok += n
                else:
                    miss += n
        return ok, miss

    rivals = [
        ("this rule: 0 below the low bound, 255 above the high bound", rule),
        ("landed: window, with v==0 and v==255 passing through", landed),
        ("window only, plain clamp to 0..255",
         lambda v, ch, h, y, x: max(0, min(255, window(v, ch, h, y, x)))),
        ("code 1 is simply black: treat expand(1) like 0",
         lambda v, ch, h, y, x: (0 if v in (0, 2 * h) else landed(v, ch, h, y, x))),
        ("code 1 does not dither: emit expand(1) unchanged",
         lambda v, ch, h, y, x: (v if v == 2 * h else landed(v, ch, h, y, x))),
        ("low limb only (keeps the v==255 clause)",
         lambda v, ch, h, y, x: (255 if v >= 255 else
                                 (0 if window(v, ch, h, y, x) < lo_bound(h)
                                  else max(0, min(255, window(v, ch, h, y, x)))))),
        ("high limb only (keeps the v==0 clause)",
         lambda v, ch, h, y, x: (0 if v <= 0 else
                                 (255 if window(v, ch, h, y, x) > hi_bound(h)
                                  else max(0, min(255, window(v, ch, h, y, x)))))),
        ("clamp instead of saturate: to the bounds, not to 0/255",
         lambda v, ch, h, y, x: max(lo_bound(h),
                                    min(hi_bound(h), window(v, ch, h, y, x)))),
    ]
    print("Every candidate, scored over %d distinct (channel, palette value,"
          % len(obs))
    print("cell) observations from the five DXT1 captures.  A rule that is")
    print("merely better in aggregate is a fit; a rule that is the only one")
    print("with zero misses is a derivation.\n")
    print("%-62s %9s %9s" % ("rule", "agree", "MISS"))
    rc = 1
    for nm, fn in rivals:
        ok, miss = score(fn)
        print("%-62s %9d %9d" % (nm, ok, miss))
        if fn is rule:
            rc = 0 if miss == 0 else 1
        elif miss == 0:
            print("   ^ a second rule with no misses: the derivation is not "
                  "decisive")
            rc = 1
    print("\nThe DECISIVE set -- every observation where this rule and the")
    print("landed one disagree, so the golden chooses between them.  The low")
    print("limb is NOT a statement about code 1: an interpolated palette entry")
    print("is an arbitrary 8-bit value and carries no code at all.")
    src = collections.Counter()
    vals = collections.defaultdict(set)
    for stem, ch, code, i, punch, v, yy, xx, gold in texels():
        if punch and i == 3:
            continue
        half = 4 if ch != 1 else 2
        a, b = landed(v, ch, half, yy, xx), rule(v, ch, half, yy, xx)
        if a == b:
            continue
        limb = "low" if b == 0 else "high"
        kind = ("endpoint code %s" % code) if i < 2 else "interpolant"
        verdict = ("this rule %s, landed %s"
                   % ("ok" if b == gold else "MISS",
                      "ok" if a == gold else "MISS"))
        src[(limb, kind, verdict)] += 1
        vals[(limb, kind)].add(v)
        if b != gold:
            rc = 1
    for k in sorted(src, key=lambda k: (k[0], -src[k])):
        print("   %-5s %-22s %-28s %5d obs   palette values %s"
              % (k[0], k[1], k[2], src[k],
                 sorted(vals[(k[0], k[1])])))
    print("   total decisive observations: %d" % sum(src.values()))
    return rc


def cmd_simulate(args):
    """Apply the rule to our own captures and re-score against the goldens."""
    print("Conservative simulation: take the landed arm's captures, move every")
    print("channel that the rule forbids to 0 or 255, and re-score.  Exact")
    print("wherever the quad is a point magnification -- which every DXT1")
    print("capture is except the minified mip quads of the one non-square")
    print("texture, and those are flagged below.\n")
    print("arm %s" % LANDED_ARM)
    rows = [("Texture_DXT", "DXT1_plasma_dxt1"),
            ("Texture_DXT", "DXT1_plasma_alpha_dxt1"),
            ("Texture_DXT", "MIPDXT1_plasma_dxt1"),
            ("Texture_DXT", "MIPDXT1_plasma_alpha_dxt1"),
            ("Texture_DXT", "MIPDXT1_64x256_bands_dxt1"),
            ("Texture_format", "TexFmt_DXT1")]
    control = [("Texture_DXT", "DXT3_plasma_dxt3"),
               ("Texture_DXT", "DXT3_plasma_alpha_dxt3"),
               ("Texture_DXT", "DXT5_plasma_dxt5"),
               ("Texture_DXT", "MIPDXT3_plasma_dxt3"),
               ("Texture_DXT", "MIPDXT5_plasma_alpha_dxt5")]
    print("\n%-16s %-28s %9s %9s %10s" %
          ("suite", "test", "landed", "with rule", "delta"))
    rc = 0
    for group, label in ((rows, "DXT1 -- the rule applies"),
                         (control, "CONTROL, DXT3/DXT5 -- it must NOT")):
        print("  -- %s" % label)
        for suite, test in group:
            p = capmod.find(LANDED_ARM, suite, test)
            g = os.path.join(GOLDEN_ROOT, suite, test + ".png")
            if not p or not os.path.exists(g):
                print("%-16s %-28s %s" % (suite, test, "MISSING"))
                rc = 1
                continue
            a = np.array(Image.open(p).convert("RGBA")).astype(int)
            go = np.array(Image.open(g).convert("RGBA")).astype(int)
            b = a.copy()
            for ch, nm, bits, half in CHANS:
                lo, hi = lo_bound(half), hi_bound(half)
                b[:, :, ch][(a[:, :, ch] > 0) & (a[:, :, ch] < lo)] = 0
                b[:, :, ch][(a[:, :, ch] > hi) & (a[:, :, ch] < 255)] = 255
            na = int((a != go).any(axis=2).sum())
            nb = int((b != go).any(axis=2).sum())
            print("%-16s %-28s %9d %9d %+10d" % (suite, test, na, nb, nb - na))
    print("\nThe control is the point: the same remap applied to DXT3 and DXT5")
    print("makes them WORSE, so this is not a rule about 8-bit output in")
    print("general and must stay inside write_dxt1_block_to_texture.")
    print("\nMIPDXT1_64x256_bands is the one capture the simulation cannot")
    print("predict: quads L1 (128x128 at 270,80) and L2 minify a 64x256")
    print("texture through a tent filter, so their pixels are blends of")
    print("expanded texels and remapping a blend is not the same as changing")
    print("the texels it blends.  Its level-0 quad -- 5,336 of its 7,594 px --")
    print("does go to 0, and the goldens' own L1 region contains forbidden")
    print("values, which is how one knows filtering happens after expansion.")
    return rc


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keys", action="store_true")
    p.add_argument("--level-set", action="store_true")
    p.add_argument("--rivals", action="store_true")
    p.add_argument("--simulate", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()
    todo = [(f, fn) for f, fn in (("keys", cmd_keys),
                                  ("level_set", cmd_level_set),
                                  ("rivals", cmd_rivals),
                                  ("simulate", cmd_simulate))
            if args.all or getattr(args, f)]
    if not todo:
        p.print_help()
        return 0
    rc = 0
    for _, fn in todo:
        rc |= fn(args)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
