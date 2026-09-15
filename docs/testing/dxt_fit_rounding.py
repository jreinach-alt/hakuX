#!/usr/bin/env python3
"""dxt_fit_rounding - fit the NV2A's DXT rounding rules against silicon.

DXT decode is pure arithmetic with no device state, so the rule the hardware
uses can be *fitted* offline instead of guessed: decode the same .dds the test
loads, compare against the golden framebuffer capture from XBOX 1.0 hardware,
and score every candidate rounding rule by exact-channel count.  No emulator
build and no device are involved, which is why this can enumerate rivals
instead of confirming a favourite.

Fits hw/xbox/nv2a/pgraph/s3tc.c.  Issue #6.


The geometry that makes the comparison exact
--------------------------------------------
Texture_DXT's non-mipmap tests upload a 32x32 compressed image and draw it
into a 256x256 screen-aligned quad with texcoords 0..1, so each texel lands
on exactly one 8x8 pixel cell of the capture.  --check-geometry verifies
every cell is constant rather than assuming it: that is what proves the
sampling is point, not filtered, and gives one golden value per texel.

The quad is centred in the 640x480 framebuffer: x 192..447, y 112..367.

Alpha blending is on, over PrepareDraw's 0xFE101010 clear, so for the
_plasma_alpha tests the capture holds the *blended* result, not the
decoder's output:

    fb = round((src * a + 0x10 * (255 - a)) / 255)      per RGB channel
    fb_a = round((a * a + 0xFE * (255 - a)) / 255)

That model is exact (--fit-alpha reports 1024/1024 alpha channels), so those
captures are usable as fit data once it is inverted, and the alpha rules can
be fitted through it.


What is usable as fit data
--------------------------
  DXT3_plasma / DXT5_plasma        byte-identical goldens, alpha 255
                                   throughout, so no blend: the cleanest
                                   constraint on the colour rule.
  DXT3_plasma_alpha                colour rule + the DXT3 4-bit alpha rule.
  DXT5_plasma_alpha                colour rule + the DXT5 alpha palette.
  DXT1_plasma, DXT1_plasma_alpha   NOT USABLE.  Their colour blocks are
                                   byte-identical to DXT3's, yet the capture
                                   holds 16 distinct colours in every 4x4
                                   block.  A DXT block encodes 4 colours, so
                                   no rounding rule of any kind can produce
                                   this.  --dxt1-anomaly records what was
                                   ruled out.

Usage:
    dxt_fit_rounding.py --check-geometry   prove/refute the assumptions above
    dxt_fit_rounding.py --fit-colour       score every colour-block rule
    dxt_fit_rounding.py --fit-alpha        score the DXT3/DXT5 alpha rules
    dxt_fit_rounding.py --verify           HEAD vs fitted, every capture
    dxt_fit_rounding.py --verify-c         compile s3tc.c and score *it*
    dxt_fit_rounding.py --dxt1-anomaly     why the DXT1 captures are excluded
"""

import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

GOLDEN_DIR = os.environ.get(
    "DXT_GOLDEN_DIR", "/home/justin/goldens/results/Texture_DXT")
DDS_DIR = os.environ.get(
    "DXT_DDS_DIR", "/home/justin/nxdk_pgraph_tests/resources/dxt_images")

QUAD_X, QUAD_Y, QUAD_SIZE = 192, 112, 256   # floor((640-256)/2), floor((480-256)/2)
TEX_DIM = 32
MAG = QUAD_SIZE // TEX_DIM                  # 8x point magnification
NB = TEX_DIM // 4                           # blocks per row

CLEAR_RGB = 0x10                            # PrepareDraw(0xFE101010)
CLEAR_A = 0xFE

# golden png stem -> (dds, format)
NON_MIP = [
    ("DXT1_plasma_dxt1", "plasma_dxt1.dds", 1),
    ("DXT1_plasma_alpha_dxt1", "plasma_alpha_dxt1.dds", 1),
    ("DXT3_plasma_dxt3", "plasma_dxt3.dds", 3),
    ("DXT3_plasma_alpha_dxt3", "plasma_alpha_dxt3.dds", 3),
    ("DXT5_plasma_dxt5", "plasma_dxt5.dds", 5),
    ("DXT5_plasma_alpha_dxt5", "plasma_alpha_dxt5.dds", 5),
]
BY_STEM = {s: (d, f) for s, d, f in NON_MIP}

