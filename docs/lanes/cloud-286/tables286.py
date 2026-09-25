#!/usr/bin/env python3
"""Aggregate decompose286.tsv by status (from the run's scores1.tsv) and by
primitive x flag. |d|=2 is split out of every class: it is two one-step
floors stacked, not a region defect."""
import collections
import csv
import sys

here = sys.argv[1] if len(sys.argv) > 1 else 'docs/lanes/cloud-286/decompose286.tsv'
SCORES = ('/home/justin/hakux-work/dispatch/results/'
          '0-a-now-8e683b3a26-002-3D_primitive/scores1.tsv')
status = {r['test']: r['status'] for r in csv.DictReader(open(SCORES), delimiter='\t')}
rows = list(csv.DictReader(open(here), delimiter='\t'))
for r in rows:
    for k in r:
        if k not in ('capture', 'prim', 'flag'):
            r[k] = int(r[k])
    r['status'] = status[r['capture']]
    r['smooth'] = r['fp-alpha'] + r['fp-rgb'] - r['fp-rgb_d2']
    r['smooth_d2'] = r['fp-rgb_d2']
    r['shared_gt2'] = r['shared'] - r['shared_d2']
    r['aa_gt2'] = r['aa-path'] - r['aa-path_d2']
    r['wash_d2'] = r['smooth_d2'] + r['shared_d2'] + r['aa-path_d2'] + r['other']

    r['out'] = r['shared'] + r['aa-path'] + r['other']
    r['out_still'] = r['out'] - r['out_moved']

COLS = ['wrong', 'smooth', 'smooth_d2', 'out_moved', 'out_moved_gt2', 'out_still',
        'out_still_gt2', 'ceiling_gold', 'cons_vs_gold']


def table(key):
    agg = collections.OrderedDict()
    for r in sorted(rows, key=key):
        a = agg.setdefault(key(r), collections.Counter())
        a['n'] += 1
        for c in COLS:
            a[c] += r[c]
    print('| group | n | ' + ' | '.join(COLS) + ' |')
    print('|---|---:|' + '---:|' * len(COLS))
    tot = collections.Counter()
    for k, a in agg.items():
        tot.update(a)
        print('| %s | %d | ' % (' '.join(k) if isinstance(k, tuple) else k, a['n'])
              + ' | '.join('{:,}'.format(a[c]) for c in COLS) + ' |')
    print('| **total** | %d | ' % tot['n'] + ' | '.join('{:,}'.format(tot[c]) for c in COLS) + ' |')
    print()


table(lambda r: r['status'])
table(lambda r: (r['status'], r['prim'], r['flag']))
table(lambda r: (r['prim'], r['flag']))
