#!/usr/bin/env python3
"""lane.kabukistall: per-create cost and miss classes from a soak's [shd413] lines.

Usage: ks_creates.py <result dir> [min_dpn]

One row per [shd413] line (60 guest frames) with dpn >= min_dpn (default 10):
  wall s since `mark gameplay`, dt_ms, dpn (pipelines created), dpc_ms and its
  per-create mean, dvs/dgs/dfs_ms (stage compile ms), and kd= (sync misses per
  ShaderState class differing from the previous binding: VP/FF/CB/TX/FL/PO/GE,
  NONE, no-prev; profile.c nv2a_profile_shader_keydiff). A TOTAL row sums them.
"""
import os, re, sys
from datetime import datetime

KD = ('VP', 'FF', 'CB', 'TX', 'FL', 'PO', 'GE', 'NONE', 'noprev')


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f').timestamp()


def main():
    d = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    mark = None
    tot = dict(dpn=0, dpc=0.0, dvs=0.0, dgs=0.0, dfs=0.0, kd=[0] * 9)
    print('%8s %7s %5s %9s %7s %8s %8s %8s  %s' % (
        't_mark', 'dt_ms', 'dpn', 'dpc_ms', 'ms/cr', 'dvs_ms', 'dgs_ms', 'dfs_ms',
        ' '.join(KD)))
    for l in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if len(l) < 20 or not l[0].isdigit():
            continue
        if 'mark gameplay' in l and mark is None:
            mark = ts(l)
        if '[shd413]' not in l:
            continue
        g = lambda k: float(re.search(r'\b%s=([\d.]+)' % k, l).group(1))
        dpn = int(g('dpn'))
        if dpn < lo:
            continue
        kd = [int(x) for x in re.search(r'kd=([\d/]+)', l).group(1).split('/')]
        row = dict(dpn=dpn, dpc=g('dpc_ms'), dvs=g('dvs_ms'), dgs=g('dgs_ms'),
                   dfs=g('dfs_ms'))
        print('%8s %7d %5d %9.1f %7.1f %8.1f %8.1f %8.1f  %s' % (
            'pre' if mark is None else '%.1f' % (ts(l) - mark), g('dt_ms'), dpn, row['dpc'], row['dpc'] / dpn,
            row['dvs'], row['dgs'], row['dfs'], ' '.join(map(str, kd))))
        if mark is not None and ts(l) >= mark:
            for k in row:
                tot[k] += row[k]
            tot['kd'] = [a + b for a, b in zip(tot['kd'], kd)]
    if tot['dpn']:
        print('%8s %7s %5d %9.1f %7.1f %8.1f %8.1f %8.1f  %s  (gameplay rows only)' % (
            'TOTAL', '', tot['dpn'], tot['dpc'], tot['dpc'] / tot['dpn'], tot['dvs'],
            tot['dgs'], tot['dfs'], ' '.join(map(str, tot['kd']))))


main()
