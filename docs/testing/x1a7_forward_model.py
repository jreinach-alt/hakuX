#!/usr/bin/env python3
"""Forward-model Blend surface's X1A7R8G8B8 DstAlpha captures from two rules.

    x1a7_forward_model.py [<goldens_root>]        # default /tmp/goldens/results
    x1a7_forward_model.py --selftest              # no goldens needed

X1A7R8G8B8 stores seven bits of alpha under a pad bit that reads back as 0
(``_Z``) or 1 (``_O``).  Emulation keeps the surface as an 8-bit-alpha host
format, so every consumer of that alpha needs a rule, and the two consumers
want DIFFERENT functions of the same seven bits:

  R1  BLEND destination alpha.  Ad8 = (A7 << 1) | (A7 >> 6), A7 = stored >> 1.
      Bit replication of the seven stored bits.  THE PAD BIT DOES NOT
      PARTICIPATE -- the _Z and _O goldens are equal on every bottom half.

  R2  TEXTURE readback.  sampled8 = (X << 7) | (stored >> 1), X = 0 for _Z and
      1 for _O.  Measured 2026-09-12 over 32,755 invertible px and recorded at
      vk/constants.h's X1A7R8G8B8 entry; reproduced here from a different
      suite, so the two derivations are independent.

R1 is what that entry left open as "the other half ... the 7-bit quantisation
on the way IN".  It is pinned here: the expansion is bit replication, not
truncation and not a constant.  Both renderers currently use the identity for
R1 and no rule at all for R2.

WHY A SCRIPT.  These sixteen numbers are the whole evidence for a change to
glsl/psh.c and the GL texture path, and a number nobody can re-run is a claim.
Composing R1 and R2 through the test's own draw sequence reproduces all
sixteen golden swatch halves EXACTLY, with no free parameter to tune.
"""
import os
import sys

# Blend surface's TestDstAlpha (nxdk_pgraph_tests, src/tests/blend_surface_tests.cpp):
#   surface <- diffuse(background_color), blend OFF     -- stores the background alpha
#   surface <- white 0x22FFFFFF, blend ON, {sfactor, ZERO}
#   then the surface is sampled and drawn over PrepareDraw(0xFF555555), twice:
#     top half    alpha = sampled alpha
#     bottom half alpha forced opaque, so it shows the surface's RGB directly
BACKGROUND_ALPHAS = (0x00, 0x40, 0x80, 0xFF)
SWATCH_ALPHA = 0x22          # kSwatchColor = 0x22FFFFFF
SWATCH_RGB = 0xFF            # white
FRAMEBUFFER_GREY = 0x55      # PrepareDraw(0xFF555555)


def r1_blend_dst_alpha(stored8):
    """Destination alpha the blend unit reads from an X1A7 surface."""
    a7 = stored8 >> 1
    return (a7 << 1) | (a7 >> 6)


def r2_sampled_alpha(stored8, pad_bit):
    """Alpha the texture unit reads back from an X1A7 surface."""
    return (pad_bit << 7) | (stored8 >> 1)


def swatch(background_alpha, pad_bit, one_minus):
    """Return (top_half_rgb, bottom_half_rgb) for one 128x128 swatch."""
    ad = r1_blend_dst_alpha(background_alpha) / 255.0
    factor = (1.0 - ad) if one_minus else ad
    # result = src * factor + dst * ZERO, on both the colour and alpha halves.
    surface_rgb = SWATCH_RGB * factor
    surface_alpha = round(SWATCH_ALPHA * factor)
    sampled = r2_sampled_alpha(surface_alpha, pad_bit) / 255.0
    over = surface_rgb * sampled + FRAMEBUFFER_GREY * (1.0 - sampled)
    return round(over), round(surface_rgb)


# The goldens, as <suite>/<capture>.png, and the swatch grid inside them.
MARGIN, TOP, SPACING, ROW_PITCH, SIZE = 32, 92, 144, 160, 128