# Opaque DXT3: alpha is 255 throughout so the blend is the identity, which
# makes this the one capture that constrains the colour rule on its own.
COLOUR_FIT = ["DXT3_plasma_dxt3"]
ALPHA_FIT = ["DXT3_plasma_alpha_dxt3", "DXT5_plasma_alpha_dxt5"]


# ---------------------------------------------------------------- input data

def golden(stem):
    """(32x32x4 silicon texel grid, cells_are_uniform)."""
    img = np.array(Image.open(os.path.join(GOLDEN_DIR, stem + ".png"))
                   .convert("RGBA")).astype(int)
    reg = img[QUAD_Y:QUAD_Y + QUAD_SIZE, QUAD_X:QUAD_X + QUAD_SIZE]
    cells = reg.reshape(TEX_DIM, MAG, TEX_DIM, MAG, 4)
    uniform = bool((cells.max(axis=(1, 3)) == cells.min(axis=(1, 3))).all())
    return cells[:, 0, :, 0, :], uniform


def level0(dds):
    return open(os.path.join(DDS_DIR, dds), "rb").read()[128:]


def colour_blocks(dds):
    """[(c0, c1, indices)] in raster block order."""
    raw = level0(dds)
    stride = 8 if "dxt1" in dds else 16
    coff = 0 if stride == 8 else 8
    return [struct.unpack("<HHI", raw[b * stride + coff:b * stride + coff + 8])
            for b in range(NB * NB)]


def scatter(per_block, shape):
    """Turn a per-block 4x4 palette-index expansion into a texel grid."""
    out = np.zeros((TEX_DIM, TEX_DIM) + shape, int)
    for b, blk in enumerate(per_block):
        bj, bi = divmod(b, NB)
        out[bj * 4:bj * 4 + 4, bi * 4:bi * 4 + 4] = blk
    return out


# ------------------------------------------------------- candidate colour rules

