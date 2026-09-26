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

WHAT THIS SCRIPT DOES NOT DO, after audit pass 1 (M1).  It shipped a
``--proposed`` mode advertised as simulating the implementation, and that mode
computed the SAME FUNCTION as the default: the write transform
``expand7(a >> 1)`` is ``r1_blend_dst_alpha`` character for character, and the
swatch alpha 0x22 is its fixed point, so the substitution collapsed.  Verified
identical on all 1,024 inputs.  The mode is removed and the "simulated at 0 of
32" claim is WITHDRAWN -- it was this model scoring itself.

The residue is worth more than the claim was: on *TestDstAlpha* the proposed
implementation and this model are indistinguishable, so **these four captures
cannot validate the implementation**.  Only a capture where alpha blending is
live can, because that is the one place the two differ -- hardware quantises
after the blend and fixed-function cannot.  ``XA_*_Add_SrcA_DstA`` is that
capture.  ``selftest --selftest`` proves the coincidence rather than asserting
it.

WHY A SCRIPT.  These sixteen numbers are the whole evidence for a change to
glsl/psh.c and the GL texture path, and a number nobody can re-run is a claim.
"""
import glob
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


def expand7(v):
    """Bit-replicate a seven-bit value to eight bits."""
    return (v << 1) | (v >> 6)


def a7_of(stored8):
    return stored8 >> 1


def r1_blend_dst_alpha(stored8):
    """Destination alpha the blend unit reads from an X1A7 surface."""
    return expand7(a7_of(stored8))


def r2_sampled_alpha(stored8, pad_bit):
    """Alpha the texture unit reads back from an X1A7 surface."""
    return (pad_bit << 7) | a7_of(stored8)


def compose(background_alpha, pad_bit, one_minus, r1=None, r2=None,
            store=None):
    """The test's draw sequence, as one function. ONE copy (audit L1).

    Both the model and every rival are scored through this, so a rival cannot
    be refuted by a divergence between two transcriptions of the composition.

    ``store`` is the WRITE side: what the emulator actually puts in the host
    surface's alpha byte after the blend. It defaults to the identity, which
    is what both renderers do today, and it exists so a design that changes
    the stored byte can be priced here rather than argued -- see DESIGNS.
    """
    r1 = r1 or r1_blend_dst_alpha
    r2 = r2 or r2_sampled_alpha
    store = store or (lambda a8, pad: a8)
    # The background pass is a draw with blending off, so it goes through the
    # write side as well; the byte the blend unit reads as its destination is
    # the STORED one, not the value the test asked for. With store = identity
    # -- every rival above, and both renderers today -- this is exactly the
    # previous expression, so nothing that was scored before moves.
    ad = r1(store(background_alpha, pad_bit)) / 255.0
    factor = (1.0 - ad) if one_minus else ad
    surface_rgb = SWATCH_RGB * factor
    surface_alpha = store(round(SWATCH_ALPHA * factor), pad_bit)
    sampled = r2(surface_alpha, pad_bit) / 255.0
    return (round(surface_rgb * sampled + FRAMEBUFFER_GREY * (1.0 - sampled)),
            round(surface_rgb))


def swatch(background_alpha, pad_bit, one_minus):
    """(top_half_rgb, bottom_half_rgb) for one 128x128 swatch."""
    return compose(background_alpha, pad_bit, one_minus)


# The goldens, as <suite>/<capture>.png, and the swatch grid inside them.
#
# Read off TestDstAlpha: kMargin = 32, top = 92.f, kTextureSpacing =
# kSwatchSize + 16 = 144, four swatches per row before `left + kTextureSpacing
# >= GetFramebufferWidthF()` wraps, and the next row is top + 144 + 16 = 160
# lower. Each swatch is kSwatchSize = 128 and splits at floor(top + 64).
# validate_geometry() checks these against the image rather than trusting them
# (audit L3).
MARGIN, TOP, SPACING, ROW_PITCH, SIZE = 32, 92, 144, 160, 128


def swatch_box(i):
    return MARGIN + SPACING * (i % 4), TOP + ROW_PITCH * (i // 4)


def validate_geometry(shape):
    """Return a complaint if the grid does not fit the image, else None."""
    height, width = shape[0], shape[1]
    need_x = MARGIN + SPACING * 3 + SIZE
    need_y = TOP + ROW_PITCH * ((len(BACKGROUND_ALPHAS) - 1) // 4) + SIZE
    if width < need_x or height < need_y:
        return ('image is %dx%d but the swatch grid needs at least %dx%d'
                % (width, height, need_x, need_y))
    return None


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


# WHOLE DESIGNS, not single rules. A rival above swaps one read; an entry here
# is a complete answer to "where does the pad bit live", scored end to end
# through the same compose().  Each is (r1_for(pad_bit), r2, store):
# r1 is built per pad bit because one of these designs has the blend unit
# reading a byte the pad bit is part of.
#
# `guest byte in the host surface` is the third refuted home for the pad bit,
# and the only one refuted BEFORE any C was written.  The sampler and the
# download were each implemented, measured and reverted first; this one cost
# a python run.  It is kept so the number can be re-run rather than quoted:
# an unrecorded number is a claim.
#
# The two other entries are controls. `today` must reproduce the error the
# renderers actually have, and `R1 expand7 + R2 rule` must reproduce zero; a
# table where the controls drift is measuring itself.
DESIGNS = {
    'today (both renderers)': (
        lambda pad: (lambda s: s),
        lambda s, pad: s,
        None),
    'R1 expand7 + R2 rule (this model)': (
        lambda pad: r1_blend_dst_alpha,
        r2_sampled_alpha,
        None),
    'guest byte in the host surface': (
        lambda pad: (lambda s: s),
        lambda s, pad: s,
        lambda a8, pad: (pad << 7) | (a8 >> 1)),
    'guest byte stored, blend still reads expand7': (
        lambda pad: r1_blend_dst_alpha,
        lambda s, pad: s,
        lambda a8, pad: (pad << 7) | (a8 >> 1)),
}


def score_design(design, truth):
    """Halves this design gets wrong, and its worst |delta|, against `truth`.

    `truth` maps (capture, background alpha, half) -> byte, so the same
    function scores GOLDEN_DSTALPHA's sixteen checked-in values and the
    thirty-two read off the goldens.
    """
    r1_for, r2, store = DESIGNS[design]
    wrong = worst = 0
    for (name, bg, half), want in truth.items():
        pad_bit = 1 if 'O1A7' in name else 0
        top, bot = compose(bg, pad_bit, name.startswith('1-'),
                           r1=r1_for(pad_bit), r2=r2, store=store)
        got = top if half == 'top' else bot
        wrong += got != want
        worst = max(worst, abs(got - want))
    return wrong, worst


def write_transform(a8):
    """The proposed implementation's write side: quantise to seven bits.

    Kept only so the coincidence below can be demonstrated. It is EQUAL to
    r1_blend_dst_alpha, which is exactly why --proposed was removed.
    """
    return expand7(a7_of(a8))


def coincidence():
    """Prove the proposed write transform cannot be distinguished here.

    Returns (differing_inputs, total_inputs, transform_equals_r1, fixed_point).
    """
    # Substitute the proposed WRITE transform where the model uses R1 at the
    # read. If the implementation were distinguishable here, these would
    # differ somewhere.
    differ = sum(
        swatch(bg, pad, om) != compose(bg, pad, om, r1=write_transform)
        for bg in range(256) for pad in (0, 1) for om in (False, True))
    same_fn = all(write_transform(a) == r1_blend_dst_alpha(a)
                  for a in range(256))
    return differ, 256 * 2 * 2, same_fn, write_transform(SWATCH_ALPHA) == SWATCH_ALPHA


def selftest():
    bad = 0
    print('R1+R2 against the sixteen DstAlpha golden swatch halves')
    for (name, bg, half), want in sorted(GOLDEN_DSTALPHA.items()):
        pad_bit = 1 if 'O1A7' in name else 0
        top, bottom = swatch(bg, pad_bit, one_minus=False)
        got = top if half == 'top' else bottom
        ok = got == want
        bad += not ok
        print('  golden %-4s %-24s bg %#04x  want %#04x  got %#04x  %s'
              % (half, name, bg, want, got, 'ok' if ok else 'MISMATCH'))

    print('\nrivals -- each must be REFUTED by the same sixteen values')
    for label, (r1, r2) in RIVALS.items():
        miss = 0
        for (name, bg, half), want in GOLDEN_DSTALPHA.items():
            pad_bit = 1 if 'O1A7' in name else 0
            top, bottom = compose(bg, pad_bit, False, r1=r1, r2=r2)
            miss += (top if half == 'top' else bottom) != want
        status = 'refuted (%d/16 wrong)' % miss if miss else 'NOT REFUTED'
        bad += miss == 0
        print('  %-46s %s' % (label, status))

    # Audit pass 1, M1. The removed --proposed mode claimed to simulate the
    # implementation and computed the same function as the model. Rather than
    # assert that in a comment, demonstrate it: the write transform IS R1, and
    # the swatch alpha is its fixed point, so this suite cannot tell the
    # implementation from the model at all.
    print('\nwhy there is no --proposed mode (audit M1)')
    differ, total, same_fn, fixed = coincidence()
    for label, got in (
            ('the write transform is r1_blend_dst_alpha on all 256 values',
             same_fn),
            ('the swatch alpha 0x22 is its fixed point', fixed)):
        bad += not got
        print('  %-58s %s' % (label, 'ok' if got else 'NO LONGER TRUE'))
    # Audit L-new: this number is the SWEEP's result, not a product of
    # constants. coincidence() scores all `total` inputs and `differ` is what
    # it found; printing `total` alone put a figure in prose where a measured
    # count belongs.
    bad += differ != 0
    print('  substituting the write transform changes %d of %d inputs  %s'
          % (differ, total, 'ok' if not differ else 'UNEXPECTED'))
    print('  so TestDstAlpha cannot distinguish them at all')
    print('  -- validating the implementation needs XA_*_Add_SrcA_DstA,')
    print('     the capture where alpha blending is live.')

    print('\ndesigns -- where the pad bit could live, scored end to end')
    print('  (sixteen checked-in DstAlpha halves; score() does all thirty-two)')
    scored = {}
    for design in DESIGNS:
        wrong, worst = score_design(design, GOLDEN_DSTALPHA)
        scored[design] = wrong
        print('  %-46s %2d of %d wrong, worst |delta| %3d'
              % (design, wrong, len(GOLDEN_DSTALPHA), worst))
    # The controls, as assertions rather than as prose. A table whose controls
    # drift is scoring itself, which is what audit M1 caught the removed
    # --proposed mode doing.
    for label, ok in (
            ('the model gets every one right',
             scored['R1 expand7 + R2 rule (this model)'] == 0),
            ("today's identity does not",
             scored['today (both renderers)'] > 0),
            ('storing the guest byte does not, either way round',
             scored['guest byte in the host surface'] > 0 and
             scored['guest byte stored, blend still reads expand7'] > 0)):
        bad += not ok
        print('  %-58s %s' % (label, 'ok' if ok else 'NO LONGER TRUE'))

    lossy = [v for v in range(128) if a7_of(expand7(v)) != v]
    bad += bool(lossy)
    print('\n  the seven-bit expansion round-trips over all 128 values  %s'
          % ('ok' if not lossy else 'FAILS at %r' % lossy[:5]))

    print('\n%s' % ('all checks pass' if not bad else 'FAILED: %d' % bad))
    return 1 if bad else 0


def score(goldens):
    pred = predictions()
    names = sorted({k[0] for k in pred})
    expected = len(pred)
    compared = missing = bad = worst = 0
    problems = []

    # RESOLVE BEFORE IMPORTING THE IMAGE STACK. Deciding which goldens exist
    # needs glob and nothing else, and the CI runner has no numpy or PIL: with
    # the imports at the top of this function, a run with no goldens died on
    # ImportError and never printed its report. The gate's "exits non-zero"
    # check then passed on the traceback rather than on the guard -- an
    # assertion satisfied for a reason other than the one it names, which is
    # the very shape H1 was. Resolve first, report first, import only to
    # compare.
    observed = {}
    resolved, why = {}, {}
    for name in names:
        hits = sorted(glob.glob(os.path.join(goldens, '*', name + '.png')))
        if len(hits) == 1:
            resolved[name] = hits[0]
        elif not hits:
            why[name] = 'no golden under %s' % goldens
        else:
            # Audit L-new-2: when EVERY capture is ambiguous, `resolved` is
            # empty and the old code reported "no golden" under a root that
            # holds several -- the opposite of what happened.
            why[name] = ('%d candidate goldens, ambiguous -- %s'
                         % (len(hits), ', '.join(hits)))

    if not resolved:
        for name in names:
            problems.append('%s: %s' % (name, why[name]))
        missing = expected
        for p in problems:
            print('PROBLEM: %s' % p)
        print('\ncompared 0 of %d modelled halves; 0 differ; worst |delta| = 0'
              % expected)
        print('%d modelled halves were NOT compared -- this is a FAILURE, not '
              'agreement' % missing)
        return 1

    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        print('PROBLEM: cannot compare: %s' % exc)
        print('\ncompared 0 of %d modelled halves; 0 differ; worst |delta| = 0'
              % expected)
        print('%d modelled halves were NOT compared -- this is a FAILURE, not '
              'agreement' % expected)
        return 1

    for name in names:
        hits = sorted(glob.glob(os.path.join(goldens, '*', name + '.png')))
        if not hits:
            # Audit H1: a golden that was never opened is NOT a golden that
            # agreed. Count it as missing and fail; the old code printed
            # "NO GOLDEN", left `bad` alone, and reported "0 of 32 ... differ"
            # against a HARDCODED 32 -- a clean pass over nothing read.
            missing += 2 * len(BACKGROUND_ALPHAS)
            problems.append('%s: no golden under %s' % (name, goldens))
            continue
        if len(hits) > 1:
            # Audit M2: glob order is arbitrary. Refuse rather than score
            # whichever the filesystem happened to return first.
            missing += 2 * len(BACKGROUND_ALPHAS)
            problems.append('%s: %d candidate goldens, ambiguous -- %s'
                            % (name, len(hits), ', '.join(hits)))
            continue
        path = hits[0]
        try:
            g = np.asarray(Image.open(path).convert('RGBA')).astype(int)
        except Exception as exc:
            # A golden that exists but will not open is not a golden that
            # agreed either, and it must not take the run down: L3 was the
            # same lesson for an undersized image.
            missing += 2 * len(BACKGROUND_ALPHAS)
            problems.append('%s: cannot open: %s' % (path, exc))
            continue
        complaint = validate_geometry(g.shape)
        if complaint:
            missing += 2 * len(BACKGROUND_ALPHAS)
            problems.append('%s: %s' % (path, complaint))
            continue
        print('%s' % path)
        for i, bg in enumerate(BACKGROUND_ALPHAS):
            left, top = swatch_box(i)
            for half, y0 in (('top', top), ('bot', top + SIZE // 2)):
                region = g[y0:y0 + SIZE // 2, left:left + SIZE]
                flat = region.reshape(-1, 4)
                vals, counts = np.unique(flat, axis=0, return_counts=True)
                got = int(vals[counts.argmax()][0])
                want = pred[(name, bg, half)]
                observed[(name, bg, half)] = got
                d = abs(got - want)
                compared += 1
                worst = max(worst, d)
                bad += d != 0
                print('  %-24s bg %#04x %-4s golden %#04x  model %#04x  %s'
                      % (name, bg, half, got, want,
                         'ok' if not d else 'off by %d' % d))

    for p in problems:
        print('PROBLEM: %s' % p)
    print('\ncompared %d of %d modelled halves; %d differ; worst |delta| = %d'
          % (compared, expected, bad, worst))
    if missing:
        print('%d modelled halves were NOT compared -- this is a FAILURE, not '
              'agreement' % missing)

    if observed:
        # The same designs the selftest prices on sixteen values, priced here
        # on every half actually read off the disc. These are the numbers the
        # #60 record quotes, and this is where they are re-run. Printed after
        # the verdict above on purpose: if that line says halves were not
        # compared, these are scored on a subset and the count says which.
        print('\ndesigns, against the %d halves read above' % len(observed))
        for design in DESIGNS:
            n, w = score_design(design, observed)
            print('  %-46s %2d of %d wrong, worst |delta| %3d'
                  % (design, n, len(observed), w))

    return 1 if (bad or missing or compared != expected) else 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sys.exit(score(args[0] if args else '/tmp/goldens/results'))