def swatch_box(i):
    left = MARGIN + SPACING * (i % 4)
    top = TOP + ROW_PITCH * (i // 4)
    return left, top


def predictions():
    """Every modelled value, keyed by (capture, background alpha, half)."""
    out = {}
    for pad_bit, suffix in ((0, 'Z'), (1, 'O')):
        for one_minus in (False, True):
            name = ('1-DstAlpha_XA_%s1A7RGB8' if one_minus
                    else 'DstAlpha_XA_%s1A7RGB8') % suffix
            for bg in BACKGROUND_ALPHAS:
                top, bottom = swatch(bg, pad_bit, one_minus)
                out[(name, bg, 'top')] = top
                out[(name, bg, 'bot')] = bottom
    return out


# Measured from the hardware goldens, checked in so --selftest needs no disc.
# Only the DstAlpha captures: the 1-DstAlpha pair reuses the same two rules
# with the complementary factor and is scored against the goldens, not pinned
# here, so that a wrong sign cannot be hidden by a table written to match.
GOLDEN_DSTALPHA = {
    ('DstAlpha_XA_Z1A7RGB8', 0x00, 'top'): 0x55,
    ('DstAlpha_XA_Z1A7RGB8', 0x00, 'bot'): 0x00,
    ('DstAlpha_XA_Z1A7RGB8', 0x40, 'top'): 0x55,
    ('DstAlpha_XA_Z1A7RGB8', 0x40, 'bot'): 0x40,
    ('DstAlpha_XA_Z1A7RGB8', 0x80, 'top'): 0x56,
    ('DstAlpha_XA_Z1A7RGB8', 0x80, 'bot'): 0x81,
    ('DstAlpha_XA_Z1A7RGB8', 0xFF, 'top'): 0x60,
    ('DstAlpha_XA_Z1A7RGB8', 0xFF, 'bot'): 0xFF,
    ('DstAlpha_XA_O1A7RGB8', 0x00, 'top'): 0x2A,
    ('DstAlpha_XA_O1A7RGB8', 0x00, 'bot'): 0x00,
    ('DstAlpha_XA_O1A7RGB8', 0x40, 'top'): 0x4A,
    ('DstAlpha_XA_O1A7RGB8', 0x40, 'bot'): 0x40,
    ('DstAlpha_XA_O1A7RGB8', 0x80, 'top'): 0x6C,
    ('DstAlpha_XA_O1A7RGB8', 0x80, 'bot'): 0x81,
    ('DstAlpha_XA_O1A7RGB8', 0xFF, 'top'): 0xB6,
    ('DstAlpha_XA_O1A7RGB8', 0xFF, 'bot'): 0xFF,
}

# A rival for each rule, so a pass means the goldens SELECTED these two and not
# merely that some rule fits.  Each must be refuted by the same sixteen values.
RIVALS = {
    'R1 identity (what both renderers do today)':
        (lambda s: s, r2_sampled_alpha),
    'R1 truncate to 7 bits, no replication':
        (lambda s: (s >> 1) << 1, r2_sampled_alpha),
    'R2 no pad bit (readback is the stored alpha)':
        (r1_blend_dst_alpha, lambda s, x: s),
    'R2 pad bit as a whole-channel constant':
        (r1_blend_dst_alpha, lambda s, x: 255 if x else 0),
}


def model_with(r1, r2, background_alpha, pad_bit, one_minus):
    ad = r1(background_alpha) / 255.0
    factor = (1.0 - ad) if one_minus else ad
    surface_rgb = SWATCH_RGB * factor
    surface_alpha = round(SWATCH_ALPHA * factor)
    sampled = r2(surface_alpha, pad_bit) / 255.0
    return (round(surface_rgb * sampled + FRAMEBUFFER_GREY * (1.0 - sampled)),
            round(surface_rgb))


def selftest():
    bad = 0
    print('R1+R2 against the sixteen DstAlpha golden swatch halves')
    for (name, bg, half), want in sorted(GOLDEN_DSTALPHA.items()):
        pad_bit = 1 if 'O1A7' in name else 0
        top, bottom = swatch(bg, pad_bit, one_minus=False)
        got = top if half == 'top' else bottom
        ok = got == want
        bad += not ok
        print('  %-4s %-24s bg %#04x  want %#04x  got %#04x  %s'
              % (half, name, bg, want, got, 'ok' if ok else 'MISMATCH'))
    print('\nrivals -- each must be REFUTED by the same sixteen values')
    for label, (r1, r2) in RIVALS.items():
        miss = 0
        for (name, bg, half), want in GOLDEN_DSTALPHA.items():
            pad_bit = 1 if 'O1A7' in name else 0
            top, bottom = model_with(r1, r2, bg, pad_bit, False)
            miss += (top if half == 'top' else bottom) != want
        status = 'refuted (%d/16 wrong)' % miss if miss else 'NOT REFUTED'
        bad += miss == 0
        print('  %-46s %s' % (label, status))
    print('\n%s' % ('all checks pass' if not bad else 'FAILED: %d' % bad))
    return 1 if bad else 0


def score(goldens):
    import glob
    import numpy as np
    from PIL import Image
    pred = predictions()
    worst = bad = 0
    for name in sorted({k[0] for k in pred}):
        hit = glob.glob(os.path.join(goldens, '*', name + '.png'))
        if not hit:
            print('%-28s NO GOLDEN' % name)
            continue
        g = np.asarray(Image.open(hit[0]).convert('RGBA')).astype(int)
        for i, bg in enumerate(BACKGROUND_ALPHAS):
            left, top = swatch_box(i)
            for half, y0 in (('top', top), ('bot', top + SIZE // 2)):
                region = g[y0:y0 + SIZE // 2, left:left + SIZE]
                flat = region.reshape(-1, 4)
                vals, counts = np.unique(flat, axis=0, return_counts=True)
                got = int(vals[counts.argmax()][0])
                want = pred[(name, bg, half)]
                d = abs(got - want)
                worst = max(worst, d)
                bad += d != 0
                print('%-24s bg %#04x %-4s golden %#04x  model %#04x  %s'
                      % (name, bg, half, got, want,
                         'ok' if not d else 'off by %d' % d))
    print('\n%d of 32 modelled halves differ; worst |delta| = %d' % (bad, worst))
    return 1 if bad else 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(score(sys.argv[1] if len(sys.argv) > 1 else '/tmp/goldens/results'))
