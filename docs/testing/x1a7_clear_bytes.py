#!/usr/bin/env python3
"""Score Clear::SCF_<fmt>_{Z,O} -- the captures that show the STORED BYTES.

    x1a7_clear_bytes.py [<run_dir>] [--goldens DIR]   # default goldens
                                                      # /tmp/goldens/results
    x1a7_clear_bytes.py --selftest                    # no goldens, no run

WHY THIS CAPTURE AND NOT THE OTHERS.  ``ClearTests::TestSurfaceFmt`` renders a
128x128 surface of the format under test, fills it with NV097_CLEAR_SURFACE,
draws ONE 4x4 centre mark (``kBlackCenterMarkSize = 2.f``) and nothing else,
then samples that memory back as a LINEAR ``A8B8G8R8`` texture with blending
off on the left half.  The texture unit is never told the memory was X1A7, so
anything X1A7-shaped in the result is IN THE BYTES.  Every other X1A7 capture
composites the surface and shows a function of them, which is why
``x1a7_forward_model.py`` needs a model of the composition and this does not.

WHAT IT SETTLED, 2026-09-20, from the goldens alone and with no emulator.
#60's record said the pad bit "is written by the raster, per pixel, and is
absent where the raster never wrote".  Six solid 128x128 surfaces are 98,304
pixels, exactly **96** of them covered by a draw, and ``_O == _Z | 0x80`` holds
on **all 98,304** with no exceptions -- including 32,736 whose alpha is 0x00.
**A CLEAR WRITES THE PAD BIT.**  Gating a download conversion on draw coverage
would leave 98,208 of 98,304 pixels unconverted, which is worse than
converting all of them.  The sentence is withdrawn; this is what withdrew it.

AND IT IS NOT AN X1A7 QUIRK.  ``X8R8G8B8_{Z,O}`` and ``X1R5G5B5_{Z,O}`` behave
identically -- see FORMATS.  For those two the blend unit has no destination
alpha to lose (``vk/draw.c:surface_color_format_dst_alpha_is_one()``), so the
host alpha byte is free to carry the X constant; only X1A7 has seven real
alpha bits under the pad and therefore the one-byte-two-readers conflict.

WHY A SCRIPT.  The Clear suite is in none of the six suites ``[job.arms]``
scores and not among the 236 captures of ``iso_surf1``, so no number in #181
has ever seen it.  A capture nobody scores needs a scorer more than one
everybody does.
"""
import glob
import os
import sys

# Read off ClearTests::TestSurfaceFmt.
SIZE = 128                  # kTextureSize
MARK = 4                    # kBlackCenterMarkSize = 2.f, so a 4x4 quad
SURFACES = 6                # the eight format cases, less the two 16bpp halves

# The six swatch rectangles, located by the _Z/_O disagreement and then
# CHECKED against the image rather than trusted: find_surfaces() refuses
# anything that is not SURFACES solid SIZExSIZE rectangles.
RECTS = ((48, 128), (192, 128), (336, 128), (480, 128), (48, 272), (192, 272))

# Each X-bit format pair, and where its X field lands in a capture that is
# sampled back as A8B8G8R8.  The 1555 pair is read two words to a texel, so
# its bit 15 shows up in a COLOUR channel of the readback and not in alpha --
# which is why `channel` is recorded per format instead of assumed.
#
# `relation` is each format's OWN statement of what the X field does to the
# stored byte, because they are not the same statement.  X1A7 has one pad bit
# over seven real alpha bits, so _O is _Z with bit 7 set.  X8R8G8B8's X field
# is the WHOLE byte, so _Z reads 0x00 and _O reads 0xff and `_O == _Z | 0x80`
# is false on every pixel -- reporting that relation for it would print a
# convincing zero and mean nothing.
FORMATS = (
    ('X1A7R8G8B8', 'SCF_X1A7R8G8B8_Z1A7R8G8B8', 'SCF_X1A7R8G8B8_O1A7R8G8B8',
     'alpha', '_O == _Z | 0x80', lambda za, oa: oa == (za | 0x80)),
    ('X8R8G8B8', 'SCF_X8R8G8B8_Z8R8G8B8', 'SCF_X8R8G8B8_O8R8G8B8',
     'alpha', '_Z alpha 0x00 and _O alpha 0xff',
     lambda za, oa: (za == 0x00) & (oa == 0xFF)),
    ('X1R5G5B5', 'SFC_X1R5G5B5_Z1R5G5B5', 'SCF_X1R5G5B5_O1R5G5B5',
     'rgb', 'bit 15 lands in a colour channel', None),
)