def expand(v, bits, mode):
    """n-bit colour component -> 8 bits."""
    mx = (1 << bits) - 1
    if mode == "trunc":                  # v * 255 / mx, what s3tc.c does today
        return v * 255 // mx
    if mode == "round":
        return (v * 255 + mx // 2) // mx
    if mode == "ceil":
        return (v * 255 + mx - 1) // mx
    if mode == "repl":                   # bit replication
        return (v << (8 - bits)) | (v >> (2 * bits - 8))
    if mode == "shift":                  # zero fill
        return v << (8 - bits)
    raise KeyError(mode)


def interp13(a, b, mode):
    """(2*a + b)/3 -- the interpolant nearer a -- under a rounding rule."""
    s = 2 * a + b
    if mode == "trunc":                  # what s3tc.c does today
        return s // 3
    if mode == "plus1":                  # identical to "round" for s >= 0
        return (s + 1) // 3
    if mode == "round":
        return (2 * s + 3) // 6
    if mode == "ceil":
        return (s + 2) // 3
    if mode == "nv171":                  # (a*171 + b*85 + 128) >> 8
        return (a * 171 + b * 85 + 128) >> 8
    if mode == "nv171t":
        return (a * 171 + b * 85) >> 8
    if mode == "m86":
        return (s * 86) >> 8
    if mode == "m85":
        return (s * 85) >> 8
    if mode == "m5556":
        return (s * 0x5556) >> 16
    raise KeyError(mode)


EXPAND_MODES = ["trunc", "round", "ceil", "repl", "shift"]
INTERP_MODES = ["trunc", "plus1", "round", "ceil", "nv171", "nv171t",
                "m86", "m85", "m5556"]
DOMAINS = ["rgb8", "q565"]


class ColourRule:
    """domain rgb8: expand endpoints to 8 bits, then interpolate (s3tc.c).
       domain q565: interpolate in the native 5/6-bit domain, then expand."""

    def __init__(self, exp5, exp6, interp, domain):
        self.exp5, self.exp6, self.interp, self.domain = \
            exp5, exp6, interp, domain

    def __str__(self):
        return "exp5=%s exp6=%s interp=%s domain=%s" % (
            self.exp5, self.exp6, self.interp, self.domain)

    def palette(self, c0, c1):
        q = [((c >> 11) & 31, (c >> 5) & 63, c & 31) for c in (c0, c1)]
        if self.domain == "q565":
            lo, hi = q
            pts = [q[0], q[1],
                   tuple(interp13(lo[i], hi[i], self.interp) for i in range(3)),
                   tuple(interp13(hi[i], lo[i], self.interp) for i in range(3))]
            return [(expand(t[0], 5, self.exp5), expand(t[1], 6, self.exp6),
                     expand(t[2], 5, self.exp5)) for t in pts]
        a, b = [(expand(t[0], 5, self.exp5), expand(t[1], 6, self.exp6),
                 expand(t[2], 5, self.exp5)) for t in q]
        return [a, b,
                tuple(interp13(a[i], b[i], self.interp) for i in range(3)),
                tuple(interp13(b[i], a[i], self.interp) for i in range(3))]

    def decode(self, dds):
        blks = []
        for c0, c1, idx in colour_blocks(dds):
            pal = self.palette(c0, c1)
            blks.append([[pal[(idx >> (2 * (ty * 4 + tx))) & 3]
                          for tx in range(4)] for ty in range(4)])
        return scatter(blks, (3,))


HEAD_COLOUR = ColourRule("trunc", "trunc", "trunc", "rgb8")
FIT_COLOUR = ColourRule("repl", "repl", "round", "rgb8")


# -------------------------------------------------------- candidate alpha rules

def divmode(num, den, mode):
    if mode == "trunc":                  # what s3tc.c does today
        return num // den
    if mode == "round":
        return (num + den // 2) // den
    if mode == "plus1":
        return (num + 1) // den
    if mode == "ceil":
        return (num + den - 1) // den
    raise KeyError(mode)


DIV_MODES = ["trunc", "round", "plus1", "ceil"]


def dxt3_alpha(dds, mode="repl"):
    """4-bit alpha -> 8 bits.  'repl' is v*17, which is what s3tc.c does."""
    raw = level0(dds)
    blks = []
    for b in range(NB * NB):
        al = struct.unpack("<Q", raw[b * 16:b * 16 + 8])[0]
        vals = []
        for k in range(16):
            v = (al >> (4 * k)) & 0xF
            vals.append(v * 17 if mode == "repl" else expand(v, 4, mode))
        blks.append([vals[ty * 4:ty * 4 + 4] for ty in range(4)])
    return scatter(blks, ())


def dxt5_alpha(dds, m7, m5):
    """DXT5 alpha palette: 8-value mode divides by 7, 6-value mode by 5."""
    raw = level0(dds)
    blks = []
    for b in range(NB * NB):
        blk = raw[b * 16:b * 16 + 16]
        a0, a1 = blk[0], blk[1]
        bits = int.from_bytes(blk[2:8], "little")
        pal = [a0, a1]
        if a0 > a1:
            pal += [divmode((6 - j) * a0 + (1 + j) * a1, 7, m7)
                    for j in range(6)]
        else:
            pal += [divmode((4 - j) * a0 + (1 + j) * a1, 5, m5)
                    for j in range(4)] + [0, 255]
        vals = [pal[(bits >> (3 * k)) & 7] for k in range(16)]
        blks.append([vals[ty * 4:ty * 4 + 4] for ty in range(4)])
    return scatter(blks, ())


HEAD_ALPHA = ("trunc", "trunc")
FIT_ALPHA = ("round", "round")


# ------------------------------------------------------------- blend and score

def blend(rgb, a):
    """The capture is post-blend: src_alpha / one_minus_src_alpha over the
    0xFE101010 clear.  Verified exact by --fit-alpha."""
    a3 = a[:, :, None]
    out_rgb = np.floor((rgb * a3 + CLEAR_RGB * (255 - a3)) / 255.0 + 0.5)
    out_a = np.floor((a * a + CLEAR_A * (255 - a)) / 255.0 + 0.5)
    return out_rgb.astype(int), out_a.astype(int)


def model(stem, crule, arule):
    """Predicted capture texels for one test under a pair of candidate rules."""
    dds, fmt = BY_STEM[stem]
    rgb = crule.decode(dds)
    if fmt == 1:
        a = np.full((TEX_DIM, TEX_DIM), 255, int)   # all blocks 4-colour mode
    elif fmt == 3:
        a = dxt3_alpha(dds)
    else:
        a = dxt5_alpha(dds, *arule)
    return blend(rgb, a)


def score(stems, crule, arule):
    rgb_ex = rgb_tot = a_ex = a_tot = worst = bad = 0
    for stem in stems:
        g, _ = golden(stem)
        prgb, pa = model(stem, crule, arule)
        r = g[:, :, :3] - prgb
        ra = g[:, :, 3] - pa
        rgb_ex += int((r == 0).sum()); rgb_tot += r.size
        a_ex += int((ra == 0).sum()); a_tot += ra.size
        worst = max(worst, int(np.abs(r).max()), int(np.abs(ra).max()))
        bad += int(((np.abs(r).max(axis=2) != 0) | (ra != 0)).sum())
    return rgb_ex, rgb_tot, a_ex, a_tot, worst, bad


# -------------------------------------------------------------------- commands

def cmd_check_geometry(args):
    d1, d3, d5 = (level0("plasma_dxt1.dds"), level0("plasma_dxt3.dds"),
                  level0("plasma_dxt5.dds"))
    print("plasma_dxt1 vs plasma_dxt3 colour blocks byte-identical: %s"
          % all(d1[i * 8:i * 8 + 8] == d3[i * 16 + 8:i * 16 + 16]
                for i in range(64)))
    print("plasma_dxt3 vs plasma_dxt5 colour blocks byte-identical: %s"
          % all(d3[i * 16 + 8:i * 16 + 16] == d5[i * 16 + 8:i * 16 + 16]
                for i in range(64)))
    print("  -> the three plasma captures decode from the *same* colour bytes,")
    print("     so any difference between their captures is the format path,")
    print("     not the data.\n")
    print("%-26s %-9s %-24s %s"
          % ("capture", "8x8 cells", "colours per 4x4 block", "verdict"))
    for stem, dds, fmt in NON_MIP:
        g, uniform = golden(stem)
        counts = [len(set(map(tuple, g[bj * 4:bj * 4 + 4, bi * 4:bi * 4 + 4, :3]
                              .reshape(-1, 3).tolist())))
                  for bj in range(NB) for bi in range(NB)]
        mx, av = max(counts), sum(counts) / len(counts)
        if not uniform:
            v = "UNUSABLE: not point-magnified"
        elif mx > 4:
            v = "NOT a palette lookup - excluded" if fmt == 1 \
                else "alpha varies within blocks"
        else:
            v = "clean: colour rule fits here"
        print("%-26s %-9s max %2d  avg %4.1f%9s %s"
              % (stem, "uniform" if uniform else "VARIES", mx, av, "", v))
    print("\nA DXT colour block encodes 4 colours, so a point-sampled 4x4 block")
    print("must show at most 4 distinct colours.  More than 4 did not come")
    print("from a palette lookup and cannot be fitted as one.  For the")
    print("_plasma_alpha rows the extra colours are the alpha blend, which")
    print("--fit-alpha models exactly; for the DXT1 rows they are not.")
    return 0


def cmd_fit_colour(args):
    stems = args.tests or COLOUR_FIT
    rows = []
    for dom in DOMAINS:
        for e5 in EXPAND_MODES:
            for e6 in EXPAND_MODES:
                for it in INTERP_MODES:
                    r = ColourRule(e5, e6, it, dom)
                    ex, tot, _, _, worst, bad = score(stems, r, FIT_ALPHA)
                    rows.append((ex, -worst, str(r), tot, worst, bad))
    rows.sort(reverse=True)
    hex_, htot, _, _, hworst, hbad = score(stems, HEAD_COLOUR, HEAD_ALPHA)
    print("fit set: %s  (%d RGB channels, %d texels)"
          % (", ".join(stems), htot, htot // 3))
    print("candidates scored: %d\n" % len(rows))
    print("%-52s %18s %5s %7s" % ("rule", "exact RGB", "max", "bad px"))
    for ex, _, s, tot, worst, bad in rows[:args.top]:
        print("%-52s %8d/%-9d %5d %7d" % (s, ex, tot, worst, bad))
    print("\n%-52s %8d/%-9d %5d %7d   <-- HEAD"
          % (str(HEAD_COLOUR), hex_, htot, hworst, hbad))
    ties = [r[2] for r in rows if r[0] == rows[0][0] == htot]
    if ties:
        print("\nEXACT on this set: %d rule(s)" % len(ties))
        for t in ties:
            print("   ", t)
        print("interp=plus1 and interp=round are the same function for")
        print("non-negative integers (verified by brute force over 0..255),")
        print("so they are one rule written two ways, not rivals.")
        cmd_separate(args)
    return 0


def cmd_separate(args):
    """round and nv171 both fit.  Are they separable by this data at all, or is
    every example degenerate?  A rule that fits is worth nothing until the
    alternatives are measured, and a tie has to be shown to be a real tie."""
    rr = ColourRule("repl", "repl", "round", "rgb8")
    rn = ColourRule("repl", "repl", "nv171", "rgb8")
    reps = ([expand(v, 5, "repl") for v in range(32)],
            [expand(v, 6, "repl") for v in range(64)])
    dis = tot = 0
    for vals in reps:
        for a in vals:
            for b in vals:
                tot += 1
                dis += interp13(a, b, "round") != interp13(a, b, "nv171")
    print("\nround vs nv171: they disagree on %d/%d (%.1f%%) of endpoint pairs"
          % (dis, tot, 100.0 * dis / tot))
    for stem in ["DXT3_plasma_dxt3", "DXT3_plasma_alpha_dxt3",
                 "DXT5_plasma_alpha_dxt5"]:
        hit = 0
        for c0, c1, idx in colour_blocks(BY_STEM[stem][0]):
            pr, pn = rr.palette(c0, c1), rn.palette(c0, c1)
            if pr == pn:
                continue
            sel = {(idx >> (2 * k)) & 3 for k in range(16)}
            hit += bool(sel & {i for i in range(4) if pr[i] != pn[i]})
        print("  %-26s blocks reaching a disagreeing pair: %d/64" % (stem, hit))
    print("None of the fittable captures contains a texel that separates them,")
    print("so this data cannot choose.  s3tc.c implements round because it is")
    print("the exact rational rule; nv171 stays observationally equivalent")
    print("until a capture with a widely separated endpoint pair is measured.")
    return 0


def cmd_fit_alpha(args):
    stems = args.tests or ALPHA_FIT
    print("blend model check (alpha channel only, colour rule irrelevant):")
    for stem in stems:
        g, _ = golden(stem)
        _, pa = model(stem, FIT_COLOUR, FIT_ALPHA)
        print("  %-26s alpha exact %4d/1024 max %d"
              % (stem, int((g[:, :, 3] == pa).sum()),
                 int(np.abs(g[:, :, 3] - pa).max())))
    print("\nDXT3 4-bit alpha expansion (v*17 == bit replication):")
    for mode in ["repl", "trunc", "round", "shift"]:
        g, _ = golden("DXT3_plasma_alpha_dxt3")
        a = dxt3_alpha("plasma_alpha_dxt3.dds", mode)
        _, pa = blend(FIT_COLOUR.decode("plasma_alpha_dxt3.dds"), a)
        print("  %-8s alpha exact %4d/1024 max %d"
              % (mode, int((g[:, :, 3] == pa).sum()),
                 int(np.abs(g[:, :, 3] - pa).max())))
    print("\nDXT5 alpha palette, scored on DXT5_plasma_alpha")
    print("(63 blocks in 8-value mode / 7, 1 block in 6-value mode / 5):")
    print("  %-8s %-8s %-22s %s" % ("/7", "/5", "alpha exact", "RGB exact"))
    rows = []
    for m7 in DIV_MODES:
        for m5 in DIV_MODES:
            ex, tot, aex, atot, worst, bad = score(
                ["DXT5_plasma_alpha_dxt5"], FIT_COLOUR, (m7, m5))
            rows.append((aex + ex, m7, m5, aex, atot, ex, tot, worst))
    rows.sort(reverse=True)
    for _, m7, m5, aex, atot, ex, tot, worst in rows:
        mark = "   <-- HEAD" if (m7, m5) == HEAD_ALPHA else ""
        mark += "   <-- fitted" if (m7, m5) == FIT_ALPHA else ""
        print("  %-8s %-8s %8d/%-12d %8d/%-9d max %d%s"
              % (m7, m5, aex, atot, ex, tot, worst, mark))
    print("\nThe /5 rule is decided by the RGB channels, not the alpha channel:")
    print("the one 6-value block differs by 1 in two palette entries, and the")
    print("blend maps both to the same framebuffer alpha.  Scoring only alpha")
    print("would have called it degenerate and left it unconstrained.")
    return 0


def cmd_verify(args):
    print("HEAD rule:   %s  +  DXT5 alpha /7=%s /5=%s"
          % (HEAD_COLOUR, HEAD_ALPHA[0], HEAD_ALPHA[1]))
    print("fitted rule: %s  +  DXT5 alpha /7=%s /5=%s\n"
          % (FIT_COLOUR, FIT_ALPHA[0], FIT_ALPHA[1]))
    print("%-26s %-26s %-26s" % ("capture", "HEAD", "fitted"))
    hdr = "%18s %5s" % ("exact RGB+A", "max")
    print("%-26s %-26s %-26s" % ("", hdr, hdr))
    tot_h = tot_f = 0
    for stem, dds, fmt in NON_MIP:
        cells = []
        for crule, arule in ((HEAD_COLOUR, HEAD_ALPHA),
                             (FIT_COLOUR, FIT_ALPHA)):
            ex, tot, aex, atot, worst, bad = score([stem], crule, arule)
            cells.append("%8d/%-9d %5d" % (ex + aex, tot + atot, worst))
        eh = score([stem], HEAD_COLOUR, HEAD_ALPHA)
        ef = score([stem], FIT_COLOUR, FIT_ALPHA)
        tot_h += eh[0] + eh[2]
        tot_f += ef[0] + ef[2]
        note = "" if stem in BY_STEM and fmt != 1 else "   (excluded: see --dxt1-anomaly)"
        print("%-26s %-26s %-26s%s" % (stem, cells[0], cells[1], note))
    print("\nfittable captures only (DXT3/DXT5, 4 captures):")
    fit_stems = [s for s, _, f in NON_MIP if f != 1]
    for nm, cr, ar in (("HEAD  ", HEAD_COLOUR, HEAD_ALPHA),
                       ("fitted", FIT_COLOUR, FIT_ALPHA)):
        ex, tot, aex, atot, worst, bad = score(fit_stems, cr, ar)
        print("  %s  RGB %d/%d  alpha %d/%d  max |d| %d  differing texels %d"
              % (nm, ex, tot, aex, atot, worst, bad))
    return 0


SHIM = """#ifndef SHIM_OSDEP_H
#define SHIM_OSDEP_H
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#define g_malloc(n) malloc(n)
#ifndef MIN
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#endif
#endif
"""

HARNESS = """#include "s3tc.c"

int main(int argc, char **argv)
{
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        perror("open");
        return 1;
    }
    static uint8_t buf[1 << 20];
    fseek(f, 128, SEEK_SET);
    size_t n = fread(buf, 1, sizeof(buf), f);
    (void)n;
    fclose(f);
    enum S3TC_DECOMPRESS_FORMAT fmt =
        !strcmp(argv[2], "dxt1") ? S3TC_DECOMPRESS_FORMAT_DXT1 :
        !strcmp(argv[2], "dxt3") ? S3TC_DECOMPRESS_FORMAT_DXT3 :
                                   S3TC_DECOMPRESS_FORMAT_DXT5;
    uint8_t *out = s3tc_decompress_2d(fmt, buf, 32, 32);
    fwrite(out, 1, 32 * 32 * 4, stdout);
    return 0;
}
"""


def cmd_verify_c(args):
    """Compile the real s3tc.c and score *it*, not a model of it, against the
    captures.  A worktree cannot build the emulator, but the decoder needs
    nothing from QEMU beyond g_malloc and MIN, so it builds standalone behind
    a twelve-line shim.  This is what keeps the fit honest: the rule in the
    script and the rule in the C are checked to be the same function."""
    import shutil
    import subprocess
    import tempfile

    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "..", "hw", "xbox", "nv2a", "pgraph")
    src = os.path.normpath(src)
    tmp = tempfile.mkdtemp(prefix="dxt_verify_c.")
    try:
        os.makedirs(os.path.join(tmp, "shim", "qemu"))
        open(os.path.join(tmp, "shim", "qemu", "osdep.h"), "w").write(SHIM)
        open(os.path.join(tmp, "harness.c"), "w").write(HARNESS)
        exe = os.path.join(tmp, "harness")
        cc = subprocess.run(
            ["cc", "-O2", "-Wall", "-o", exe, os.path.join(tmp, "harness.c"),
             "-I" + os.path.join(tmp, "shim"), "-I" + src, "-lpthread"],
            capture_output=True, text=True)
        if cc.returncode:
            print(cc.stderr)
            return 1
        print("compiled %s standalone\n" % os.path.join(src, "s3tc.c"))
        print("%-26s %-22s %s" % ("capture", "RGB exact", "alpha exact"))
        t_rgb = n_rgb = t_a = n_a = worst = bad = 0
        for stem, dds, fmt in NON_MIP:
            raw = subprocess.run(
                [exe, os.path.join(DDS_DIR, dds), "dxt%d" % fmt],
                capture_output=True, check=True).stdout
            dec = np.frombuffer(raw, dtype=np.uint8).reshape(
                TEX_DIM, TEX_DIM, 4).astype(int)
            g, _ = golden(stem)
            prgb, pa = blend(dec[:, :, :3], dec[:, :, 3])
            r, ra = g[:, :, :3] - prgb, g[:, :, 3] - pa
            print("%-26s %5d/3072 max %d      %5d/1024 max %d%s"
                  % (stem, (r == 0).sum(), np.abs(r).max(),
                     (ra == 0).sum(), np.abs(ra).max(),
                     "   (excluded: see --dxt1-anomaly)" if fmt == 1 else ""))
            if fmt != 1:
                t_rgb += int((r == 0).sum()); n_rgb += r.size
                t_a += int((ra == 0).sum()); n_a += ra.size
                worst = max(worst, int(np.abs(r).max()), int(np.abs(ra).max()))
                bad += int(((np.abs(r).max(axis=2) != 0) | (ra != 0)).sum())
        print("\nfittable captures: RGB %d/%d  alpha %d/%d  max |d| %d  "
              "differing texels %d" % (t_rgb, n_rgb, t_a, n_a, worst, bad))
        return 0 if (t_rgb == n_rgb and t_a == n_a) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_dxt1_anomaly(args):
    """Why the DXT1 captures cannot be fitted, and what was ruled out."""
    stem, dds = "DXT1_plasma_dxt1", "plasma_dxt1.dds"
    g, uniform = golden(stem)
    blks = colour_blocks(dds)
    print("%s: 8x8 cells uniform = %s (so sampling is point)" % (stem, uniform))
    print("alpha channel: %s (all blocks are 4-colour mode, so the blend is"
          % np.unique(g[:, :, 3]))
    print("the identity and cannot be the source of the variation)")
    n3 = sum(1 for c0, c1, _ in blks if c0 <= c1)
    print("blocks in 3-colour (punch-through) mode: %d/64" % n3)

    dec = FIT_COLOUR.decode(dds)
    res = g[:, :, :3] - dec
    print("\nresidual vs the rule fitted on DXT3: max %d mean %+.3f mean|d| %.3f"
          % (int(np.abs(res).max()), res.mean(), np.abs(res).mean()))
    print("the same bytes decoded the same way match the DXT3 capture exactly.")

    print("\nruled out:")
    ok = bad = 0
    for b, (c0, c1, idx) in enumerate(blks):
        bj, bi = divmod(b, NB)
        pal = FIT_COLOUR.palette(c0, c1)
        for ty in range(4):
            for tx in range(4):
                i = (idx >> (2 * (ty * 4 + tx))) & 3
                gv = g[bj * 4 + ty, bi * 4 + tx, :3]
                near = min(range(4), key=lambda j: sum(
                    (int(gv[c]) - pal[j][c]) ** 2 for c in range(3)))
                ok += near == i
                bad += near != i
    print("  mis-indexing: golden texel nearest its own index's palette entry")
    print("                in %d/%d cases, so block alignment and index" % (ok, ok + bad))
    print("                extraction are confirmed correct.")

    from collections import defaultdict
    for mask, nm in ((1, "2x2"), (3, "4x4")):
        cells = defaultdict(list)
        for b, (c0, c1, idx) in enumerate(blks):
            bj, bi = divmod(b, NB)
            pal = FIT_COLOUR.palette(c0, c1)
            for ty in range(4):
                for tx in range(4):
                    i = (idx >> (2 * (ty * 4 + tx))) & 3
                    x, y = bi * 4 + tx, bj * 4 + ty
                    for c in range(3):
                        cells[(x & mask, y & mask)].append(
                            int(g[y, x, c]) - pal[i][c])
        print("  %s ordered dither: largest cell mean %+.3f (a real ordered"
              % (nm, max(abs(np.mean(v)) for v in cells.values())))
        print("                   dither would separate the cells; it does not)")

    lat_hits = []
    for mode in ("trunc", "repl", "round"):
        lat = {expand(v, 5, mode) for v in range(32)}
        lat_hits.append("%s %d/1024" % (
            mode, sum(int(v) in lat for v in g[:, :, 0].reshape(-1))))
    print("  A1R5G5B5 output: R values on the 5-bit lattice: %s"
          % ", ".join(lat_hits))
    print("                   (a 16-bit DXT1 output path would put all 1024")
    print("                   on it)")

    K = 2
    A, rhs = [], []
    for y in range(K, TEX_DIM - K):
        for x in range(K, TEX_DIM - K):
            for c in range(3):
                A.append(dec[y - K:y + K + 1, x - K:x + K + 1, c]
                         .reshape(-1).astype(float))
                rhs.append(float(g[y, x, c]))
    A, rhs = np.array(A), np.array(rhs)
    w = np.linalg.lstsq(A, rhs, rcond=None)[0]
    pred = A @ w
    print("  texture filtering: best-fit 5x5 kernel is the identity (centre")
    print("                     %.4f, largest neighbour %.4f) and leaves"
          % (w[12], np.abs(np.delete(w, 12)).max()))
    print("                     residual max %.2f vs %.2f for no filter at all"
          % (np.abs(pred - rhs).max(),
             np.abs(g[K:-K, K:-K, :3] - dec[K:-K, K:-K]).max()))

    best = (0, None)
    for dom in DOMAINS:
        for e5 in EXPAND_MODES:
            for e6 in EXPAND_MODES:
                for it in INTERP_MODES:
                    r = ColourRule(e5, e6, it, dom)
                    ex = score([stem], r, FIT_ALPHA)[0]
                    best = max(best, (ex, str(r)))
    print("  every rounding rule: best of %d candidates is %d/3072 channels"
          % (len(DOMAINS) * len(EXPAND_MODES) ** 2 * len(INTERP_MODES),
             best[0]))
    print("                       (%s)" % best[1])
    print("                       against 3072/3072 on DXT3's identical bytes.")
    print("\nConclusion: the DXT1 captures are not the output of any DXT1")
    print("palette decode, so the residual issue #6 tabulates for DXT1 is not")
    print("a decode rounding rule and cannot be fixed by changing one.")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-geometry", action="store_true")
    ap.add_argument("--fit-colour", action="store_true")
    ap.add_argument("--fit-alpha", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--verify-c", action="store_true")
    ap.add_argument("--dxt1-anomaly", action="store_true")
    ap.add_argument("--tests", nargs="*", help="golden stems to use")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    for flag, fn in (("check_geometry", cmd_check_geometry),
                     ("fit_colour", cmd_fit_colour),
                     ("fit_alpha", cmd_fit_alpha),
                     ("verify", cmd_verify),
                     ("verify_c", cmd_verify_c),
                     ("dxt1_anomaly", cmd_dxt1_anomaly)):
        if getattr(args, flag):
            return fn(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
