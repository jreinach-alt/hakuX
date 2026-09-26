#!/usr/bin/env python3
"""Re-derive X1A7R8G8B8's alpha rules from Blend surface's goldens, RGB AND alpha.

    derive_x1a7.py [--goldens DIR] [--capture DIR]

Independent of docs/testing/x1a7_forward_model.py: that script pins two rules
and checks the R channel of the modal colour.  This one does not start from
the rules.  It enumerates every combination of candidate stages in the
TestDstAlpha draw sequence (blend_surface_tests.cpp:492) and keeps the ones
that reproduce EVERY half-swatch of all four DstAlpha goldens in all four
channels, framebuffer alpha included -- the scorer counts alpha, so a rule
that fits R alone is not a fit.

Stages, each with rivals:
  qin    background pass (blend off): 8-bit diffuse alpha -> stored A7
  rd     blend unit's destination-alpha read: A7 -> 8-bit Ad
  qout   swatch pass result (0x22 * factor, real) -> stored A7
  smp    texture unit's read of the stored byte: (A7, X) -> 8-bit alpha

--capture DIR additionally prices the winning model against a device capture
directory (captures1/ of a dispatch result): the predicted image is the
capture with every swatch half replaced by the model's RGBA, scored with
score_sweep.py's differing / off_by_one rules.
"""
import argparse
import itertools
import math
import os

import numpy as np
from PIL import Image

SWATCH_A, GREY = 0x22, 0x55
BGS = (0x00, 0x40, 0x80, 0xFF)
CAPTURES = ('DstAlpha_XA_Z1A7RGB8', 'DstAlpha_XA_O1A7RGB8',
            '1-DstAlpha_XA_Z1A7RGB8', '1-DstAlpha_XA_O1A7RGB8')
MARGIN, TOP, SP, RP, S = 32, 92, 144, 160, 128


def rnd(x):
    return int(math.floor(x + 0.5))


QIN = {
    'trunc a>>1': lambda a: a >> 1,
    'round a*127/255': lambda a: rnd(a * 127 / 255),
    'identity (8-bit kept)': None,  # marks "no quantisation", handled below
}
RD = {
    'replicate (v<<1)|(v>>6)': lambda v: (v << 1) | (v >> 6),
    'round v*255/127': lambda v: rnd(v * 255 / 127),
    'shift v<<1': lambda v: v << 1,
}
QOUT = {
    'trunc(round8(x))>>1': lambda x: rnd(x) >> 1,
    'trunc x*127/255': lambda x: int(x * 127 / 255),
    'round x*127/255': lambda x: rnd(x * 127 / 255),
    'trunc(floor8(x))>>1': lambda x: int(x) >> 1,
}
SMP = {
    '(X<<7)|A7': lambda v, x: (x << 7) | v,
    'replicate(A7), X ignored': lambda v, x: (v << 1) | (v >> 6),
    'A7<<1, X ignored': lambda v, x: v << 1,
    'X ? 255 : replicate(A7)': lambda v, x: 255 if x else (v << 1) | (v >> 6),
}


def model(bg, x, one_minus, qin, rd, qout, smp):
    """(top_rgba, bottom_rgba) for one swatch."""
    if qin is None:        # store 8 bits, blend reads them as-is
        ad = bg
    else:
        ad = rd(qin(bg))
    f = (255 - ad) / 255 if one_minus else ad / 255
    rgb = 255 * f                      # white * factor, dfactor ZERO
    a7 = qout(SWATCH_A * f)
    s = smp(a7, x)                     # sampled alpha, 8-bit
    rgb8 = rnd(rgb)
    # top: SRC_TEX0 alpha, composited over PrepareDraw grey with
    # {SRC_ALPHA, 1-SRC_ALPHA} -- the framebuffer alpha is 0xFF.
    top_c = rnd(rgb8 * s / 255 + GREY * (255 - s) / 255)
    top_a = rnd(s * s / 255 + 255 * (255 - s) / 255)
    return (top_c, top_c, top_c, top_a), (rgb8, rgb8, rgb8, 255)


