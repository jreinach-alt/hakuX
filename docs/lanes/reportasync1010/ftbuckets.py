#!/usr/bin/env python3
"""The frametrace pair's other side: the guest vCPU, and which side misses 2 VBLANKs (#433, lane.reportasync1010).

    ftbuckets.py <A dir> <B dir>

Same runs, windows and frame selection as ftpair.py (which judges the registered prediction; this does
not). ftpair.py splits the PFIFO thread's row. This prints, per window, for all frames and heavy (vb >= 3):

  vCPU     v_run (on CPU, the guest's idle spin included), gidle (that spin), work = v_run - gidle + v_rq
           (frametrace's own RUN charge, profile.h hakux_ft_attribute), v_blk, and lockw: the vCPU's wait for
           pfifo.lock in user_write (user.c:92-95, DMA_PUT), which no holder is attributed to (UNATTR)
  busy     PFIFO busy = P - pidle, and guest busy = work + v_blk: each thread's non-idle time in the frame
  > 2 vb   the share of frames where that busy time exceeds 2 VBLANKs (2 x vbp, the frame's own period):
           on those frames that thread alone could not have made 30 fps. Guest busy is also shown without
           lockw. That column is a bound, not a prediction: it assumes the guest's wait would vanish
           with nothing taking its place.
  ireq     the interval frametrace infers (profile.h ft_ireq: the smallest VBLANK count used by >= 5 % of
           the last 256 flips). It sets the deadline D the `cls` column is judged against, so `cls` is
           comparable between two runs only when ireq is.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ftpair  # noqa: E402


def ms(fr, f):
    return sum(f(r) for r in fr) / len(fr) / 1000.0


def pct(fr, f):
    return 100.0 * sum(1 for r in fr if f(r)) / len(fr)


def work(r):
    return r['v_run'] - (r['gidle'] or 0) + (r['v_rq'] or 0)


def gbusy(r):
    return work(r) + r['v_blk']


def pbusy(r):
    return r['P'] - r['pidle']


def line(name, fr):
    if not fr:
        return f"  {name:6s} (no frames)"
    two = lambda r: 2 * r['vbp']  # noqa: E731
    ireq = Counter(r['ireq'] for r in fr)
    cls = Counter(r['cls'] for r in fr)
    return (f"  {name:6s} n={len(fr):4d}  P {ms(fr, lambda r: r['P']):5.1f}  "
            f"vCPU: v_run {ms(fr, lambda r: r['v_run']):5.1f} gidle {ms(fr, lambda r: r['gidle'] or 0):5.1f} "
            f"work {ms(fr, work):5.1f} v_blk {ms(fr, lambda r: r['v_blk']):5.1f} lockw {ms(fr, lambda r: r['lockw']):5.2f}\n"
            f"         busy: PFIFO {ms(fr, pbusy):5.1f} guest {ms(fr, gbusy):5.1f} "
            f"(w/o lockw {ms(fr, lambda r: gbusy(r) - r['lockw']):5.1f})   "
            f"> 2 vb: PFIFO {pct(fr, lambda r: pbusy(r) > two(r)):3.0f} %, "
            f"guest {pct(fr, lambda r: gbusy(r) > two(r)):3.0f} % "
            f"(w/o lockw {pct(fr, lambda r: gbusy(r) - r['lockw'] > two(r)):3.0f} %), "
            f"either {pct(fr, lambda r: pbusy(r) > two(r) or gbusy(r) > two(r)):3.0f} % "
            f"(w/o lockw {pct(fr, lambda r: pbusy(r) > two(r) or gbusy(r) - r['lockw'] > two(r)):3.0f} %)\n"
            f"         ireq " + ' '.join(f"{k}:{100 * v / len(fr):.0f}%" for k, v in sorted(ireq.items()))
            + "   cls " + ' '.join(f"{k}:{100 * v / len(fr):.0f}%" for k, v in cls.most_common()))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    runs = [(k, d, ftpair.load(d)) for k, d in zip('AB', sys.argv[1:])]
    if not all(r for _, _, r in runs):
        print('missing frametrace or marks')
        return 2
    for name, _, lo, hi in ftpair.WINDOWS:
        print(f"\n{name}: frame end in mark{lo:+.1f} .. mark{hi:+.1f} s, ms per frame")
        for k, d, r in runs:
            print(f" {k} {os.path.basename(d)}")
            print(line('all', r[name]))
            print(line('heavy', [f for f in r[name] if (f.get('vb') or 0) >= 3]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
