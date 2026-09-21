#!/usr/bin/env python3
"""Score every Clear::{SCF,SFC}_* capture and split its error in two.

    clear_surface_fmt.py <run_dir> [--goldens DIR]   # default goldens
                                                     # /tmp/goldens/results
    clear_surface_fmt.py --selftest                  # no goldens, no run

WHY A SECOND SCRIPT NEXT TO x1a7_clear_bytes.py.  That one asks what the
STORED BYTES say about one format pair's pad bit, and it reads the goldens.
This one asks a question about the EMULATOR that the goldens cannot answer on
their own: whether a capture's error is `the renderer served swatch 0's pixels
for swatches 1..5` or `swatch 0 itself came out wrong`.  Those are different
defects with different owners -- #184 and #164/#48 respectively -- and they
are superimposed on four of the eight captures, so a single differing-pixel
count attributes neither.

THE GEOMETRY, read off nxdk_pgraph_tests/src/tests/clear_tests.cpp.
``ClearTests::TestSurfaceFmt`` loops six times over a fixed list of clear
colours.  Each iteration points a 128x128 surface of the format under test at
``GetTextureMemoryForStage(0)``, fills it with one NV097_CLEAR_SURFACE, draws
one 4x4 black centre mark, and then samples that same memory back through a
LU_IMAGE_A8B8G8R8 stage into the Nth quad on screen.  ONE ADDRESS, ONE TEXTURE
STATE, SIX DIFFERENT CONTENTS -- so if the renderer ever answers the sample
with a previous iteration's pixels, the Nth quad comes out byte-identical to
an earlier quad, and the six clear colours being distinct is what makes that
visible rather than vacuous.  check_goldens() asserts that distinctness; if a
future disc ever made two swatches the same colour this whole instrument would
report agreement where it can no longer see.

WHAT IT REPORTS, per capture:

    diff        pixels differing from the golden, whole frame
    alias       for each of quads 1..5, the earlier quad it is byte-identical
                to, or '.' -- and the pixels that accounts for
    residual    diff minus the aliased pixels, i.e. what is wrong with the
                capture BEFORE any duplication: quad 0's own error, plus the
                centre marks.

MEASURED, 2026-09-20, #184.  On every Vulkan run on disk -- 15 device runs at
15 distinct refs spanning 2026-09-13..19 -- six of the eight captures read
alias=11111 (every later quad is quad 0 repeated) and the two X1R5G5B5
captures read alias=..... (no duplication at all, and _O is pixel-exact on all
six swatches).  See docs/lanes/clrvk184/NOTES.md; the split by surface format
is exact and is the finding.
"""
import glob
import os
import sys

# Read off clear_tests.cpp: kTextureSize, kLeftStart, kQuadSpacing, top=128.
SIZE = 128
QUADS = 6
RECTS = ((48, 128), (192, 128), (336, 128), (480, 128), (48, 272), (192, 272))

# kClearColors, in iteration order. Used only to state that they are distinct.
CLEAR_COLORS = (0x00DACABA, 0x011B2B3B, 0x7F3C2C1C,
                0x804D5D6D, 0xFE0ECE3E, 0xFF8F9FAF)

# The suite's eight surface-format cases, in clear_tests.cpp's own order and
# with its own SFC/SCF prefix inconsistency preserved -- these are capture file
# names, not format names, and renaming them here would find no file.
CAPTURES = (
    'SFC_A8R8G8B8',
    'SFC_X1R5G5B5_Z1R5G5B5',
    'SCF_X1R5G5B5_O1R5G5B5',
    'SCF_R5G6B5',
    'SCF_X8R8G8B8_Z8R8G8B8',
    'SCF_X8R8G8B8_O8R8G8B8',
    'SCF_X1A7R8G8B8_Z1A7R8G8B8',
    'SCF_X1A7R8G8B8_O1A7R8G8B8',
)

# Measured 2026-09-20 over the runs named in the docstring. --selftest cannot
# re-derive these without images; it checks they are ARITHMETICALLY consistent
# with the geometry above, which is the part a typo would break.
MEASURED = {
    # quads 1..5 duplicated, at 16,368 px of quad (16,384 less the 4x4 mark)
    'alias_px_4byte': 81840,
    # the 2-byte formats halve quad_height, so a quad is 128x64 less an 8 px
    # mark -- 8,184 -- and five of them are 40,920
    'alias_px_2byte': 40920,
    'aliasing_captures': 6,      # of len(CAPTURES)
    'clean_captures': 2,         # SFC_X1R5G5B5_Z, SCF_X1R5G5B5_O
}