def host_model(bg, x, one_minus, w, r):
    """(top, bottom) RGBA with host byte h: blend reads h, sampler reads r(h)."""
    h_bg = w(bg)
    f = (255 - h_bg) / 255 if one_minus else h_bg / 255
    rgb8 = rnd(255 * f)
    h_sw = rnd(SWATCH_A * f)          # blended pass, stored at 8 bits
    s = r(h_sw, x)
    top_c = rnd(rgb8 * s / 255 + GREY * (255 - s) / 255)
    top_a = rnd(s * s / 255 + 255 * (255 - s) / 255)
    return (top_c, top_c, top_c, top_a), (rgb8, rgb8, rgb8, 255)


def boxes():
    for i in range(8):
        l, t = MARGIN + SP * (i % 4), TOP + RP * (i // 4)
        yield i, 'top', t, l
        yield i, 'bot', t + S // 2, l


def read(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(int)


def truth(goldens):
    out = {}
    for name in CAPTURES:
        g = read(os.path.join(goldens, 'Blend_surface', name + '.png'))
        for i, half, y, l in boxes():
            v, n = np.unique(g[y:y + S // 2, l:l + S].reshape(-1, 4), axis=0,
                             return_counts=True)
            assert len(v) == 1, (name, i, half, 'golden half not flat')
            out[(name, i, half)] = tuple(int(c) for c in v[0])
    return out


def predict(name, i, half, qin, rd, qout, smp):
    x = 1 if '_O1A7' in name else 0
    top, bot = model(BGS[i % 4], x, name.startswith('1-'), qin, rd, qout, smp)
    return top if half == 'top' else bot


def score_combo(t, qin, rd, qout, smp):
    wrong_halves = wrong_vals = 0
    for (name, i, half), want in t.items():
        got = predict(name, i, half, qin, rd, qout, smp)
        d = sum(a != b for a, b in zip(got, want))
        wrong_vals += d
        wrong_halves += d > 0
    return wrong_halves, wrong_vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--goldens', default='/home/justin/goldens/results')
    ap.add_argument('--capture')
    a = ap.parse_args()
    t = truth(a.goldens)
    print('%d golden half-swatches read, every one a single flat RGBA' % len(t))

    rows = []
    for (qn, q), (rn, r), (on, o), (sn, s) in itertools.product(
            QIN.items(), RD.items(), QOUT.items(), SMP.items()):
        if q is None and rn != 'replicate (v<<1)|(v>>6)':
            continue    # rd is unused when nothing is quantised
        wh, wv = score_combo(t, q, r, o, s)
        rows.append((wh, wv, qn, rn if q else '-', on, sn))
    rows.sort()
    fits = [r for r in rows if r[0] == 0]
    print('\n%d combinations scored; %d fit all %d halves in all 4 channels'
          % (len(rows), len(fits), len(t)))
    for r in rows[:len(fits) + 8]:
        print('  %2d halves / %3d values wrong  qin=%-22s rd=%-24s qout=%-22s smp=%s'
              % r)

    # Where the surviving read-side rivals disagree, over all 128 A7 values.
    rep, rnd127 = RD['replicate (v<<1)|(v>>6)'], RD['round v*255/127']
    diff = [v for v in range(128) if rep(v) != rnd127(v)]
    print('\nreplicate vs round(v*255/127) differ on %d of 128 A7 values: %s'
          % (len(diff), diff[:16]))

    # The same draw sequence in HOST terms: what the emulator stores in its
    # B8G8R8A8 image and how each consumer reads that byte.  The blend unit
    # always reads the host byte by identity (fixed function), and the swatch
    # pass is blended, so its stored alpha is round8(0x22 * f) whatever the
    # shader does -- only the blend-OFF background pass can be quantised.
    #   W  write side, blend-off draws: identity, or quantise to A7 and store
    #      the UNORM8 of A7/127 (== expand7, see the 0-of-128 line above)
    #   R  read side, texture sample:   identity, or (X<<7) | (h>>1)
    exp7 = RD['replicate (v<<1)|(v>>6)']
    designs = {
        'today: W identity, R identity': (lambda a: a, lambda h, x: h),
        'W expand7 only': (lambda a: exp7(rnd(a * 127 / 255)), lambda h, x: h),
        'R (X<<7)|(h>>1) only': (lambda a: a, lambda h, x: (x << 7) | (h >> 1)),
        'W expand7 + R (X<<7)|(h>>1) (#176)':
            (lambda a: exp7(rnd(a * 127 / 255)),
             lambda h, x: (x << 7) | (h >> 1)),
    }
    print('\nhost-side designs, against all %d golden halves' % len(t))
    host_pred = {}
    for label, (w, r) in designs.items():
        wrong = 0
        for (name, i, half), want in t.items():
            got = host_model(BGS[i % 4], 1 if '_O1A7' in name else 0,
                             name.startswith('1-'), w, r)
            got = got[0] if half == 'top' else got[1]
            host_pred[(label, name, i, half)] = got
            wrong += got != want
        print('  %-40s %2d of %d halves wrong' % (label, wrong, len(t)))

    if not a.capture:
        return
    # CONTROL: the `today` design must reproduce the capture itself, half by
    # half, or the pricing below is scoring the model against itself.
    miss = 0
    for name in CAPTURES:
        c = read(os.path.join(a.capture, 'Blend_surface::' + name + '.png'))
        for i, half, y, l in boxes():
            v = np.unique(c[y:y + S // 2, l:l + S].reshape(-1, 4), axis=0)
            want = host_pred[('today: W identity, R identity', name, i, half)]
            miss += not (len(v) == 1 and tuple(int(q) for q in v[0]) == want)
    print('\ncontrol: `today` reproduces the capture on %d of %d halves'
          % (len(t) - miss, len(t)))

    print('\nhost-side designs priced against the capture (structural px)')
    for label in designs:
        tot = 0
        for name in CAPTURES:
            g = read(os.path.join(a.goldens, 'Blend_surface', name + '.png'))
            p = read(os.path.join(a.capture, 'Blend_surface::' + name + '.png'))
            for i, half, y, l in boxes():
                p[y:y + S // 2, l:l + S] = host_pred[(label, name, i, half)]
            d = np.abs(g - p)
            rgb, al = d[..., :3].max(axis=2), d[..., 3]
            differing = int(((rgb > 0) | (al > 0)).sum())
            obo = int(((rgb <= 1) & (al <= 1) & ((rgb > 0) | (al > 0))).sum())
            tot += differing - obo
            print('  %-40s %-24s differing %6d structural %6d'
                  % (label, name, differing, differing - obo))
        print('  %-40s TOTAL structural %d' % (label, tot))
    best = fits[0] if fits else rows[0]
    q = QIN[best[2]]
    r = RD.get(best[3])
    o, s = QOUT[best[4]], SMP[best[5]]
    print('\npricing %s against %s' % (best[2:], a.capture))
    tot_now = tot_pred = 0
    for name in CAPTURES:
        g = read(os.path.join(a.goldens, 'Blend_surface', name + '.png'))
        c = read(os.path.join(a.capture, 'Blend_surface::' + name + '.png'))
        p = c.copy()
        for i, half, y, l in boxes():
            p[y:y + S // 2, l:l + S] = predict(name, i, half, q, r, o, s)
        for label, img in (('now', c), ('pred', p)):
            d = np.abs(g - img)
            rgb, al = d[..., :3].max(axis=2), d[..., 3]
            differing = int(((rgb > 0) | (al > 0)).sum())
            obo = int(((rgb <= 1) & (al <= 1) & ((rgb > 0) | (al > 0))).sum())
            print('  %-24s %-4s differing %6d  off_by_one %6d  structural %6d'
                  % (name, label, differing, obo, differing - obo))
            if label == 'now':
                tot_now += differing - obo
            else:
                tot_pred += differing - obo
    print('  structural total: now %d -> predicted %d' % (tot_now, tot_pred))


if __name__ == '__main__':
    main()
