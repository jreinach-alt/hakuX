#!/usr/bin/env python3
"""Per-rep submit time and rep-to-rep cycle from a Signal_timing ST_Done_*.txt.

    python3 rep_cycle.py <result-id> [<result-id> ...]

kick_to_semaphore alone cannot show a wait that moved from the release into
the next rep's submission; the cycle (start[i+1] - start[i]) can.
"""
import os
import statistics as st
import sys

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
FREQ_MHZ = 3.375


def load(path):
    rows, hdr = [], None
    for line in open(path):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        if hdr is None and '\t' in line and not line[0].isdigit():
            hdr = line.split('\t')
            continue
        if hdr:
            rows.append(dict(zip(hdr, map(int, line.split('\t')))))
    return rows


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


for run in sys.argv[1:]:
    for test in ('ST_Done_Tiny', 'ST_Done_DOA', 'ST_Done_DOA_Read'):
        path = R + run + '/captures1/Signal_timing::' + test + '.txt'
        if not os.path.exists(path):
            continue
        r = load(path)
        sub = [(x['kick'] - x['start']) / FREQ_MHZ / 1000 for x in r]
        cyc = [(r[i + 1]['start'] - r[i]['start']) / FREQ_MHZ / 1000
               for i in range(len(r) - 1)]
        blocks = [round(st.median(sub[i:i + 30]), 1) for i in range(0, len(sub), 30)]
        print(f'{run[:44]:44} {test:16} submit ms/30-rep block {blocks}')
        print(f'{"":44} {"":16} cycle ms median {st.median(cyc):.1f} '
              f'p95 {pct(cyc, .95):.1f}')