def masks(shape):
    """Boolean mask per quad, in iteration order."""
    import numpy as np
    out = []
    for x, y in RECTS:
        m = np.zeros(shape[:2], bool)
        m[y:y + SIZE, x:x + SIZE] = True
        out.append(m)
    return out


def load(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGBA'))


def find_golden(root, name):
    hits = sorted(glob.glob(os.path.join(root, '*', name + '.png')))
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, 'no golden named %s under %s' % (name, root)
    return None, '%d candidates for %s, ambiguous -- %s' % (
        len(hits), name, ', '.join(hits))


def find_capture(run_dir, name):
    """Run dirs come in two shapes: flat, and dispatch's captures<N>/."""
    for c in [os.path.join(run_dir, 'Clear::%s.png' % name)] + sorted(
            glob.glob(os.path.join(run_dir, 'captures*',
                                   'Clear::%s.png' % name))):
        if os.path.exists(c):
            return c
    return None


def check_goldens(g):
    """The golden's own six quads must differ from each other.

    Without this the alias test is vacuous: two quads that SHOULD hold the
    same bytes are byte-identical in a correct renderer too, and every
    capture would report aliasing. This is the check, and it is run per
    capture rather than argued once from the clear-colour list, because the
    colour list says what the guest asked for and the golden says what
    hardware stored -- a format coarse enough to quantise two clear colours
    together would break the inference and not the list.
    """
    import numpy as np
    for i in range(1, QUADS):
        x0, y0 = RECTS[0]
        x, y = RECTS[i]
        if np.array_equal(g[y0:y0 + SIZE, x0:x0 + SIZE],
                          g[y:y + SIZE, x:x + SIZE]):
            return ('golden quads 0 and %d are byte-identical -- this format '
                    'cannot show duplication and is not scored' % i)
    return None


def check_geometry(g, e):
    """Refuse a capture RECTS does not describe, rather than score elsewhere.

    Same discipline as x1a7_clear_bytes.py: RECTS was read off the test and
    must be asserted against the image. A capture whose disagreement with the
    golden lies mostly outside the six quads is not this test's frame.
    """
    import numpy as np
    if g.shape != e.shape:
        return 'run capture differs in shape from the golden'
    differs = (g != e).any(axis=2)
    total = int(differs.sum())
    if not total:
        return None
    inside = np.zeros(g.shape[:2], bool)
    for m in masks(g.shape):
        inside |= m
    outside = int((differs & ~inside).sum())
    # The suite prints its name and the six clear colours over every capture;
    # a handful of HUD pixels can move. A large share cannot.
    if outside > 256 and outside > total * 0.05:
        return ('%d of %d differing pixels are OUTSIDE the six quads -- RECTS '
                'does not describe this capture' % (outside, total))
    return None


def score(g, e):
    """(diff, alias_of[], aliased_px) for one capture against its golden."""
    import numpy as np
    ms = masks(g.shape)
    diff = int((g != e).any(axis=2).sum())

    alias_of = [None] * QUADS
    aliased = np.zeros(g.shape[:2], bool)
    for i in range(1, QUADS):
        xi, yi = RECTS[i]
        ei = e[yi:yi + SIZE, xi:xi + SIZE]
        for j in range(i):
            xj, yj = RECTS[j]
            if np.array_equal(ei, e[yj:yj + SIZE, xj:xj + SIZE]):
                alias_of[i] = j
                # Only the pixels that are BOTH duplicated and wrong are
                # attributed to duplication. A duplicated pixel that matches
                # the golden anyway -- the background around a half-height
                # quad -- is not this defect's and must not be counted as
                # explained by it.
                aliased |= ms[i] & (g != e).any(axis=2)
                break
    return diff, alias_of, int(aliased.sum())


def selftest():
    bad = 0
    print('geometry, against the constants read off clear_tests.cpp')
    quad_px = SIZE * SIZE
    mark_px = 4 * 4
    for label, got, want in (
            ('a 4-byte quad is %dx%d less a 4x4 mark' % (SIZE, SIZE),
             quad_px - mark_px, 16368),
            ('five of them', 5 * (quad_px - mark_px),
             MEASURED['alias_px_4byte']),
            ('a 2-byte quad halves the height, less a 2x4 mark',
             (SIZE * (SIZE // 2)) - (mark_px // 2), 8184),
            ('five of them', 5 * ((SIZE * (SIZE // 2)) - (mark_px // 2)),
             MEASURED['alias_px_2byte']),
            ('the suite has %d format cases' % len(CAPTURES), len(CAPTURES),
             MEASURED['aliasing_captures'] + MEASURED['clean_captures'])):
        ok = got == want
        bad += not ok
        print('  %-52s %7d  %s' % (label, got,
                                   'ok' if ok else 'MISMATCH, want %d' % want))

    print('\nthe six quads do not overlap and do not collide')
    seen = set()
    for i, (x, y) in enumerate(RECTS):
        for j, (x2, y2) in enumerate(RECTS):
            if j <= i:
                continue
            if abs(x - x2) < SIZE and abs(y - y2) < SIZE:
                bad += 1
                print('  quads %d and %d overlap' % (i, j))
        seen.add((x, y))
    ok = len(seen) == QUADS == len(RECTS)
    bad += not ok
    print('  %-52s %s' % ('%d distinct quad origins' % len(seen),
                          'ok' if ok else 'RECTS is malformed'))

    print('\nthe alias test is not vacuous')
    ok = len(set(CLEAR_COLORS)) == QUADS
    bad += not ok
    print('  %-52s %s' % ('the six clear colours are distinct',
                          'ok' if ok else 'TWO CLEARS ASK FOR THE SAME COLOUR'))
    print('  (and check_goldens() asserts the same of the stored bytes, per')
    print('   capture, because a coarse format could quantise two together)')

    print('\n  NOT CHECKED HERE: every claim about the IMAGES. Run this')
    print('  against a run directory to re-derive them; --selftest has no disc.')
    print('\n%s' % ('all checks pass' if not bad else 'FAILED: %d' % bad))
    return 1 if bad else 0


def report(goldens, run_dir):
    problems = []
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        print('PROBLEM: cannot compare: %s' % exc)
        print('\n0 of %d captures checked -- this is a FAILURE, not agreement'
              % len(CAPTURES))
        return 1

    print('%-28s %8s  %-7s %8s %9s' %
          ('capture', 'diff', 'alias', 'aliased', 'residual'))
    checked = 0
    aliasing = clean = 0
    for name in CAPTURES:
        gp, why = find_golden(goldens, name)
        if not gp:
            problems.append(why)
            continue
        ep = find_capture(run_dir, name)
        if not ep:
            problems.append('%s: no run capture under %s' % (name, run_dir))
            continue
        g, e = load(gp), load(ep)
        complaint = check_geometry(g, e) or check_goldens(g)
        if complaint:
            problems.append('%s: %s' % (name, complaint))
            continue
        checked += 1
        diff, alias_of, aliased = score(g, e)
        col = ''.join('.' if alias_of[i] is None else str(alias_of[i])
                      for i in range(1, QUADS))
        if col.strip('.'):
            aliasing += 1
        else:
            clean += 1
        print('%-28s %8d  %-7s %8d %9d'
              % (name, diff, col, aliased, diff - aliased))

    print('\nalias column: for quads 1..5, the EARLIER quad whose bytes they '
          'repeat.\n"11111" would be quad 1 repeated; "00000" is quad 0 served '
          'six times.\nresidual is what is left once duplication is accounted '
          'for -- a different\ndefect, and on this suite a pad-byte one '
          '(#164, #48).')
    # The denominator is in the sentence on purpose. "0 show duplication" is
    # what a run directory with no captures in it also prints, and those two
    # readings must not look alike -- a starved instrument reporting a clean
    # result is the failure this line is shaped to prevent.
    print('\nof %d capture(s) SCORED (%d in the suite): %d show duplication, '
          '%d do not' % (checked, len(CAPTURES), aliasing, clean))

    for p in problems:
        print('PROBLEM: %s' % p)
    if checked != len(CAPTURES):
        print('%d of %d captures were NOT checked -- this is a FAILURE, not '
              'agreement, and the line above describes only the %d that were'
              % (len(CAPTURES) - checked, len(CAPTURES), checked))
    return 1 if (problems or checked != len(CAPTURES)) else 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    root = '/tmp/goldens/results'
    argv = sys.argv[1:]
    if '--goldens' in argv:
        i = argv.index('--goldens')
        root = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        print(__doc__)
        sys.exit(2)
    sys.exit(report(root, args[0]))
