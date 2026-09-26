#!/usr/bin/env python3
"""Test #87's layout model against a capture, offline, before any build.

    swizzle_morton_fit.py <ours.png> [golden.png]

``swizzle_residual.py`` says *what shape* Surface_pitch::Swizzle's residual is
-- a permutation, right pixels in wrong places, runs of 16/32/64/80 px. It
does not say *which* permutation, and it cannot: it searches translations
only, stepping dx by 4, so an interleave is invisible to it. This script names
the permutation and then tries to break it.

THE MODEL. The host render target is always linear. Sampling it in place of
the guest's memory is valid only because a swizzled STORE and a swizzled READ
cancel. ``Surface pitch::Swizzle`` renders into a *swizzled* 128x128 surface
and then reads it back as a *linear* 128x128 texture, so nothing cancels and
what we hand the texture unit is the guest's image with exactly one
uncancelled Morton transform on it:

    ours[v][u] == gold[M(u, v) // 128][M(u, v) % 128]

M being the interleave ``generate_swizzle_masks(128, 128)`` builds, read at a
128-pixel stride -- ``unswizzle_box()`` applied to data that was already
linear. There are no free parameters. The masks come from the renderer's own
swizzle.c, the 128s from the test's ``kTextureSize``, and the quad corners
from the arithmetic in ``SurfacePitchTests::DrawResults``.

WHY THE CONTROL IS THE POINT. The test draws a 2x2 matrix -- {64x64, 128x128}
surface x {512, 256} colour pitch -- into four quads, and only the two 128x128
ones are wrong. A transform that "explains" all four explains nothing; it is a
curve fit over an image with four colours in it. So this script scores the map
on the two quads we get RIGHT as well, where the honest answer is that it must
LOSE to the identity. It also scores the map against a shuffled control, since
an identical colour multiset is not evidence of a permutation: two of the four
colours appear exactly 1536 times each, so a pure value swap passes a multiset
test, and this lane built that counter-example once already.

EXIT STATUS, and it has three values rather than two on purpose:

    0  MODEL HOLDS -- fits the wrong quads, LOSES on the right ones, and
       reconstructs the golden byte for byte. All three, or this is not it.
    1  MODEL REFUTED -- a leg failed. The layout model is wrong; do not
       compile a guess against it.
    2  NOT EXERCISED -- the capture is byte-identical to the golden, so there
       was no defect to model and no leg was scored.

2 is separate from 0 because #87's fix is in master, which makes the clean
capture the common case rather than the odd one: point this at any capture
taken since c807592d02 and it scores nothing. Collapsing that into 0 would
make `swizzle_morton_fit.py cap.png && echo holds` print "holds" for a run
that tested nothing, which is exactly the free green this script exists to
argue against.
"""
import sys

import numpy as np
from PIL import Image

# hw/xbox/nv2a/pgraph/swizzle.c, generate_swizzle_masks(). Bits of the linear
# coordinates are dealt alternately into the offset, x first.
def generate_swizzle_masks(width, height, depth=1):
    x = y = z = 0
    bit = 1
    mask_bit = 1
    while True:
        done = True
        if bit < width:
            x |= mask_bit
            mask_bit <<= 1
            done = False
        if bit < height:
            y |= mask_bit
            mask_bit <<= 1
            done = False
        if bit < depth:
            z |= mask_bit
            mask_bit <<= 1
            done = False
        bit <<= 1
        if done:
            break
    assert (x ^ y ^ z) == (mask_bit - 1), "masks are mutually exclusive"
    return x, y, z


def deposit(value, mask):
    """The offset swizzle_increment_offset() reaches after `value` steps.

    Repeatedly applying ``(off - mask) & mask`` from 0 enumerates the
    submasks of `mask` in increasing order, which is a bit-deposit of the
    step count. Asserted against the renderer's own iteration below rather
    than argued, because this is the one place a silent disagreement would
    make the whole fit meaningless.
    """
    out = 0
    bit = 1
    while mask:
        low = mask & -mask
        if value & bit:
            out |= low
        mask ^= low
        bit <<= 1
    return out


def _check_deposit_matches_renderer(mask, n):
    off = 0
    for i in range(n):
        assert off == deposit(i, mask), "deposit() disagrees with swizzle.c"
        off = (off - mask) & mask


def morton_map(size):
    """M[v][u] -> the linear index our capture took pixel (u, v) from."""
    mask_x, mask_y, _ = generate_swizzle_masks(size, size)
    _check_deposit_matches_renderer(mask_x, size)
    _check_deposit_matches_renderer(mask_y, size)
    ox = np.array([deposit(u, mask_x) for u in range(size)])
    oy = np.array([deposit(v, mask_y) for v in range(size)])
    return oy[:, None] + ox[None, :]


# SurfacePitchTests::DrawResults, framebuffer 640x480, kTextureSize 128:
#   start = (640 - 256) / 3 = 128,  top = (480 - 256) / 3 = 74.667
# Each result quad is 128x128 on screen whatever the surface behind it was.
SIZE = 128
QUADS = [
    ("64x64  p512  (right)", 128, 75, False),
    ("64x64  p256  (right)", 384, 75, False),
    ("128x128 p512 (wrong)", 128, 277, True),
    ("128x128 p256 (wrong)", 384, 277, True),
]


