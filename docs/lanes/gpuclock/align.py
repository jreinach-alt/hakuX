#!/usr/bin/env python3
"""Scene-matched reading of a gpuclock pair: the two arms' windows (from
gpuclock.py --tsv) put in 2 s bins of time since `mark gameplay`, the high
arm shifted by the lag that best correlates the two gms series (scripted
content -- cutscenes, a blind route -- replays at the same pace in both arms,
so equal time is equal scene once the lag is found), then per-bin ratios.

    align.py PAIR.tsv LOW_RUN HIGH_RUN [--bin 2] [--maxlag 30] [--upto S]

Prints the lag and its correlation, and over the matched bins: the median
per-bin gms ratio high/low and its elasticity e = -ln(ratio)/ln(MHz ratio),
the same for F (frame ms), the share of bins where the high arm's gms is
lower, and per 30 s segment the medians, so a reader can see whether the
effect holds in every scene or comes from one.

A matched bin is a bin both arms have a window in. With a correlation under
0.5 the lag is not trusted and the script says so (the arms did not replay
the same content, and the per-bin ratios compare different scenes).
"""
import argparse, math, statistics as st, sys

ap = argparse.ArgumentParser()
ap.add_argument('tsv')
ap.add_argument('low')
ap.add_argument('high')
ap.add_argument('--bin', type=float, default=2.0)
ap.add_argument('--maxlag', type=float, default=30.0)
ap.add_argument('--upto', type=float, default=1e9)
a = ap.parse_args()

rows = {a.low: [], a.high: []}
hdr = None
for line in open(a.tsv):
    p = line.rstrip('\n').split('\t')
    if hdr is None:
        hdr = p
        continue
    r = dict(zip(hdr, p))
    for k in rows:
        if r['run'].endswith(k) or k.endswith(r['run']):
            rows[k].append({x: float(r[x]) for x in ('t', 'F', 'gms', 'mhz', 'busy')})


def bins(ws, shift=0.0):
    b = {}
    for w in ws:
        t = w['t'] - shift
        if t < 0 or t > a.upto:
            continue
        b.setdefault(int(t // a.bin), []).append(w)
    return {k: {x: st.median(w[x] for w in v) for x in ('F', 'gms', 'mhz', 'busy')} for k, v in b.items()}


def corr(xs, ys):
    if len(xs) < 10:
        return -2
    mx, my = st.mean(xs), st.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return -2
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


lo = bins(rows[a.low])
best = None
steps = int(a.maxlag / a.bin)
for s in range(-steps, steps + 1):
    hi = bins(rows[a.high], s * a.bin)
    ks = sorted(set(lo) & set(hi))
    c = corr([math.log(lo[k]['gms']) for k in ks], [math.log(hi[k]['gms']) for k in ks])
    if best is None or c > best[0]:
        best = (c, s * a.bin, ks, hi)
c, lag, ks, hi = best
print('lag %+.0f s (high arm later by this), log-gms correlation %.2f over %d matched %.0f s bins%s'
      % (lag, c, len(ks), a.bin, '' if c >= 0.5 else '  ** under 0.5: the arms did not replay the same content; per-bin ratios are not scene-matched'))
if not ks:
    sys.exit(1)
mr = st.median(hi[k]['mhz'] / lo[k]['mhz'] for k in ks)
gr = [hi[k]['gms'] / lo[k]['gms'] for k in ks]
fr = [hi[k]['F'] / lo[k]['F'] for k in ks]
dG = [lo[k]['gms'] - hi[k]['gms'] for k in ks]
dF = [lo[k]['F'] - hi[k]['F'] for k in ks]
e = lambda r: -math.log(r) / math.log(mr) if mr > 1 else float('nan')
print('MHz ratio %.3f; gms ratio median %.3f (e %.2f, IQR of per-bin e %.2f..%.2f); high arm gms lower in %.0f%% of bins'
      % (mr, st.median(gr), e(st.median(gr)), *[e(q) for q in reversed(st.quantiles(gr, n=4)[::2])],
         100.0 * sum(1 for r in gr if r < 1) / len(gr)))
print('F ratio median %.3f (fps x%.3f); median per-bin dF %.2f ms against dGPU %.2f ms (dF/dG %.2f)'
      % (st.median(fr), 1 / st.median(fr), st.median(dF), st.median(dG), st.median(dF) / st.median(dG) if st.median(dG) else float('nan')))
print('%8s %5s | %7s %7s %6s | %7s %7s | %5s %5s' % ('segment', 'bins', 'gms lo', 'gms hi', 'e', 'F lo', 'F hi', 'busyL', 'busyH'))
seg = 30.0
for s0 in range(0, int(max(ks) * a.bin) + 1, int(seg)):
    kk = [k for k in ks if s0 <= k * a.bin < s0 + seg]
    if len(kk) < 3:
        continue
    gl, gh = st.median(lo[k]['gms'] for k in kk), st.median(hi[k]['gms'] for k in kk)
    print('%4d-%-3d %5d | %7.2f %7.2f %6.2f | %7.1f %7.1f | %5.0f %5.0f'
          % (s0, s0 + seg, len(kk), gl, gh, e(gh / gl), st.median(lo[k]['F'] for k in kk),
             st.median(hi[k]['F'] for k in kk), st.median(lo[k]['busy'] for k in kk), st.median(hi[k]['busy'] for k in kk)))
