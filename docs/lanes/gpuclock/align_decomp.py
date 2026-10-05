#!/usr/bin/env python3
"""The vCPU split of a gpuclock pair, scene-matched with the lag align.py found.

    align_decomp.py DECOMP.tsv LOW_RUN HIGH_RUN LAG [--bin 2] [--seg 30]

DECOMP.tsv is near30's decompose.py --tsv over both runs (2 s rows, t from
`mark gameplay`). The high arm's t is shifted by LAG (align.py's, high arm
later by this), both arms are binned, and over the matched bins it prints the
medians of F, guest busy / idle (and the idle's timer-woken part), the vCPU
thread's on-CPU (v_run) and blocked (v_blk) ms per frame, and the render
thread's busy share, per arm and as high minus low: which part of the frame
the clock moved.
"""
import argparse, statistics as st

ap = argparse.ArgumentParser()
ap.add_argument('tsv')
ap.add_argument('low')
ap.add_argument('high')
ap.add_argument('lag', type=float)
ap.add_argument('--bin', type=float, default=2.0)
ap.add_argument('--seg', type=float, default=30.0)
a = ap.parse_args()
COLS = ('F', 'gbusy', 'gidle', 'timer_ms', 'v_run', 'v_blk', 'rthr')
rows = {a.low: [], a.high: []}
hdr = None
for line in open(a.tsv):
    p = line.rstrip('\n').split('\t')
    if hdr is None:
        hdr = p
        continue
    r = dict(zip(hdr, p))
    if r['run'] in rows:
        try:
            rows[r['run']].append({k: float(r[k]) for k in ('t',) + COLS})
        except ValueError:
            pass


def bins(ws, shift):
    b = {}
    for w in ws:
        t = w['t'] - shift
        if t >= 0:
            b.setdefault(int(t // a.bin), []).append(w)
    return {k: {c: st.median(w[c] for w in v) for c in COLS} for k, v in b.items()}


lo, hi = bins(rows[a.low], 0.0), bins(rows[a.high], a.lag)
ks = sorted(set(lo) & set(hi))
print('matched bins %d (lag %+.0f s)' % (len(ks), a.lag))
print('%-9s %4s | ' % ('segment', 'n') + ' '.join('%13s' % c for c in COLS))


def line(name, kk):
    cells = []
    for c in COLS:
        l, h = st.median(lo[k][c] for k in kk), st.median(hi[k][c] for k in kk)
        cells.append('%5.1f>%5.1f%+3.0f' % (l, h, h - l) if c != 'rthr' else '%6.0f>%3.0f%%  ' % (l, h))
    print('%-9s %4d | ' % (name, len(kk)) + ' '.join('%13s' % x for x in cells))


line('all', ks)
for s0 in range(0, int(max(ks) * a.bin) + 1, int(a.seg)):
    kk = [k for k in ks if s0 <= k * a.bin < s0 + a.seg]
    if len(kk) >= 3:
        line('%d-%d' % (s0, s0 + a.seg), kk)