def score(ours, gold, x0, y0, M):
    """Fraction of the quad the model explains, and the identity's fraction."""
    o = ours[y0:y0 + SIZE, x0:x0 + SIZE]
    g = gold[y0:y0 + SIZE, x0:x0 + SIZE]
    src = g.reshape(-1, g.shape[-1])[M.ravel()].reshape(o.shape)
    model = (o == src).all(axis=-1).mean()
    ident = (o == g).all(axis=-1).mean()
    return model, ident, src


def main(ours_p, gold_p):
    ours = np.asarray(Image.open(ours_p).convert("RGB")).astype(int)
    gold = np.asarray(Image.open(gold_p).convert("RGB")).astype(int)
    if ours.shape != gold.shape:
        raise SystemExit("shape mismatch: %s vs %s" % (ours.shape, gold.shape))

    M = morton_map(SIZE)
    mask_x, mask_y, _ = generate_swizzle_masks(SIZE, SIZE)
    print("generate_swizzle_masks(%d, %d) -> mask_x %#010x  mask_y %#010x"
          % (SIZE, SIZE, mask_x, mask_y))
    print("M is a permutation of 0..%d: %s"
          % (SIZE * SIZE - 1, sorted(M.ravel()) == list(range(SIZE * SIZE))))
    print()

    # A capture taken after the fix has no defect left to model, and saying
    # "MODEL REFUTED" about it would be a confident answer to a question that
    # was not asked. Name that case rather than scoring it -- but do NOT name
    # it with status 0, which is what this path did when it was written.
    #
    # Status 0 there means `swizzle_morton_fit.py cap.png && echo holds` prints
    # "holds" having scored no leg at all, and since #87's fix is in master the
    # clean capture is now the COMMON case: every fresh Surface_pitch::Swizzle
    # run takes this branch. A check whose default outcome is a green that
    # means nothing is the failure mode this script exists to argue against.
    # Three outcomes, three statuses: 0 held, 1 refuted, 2 never exercised.
    if not (np.abs(ours - gold).max(axis=2) > 0).any():
        print("NOT EXERCISED: this capture is byte-identical to the golden, so "
              "the defect\nthis models is absent from it and no leg was "
              "scored. This is the expected\nresult for a post-fix capture. "
              "Point the script at a pre-fix capture to\nexercise the model.")
        return 2

    print("per quad, fraction of the 16,384 px each model explains:")
    print("  %-22s %9s %9s" % ("quad", "MORTON", "identity"))
    ok = True
    rebuilt = ours.copy()
    for name, x0, y0, is_wrong in QUADS:
        model, ident, src = score(ours, gold, x0, y0, M)
        flag = ""
        if is_wrong:
            # The map must explain the whole quad and beat the identity.
            if model < 1.0:
                flag, ok = "  <<< MODEL FAILS", False
            elif ident >= model:
                flag, ok = "  <<< NO SEPARATION", False
        else:
            # And must LOSE here, or it is a curve fit rather than a model.
            if ident < 1.0:
                flag, ok = "  <<< control is not clean", False
            elif model >= ident:
                flag, ok = "  <<< CURVE FIT: wins where it must not", False
        print("  %-22s %8.4f%% %8.4f%%%s"
              % (name, model * 100, ident * 100, flag))
        if is_wrong:
            # Invert: put each pixel back where the golden has it.
            inv = np.empty_like(M).ravel()
            inv[M.ravel()] = np.arange(M.size)
            q = ours[y0:y0 + SIZE, x0:x0 + SIZE].reshape(-1, 3)
            rebuilt[y0:y0 + SIZE, x0:x0 + SIZE] = \
                q[inv].reshape(SIZE, SIZE, 3)
    print()

    resid = int((np.abs(rebuilt - gold).max(axis=2) > 0).sum())
    before = int((np.abs(ours - gold).max(axis=2) > 0).sum())
    print("inverting the map on the two wrong quads:")
    print("  differing before %6d of %d" % (before, ours[:, :, 0].size))
    print("  differing after  %6d of %d" % (resid, ours[:, :, 0].size))
    if resid:
        ok = False
        print("  <<< the inverse does NOT reconstruct the golden")

    # The run-length signature swizzle_residual.py reports is a constraint on
    # tile geometry, so the model has to predict it rather than merely agree
    # that something is wrong.
    print()
    print("horizontal run lengths of the differing set:")
    for label, img in (("observed", ours), ("predicted by M", None)):
        if img is None:
            pred = gold.copy()
            for name, x0, y0, is_wrong in QUADS:
                if not is_wrong:
                    continue
                g = gold[y0:y0 + SIZE, x0:x0 + SIZE]
                pred[y0:y0 + SIZE, x0:x0 + SIZE] = \
                    g.reshape(-1, 3)[M.ravel()].reshape(SIZE, SIZE, 3)
            img = pred
        d = np.abs(img - gold).max(axis=2) > 0
        runs = {}
        for row in d:
            n = 0
            for v in row:
                if v:
                    n += 1
                elif n:
                    runs[n] = runs.get(n, 0) + 1
                    n = 0
            if n:
                runs[n] = runs.get(n, 0) + 1
        print("  %-14s %s" % (label, ", ".join(
            "%dpx x%d" % (k, runs[k]) for k in sorted(runs, reverse=True))))

    print()
    print("VERDICT:", "MODEL HOLDS" if ok else "MODEL REFUTED")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    gold = (sys.argv[2] if len(sys.argv) > 2
            else "/home/justin/goldens/results/Surface_pitch/Swizzle.png")
    sys.exit(main(sys.argv[1], gold))
