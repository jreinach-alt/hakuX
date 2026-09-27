#!/usr/bin/env python3
"""Which guest stores land on code pages, over a window of a soak's logcat (#482, #424).

    codewrites.py <logcat.txt> <from s> <to s> [--anchor 'mark gameplay'] [--top N]

The window is [from, to] seconds after the anchor route line. Sums, over the
hakuX-pages lines inside it:
  - the `inval` line's ev (events), ov (discarded blocks whose bytes the guest
    actually wrote), sp (discarded blocks a range test would have spared), em
    (events that emptied the page, so it is re-armed), pr (arming walks), di
    (discards), cg (real code generations), iv (tb_gen_code calls), ih
    (recycled translations);
  - the `slow stores` line's per-page rows (pfn, n, va, off range): up to 8
    tracked code pages, n cumulative since boot, so a page's count in the
    window is its last n minus its first. A page first listed mid-window is
    counted from there: the per-page counts are lower bounds.
Rates are per second of the window and per displayed frame (flips counted
from hakuX-pace `f=` deltas in the window).
"""
import argparse
import collections
import re
from datetime import datetime


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('logcat')
    ap.add_argument('t0', type=float)
    ap.add_argument('t1', type=float)
    ap.add_argument('--anchor', default='mark gameplay')
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()
    lines = open(a.logcat, errors='replace').read().splitlines()
    anc = next(ts(l) for l in lines if 'hakuX-route' in l and a.anchor in l)
    inval = collections.Counter()
    pages = collections.Counter()
    pinfo = {}
    pfirst = {}
    nwin = 0
    flips = []
    first = last = None
    for l in lines:
        if len(l) < 18 or not l[0].isdigit():
            continue
        try:
            t = (ts(l) - anc).total_seconds()
        except ValueError:
            continue
        if t < a.t0 or t > a.t1:
            continue
        if 'hakuX-pace' in l:
            m = re.search(r' f=(\d+)', l)
            if m:
                flips.append((t, int(m.group(1))))
        if 'hakuX-pages' not in l:
            continue
        if ' inval ev=' in l:
            nwin += 1
            first = t if first is None else first
            last = t
            for k, v in re.findall(r' (ev|ov|sp|em|pr|di|cg|iv|ih|ins)=(\d+)', l):
                inval[k] += int(v)
        elif 'slow stores' in l:
            m = re.search(r'slow stores (\d+) \((\d+) reached', l)
            inval['slow'] += int(m.group(1))
            inval['reach'] += int(m.group(2))
            # n= is cumulative since boot (hakux_notdirty_hits is never reset):
            # keep the first and last value seen in the window
            for pfn, n, va, lo, hi in re.findall(r'pfn([0-9a-f]+) n=(\d+) va=([0-9a-f]+) off=([0-9a-f]+)\.\.([0-9a-f]+)', l):
                pfirst.setdefault(pfn, int(n))
                pages[pfn] = int(n) - pfirst[pfn]
                pinfo[pfn] = (va, lo, hi)
    if nwin < 2:
        raise SystemExit(f'{nwin} inval lines in the window: VOID')
    # the first line's counts cover the 120 frames BEFORE it, partly outside
    # the window; the span is taken from line to line, so drop the first line's
    # share by using (nwin - 1) windows over (last - first) seconds
    span = last - first
    scale = (nwin - 1) / nwin
    nfl = (flips[-1][1] - flips[0][1]) if len(flips) > 1 else 0
    fspan = (flips[-1][0] - flips[0][0]) if len(flips) > 1 else 0
    fps = nfl / fspan if fspan else 0
    print(f'window {a.t0:.0f}..{a.t1:.0f} s after "{a.anchor}": {nwin} inval lines over {span:.1f} s; '
          f'{fps:.2f} fps from hakuX-pace')
    print('per s / per frame:')
    for k in ('slow', 'reach', 'ev', 'di', 'ov', 'sp', 'em', 'pr', 'iv', 'cg', 'ih'):
        per_s = inval[k] * scale / span
        print(f'  {k:5s} {per_s:10.1f} /s  {per_s / fps if fps else 0:9.1f} /frame')
    if inval['di']:
        print(f'  discarded blocks the guest wrote (ov/di): {100 * inval["ov"] / inval["di"]:.2f}%; '
              f'spared by a range test (sp/di): {100 * inval["sp"] / inval["di"]:.2f}%; '
              f'recycled (ih/iv): {100 * inval["ih"] / max(1, inval["iv"]):.1f}%')
    tot = sum(pages.values())
    print(f'top code pages by slow stores (lower bounds; {tot} stores listed):')
    for pfn, n in pages.most_common(a.top):
        va, lo, hi = pinfo[pfn]
        per_s = n / span
        print(f'  pfn {pfn:>5s} va {va:>8s} off {lo}..{hi}  {per_s:8.1f} /s  {per_s / fps if fps else 0:7.1f} /frame  '
              f'{100 * n / max(1, inval["slow"] * scale):5.1f}% of slow stores')


if __name__ == '__main__':
    main()