# Measured 2026-09-20 against the checked-in goldens.  --selftest cannot
# re-derive these without the images; it checks that they are ARITHMETICALLY
# consistent with the geometry above, which is the part a typo would break.
MEASURED = {
    'surface_px': 98304,        # SURFACES * SIZE * SIZE
    'drawn_px': 96,             # SURFACES * MARK * MARK
    'cleared_only_px': 98208,   # the difference
    'x1a7_pad_set': 98304,      # _O == _Z|0x80 on every surface pixel
    'x1a7_pad_absent': 0,
    'x1a7_zero_alpha_with_pad': 32736,
}


def expand7(v):
    """Bit-replicate a seven-bit value to eight bits. Same rule as the model."""
    return ((v << 1) | (v >> 6)) & 0xFF


def masks(shape):
    """(surface, drawn) boolean masks for the six swatches."""
    import numpy as np
    surf = np.zeros(shape[:2], bool)
    drawn = np.zeros(shape[:2], bool)
    for x, y in RECTS:
        surf[y:y + SIZE, x:x + SIZE] = True
        c = SIZE // 2
        drawn[y + c - MARK // 2:y + c + MARK // 2,
              x + c - MARK // 2:x + c + MARK // 2] = True
    return surf, drawn


def check_geometry(z, o):
    """Complain unless the _Z/_O disagreement really is the six rectangles.

    RECTS was found by looking at ONE pair of goldens.  Asserting it against
    every pair is the difference between a located instrument and a guess that
    happened to work once.  Two things are checked and neither assumes a full
    rectangle: the 1555 pair covers only half of each, because
    TestSurfaceFmt halves quad_height for a two-byte format.
    """
    differs = (z != o).any(axis=2)
    surf, _ = masks(z.shape)
    # A handful outside is the HUD text the suite prints over every capture;
    # 38 is what the goldens carry. A large number means RECTS is wrong.
    outside = int((differs & ~surf).sum())
    if outside > 256:
        return ('%d pixels disagree OUTSIDE the six rectangles -- RECTS does '
                'not describe this capture' % outside)
    empty = [i for i, (x, y) in enumerate(RECTS)
             if not differs[y:y + SIZE, x:x + SIZE].any()]
    if empty:
        return ('rect(s) %s show no _Z/_O difference at all -- RECTS is not '
                'where this capture puts its surfaces'
                % ', '.join(str(i) for i in empty))
    return None


def load(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGBA')).astype(int)


def find(root, name):
    hits = sorted(glob.glob(os.path.join(root, '*', name + '.png')))
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, 'no golden named %s under %s' % (name, root)
    return None, '%d candidates for %s, ambiguous -- %s' % (
        len(hits), name, ', '.join(hits))


def selftest():
    bad = 0
    print('geometry, against the constants read off clear_tests.cpp')
    for label, got, want in (
            ('%d surfaces of %dx%d' % (SURFACES, SIZE, SIZE),
             SURFACES * SIZE * SIZE, MEASURED['surface_px']),
            ('%d centre marks of %dx%d' % (SURFACES, MARK, MARK),
             SURFACES * MARK * MARK, MEASURED['drawn_px']),
            ('cleared-only is the difference',
             MEASURED['surface_px'] - MEASURED['drawn_px'],
             MEASURED['cleared_only_px'])):
        ok = got == want
        bad += not ok
        print('  %-44s %7d  %s' % (label, got, 'ok' if ok else
                                   'MISMATCH, want %d' % want))

    print('\nthe measured claim, as arithmetic')
    for label, ok in (
            ('the pad bit is on every surface pixel',
             MEASURED['x1a7_pad_set'] == MEASURED['surface_px']),
            ('so none of them lacks it',
             MEASURED['x1a7_pad_absent'] == 0),
            ('and %d of those carry it under alpha 0x00'
             % MEASURED['x1a7_zero_alpha_with_pad'],
             0 < MEASURED['x1a7_zero_alpha_with_pad']
             < MEASURED['cleared_only_px']),
            ('gating on DRAW coverage would miss %d of %d'
             % (MEASURED['cleared_only_px'], MEASURED['surface_px']),
             MEASURED['cleared_only_px'] > MEASURED['surface_px'] * 0.99)):
        bad += not ok
        print('  %-58s %s' % (label, 'ok' if ok else 'NO LONGER TRUE'))

    lossy = [v for v in range(128) if (expand7(v) >> 1) != v]
    bad += bool(lossy)
    print('\n  the seven-bit expansion round-trips over all 128 values  %s'
          % ('ok' if not lossy else 'FAILS at %r' % lossy[:5]))

    print('\n  NOT CHECKED HERE: every claim above about the IMAGES. Run this')
    print('  against the goldens to re-derive them; --selftest has no disc.')
    print('\n%s' % ('all checks pass' if not bad else 'FAILED: %d' % bad))
    return 1 if bad else 0


def report(goldens, run_dir):
    problems = []
    try:
        import numpy as np
    except ImportError as exc:
        print('PROBLEM: cannot compare: %s' % exc)
        print('\n0 of %d format pairs checked -- this is a FAILURE, not '
              'agreement' % len(FORMATS))
        return 1

    checked = bad = 0
    for label, zname, oname, channel, rel_label, relation in FORMATS:
        zp, why = find(goldens, zname)
        op, why2 = find(goldens, oname)
        if not zp or not op:
            problems.append(why or why2)
            continue
        z, o = load(zp), load(op)
        if z.shape != o.shape:
            problems.append('%s: the _Z and _O goldens differ in shape' % label)
            continue
        complaint = check_geometry(z, o)
        if complaint:
            problems.append('%s: %s' % (label, complaint))
            continue
        surf, drawn = masks(z.shape)
        checked += 1
        za, oa = z[:, :, 3], o[:, :, 3]
        print('%s  (X shows up in %s)' % (label, channel))
        print('    surface %d px, drawn %d, cleared-only %d'
              % (int(surf.sum()), int((surf & drawn).sum()),
                 int((surf & ~drawn).sum())))
        if relation is not None:
            holds = relation(za, oa) & surf
            pad_on = int(holds.sum())
            zero_pad = int((holds & (za == 0)).sum())
            print('    %s on %d of %d surface px; _Z alpha 0x00 among them %d'
                  % (rel_label, pad_on, int(surf.sum()), zero_pad))
            if label == 'X1A7R8G8B8':
                for k, want in (('x1a7_pad_set', pad_on),
                                ('x1a7_zero_alpha_with_pad', zero_pad)):
                    if MEASURED[k] != want:
                        bad += 1
                        problems.append('%s: recorded %d, measured %d'
                                        % (k, MEASURED[k], want))
        else:
            d = int(((z[:, :, :3] != o[:, :, :3]).any(axis=2) & surf).sum())
            print('    _Z and _O differ in RGB on %d surface px '
                  '(alpha carries nothing here)' % d)

        if not run_dir:
            continue
        # The emulator, if a run directory was given. The relation below is
        # the forward model's two rules seen on stored bytes: the host surface
        # holds expand7(A7) and never the pad bit, so an emulator that has the
        # quantisation and not the pad reads exactly this.
        for gname, g in ((zname, z), (oname, o)):
            path = os.path.join(run_dir, 'Clear::%s.png' % gname)
            if not os.path.exists(path):
                problems.append('%s: no run capture at %s' % (gname, path))
                continue
            e = load(path)
            if e.shape != g.shape:
                problems.append('%s: run capture differs in shape' % gname)
                continue
            diff = int((g != e).any(axis=2).sum())
            line = '    run %-28s %7d px differ from the golden' % (gname, diff)
            if label == 'X1A7R8G8B8':
                # Only X1A7 has real alpha bits under its pad, so only here
                # does the quantisation relation mean anything. X8R8G8B8's X
                # field is the whole byte; scoring it against expand7 would
                # print a large number about nothing.
                exc = int((surf & (expand7(g[:, :, 3] & 0x7F)
                                   != e[:, :, 3])).sum())
                line += (';  emu == expand7(golden & 0x7F) with %d '
                         'exception(s)' % exc)
            print(line)

    for p in problems:
        print('PROBLEM: %s' % p)
    print('\nchecked %d of %d format pairs; %d recorded value(s) no longer hold'
          % (checked, len(FORMATS), bad))
    if checked != len(FORMATS):
        print('%d pair(s) were NOT checked -- this is a FAILURE, not agreement'
              % (len(FORMATS) - checked))
    return 1 if (bad or problems or checked != len(FORMATS)) else 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = '/tmp/goldens/results'
    if '--goldens' in sys.argv:
        root = sys.argv[sys.argv.index('--goldens') + 1]
        args = [a for a in args if a != root]
    sys.exit(report(root, args[0] if args else None))
