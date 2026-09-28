#!/usr/bin/env python3
"""The Signal timing suite's 500-quad reps, read per rep and not per median.

    python3 stmodes.py [--split 40] <result id> ...
    python3 stmodes.py --selftest

lane.notify488 read ST_Done_DOA's submit (first draw -> last kick) as 93.7 ms
and ST_Done_DOA_Read's as 8.9 ms, both medians. A median of a two-humped
distribution says which hump holds more than half the reps and nothing else,
so this prints, per test of a result:

  the share of reps whose submit is over --split ms (the slow hump), and each
  hump's own median;
  kick -> semaphore for each hump;
  the rep's cost on the pusher's side: submit + kick -> semaphore (+ read);
  how a slow rep follows a slow or a fast one (the transition counts), which
  separates a state the previous rep leaves behind from an independent draw.

Input: the suite's own <test>.txt files in the result's captures1/, raw
counter ticks at the `freq_hz` the file names.
"""
import argparse
import os
import sys
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
TESTS = ('ST_Done_Tiny', 'ST_Done_DOA', 'ST_Done_DOA_Read')


def parse(text):
    freq, rows, cols = None, [], None
    for l in text.splitlines():
        if l.startswith('freq_hz'):
            freq = float(l.split()[1])
        elif l.startswith('start\t'):
            cols = l.split('\t')
        elif cols and l and l[0].isdigit():
            v = l.split('\t')
            if len(v) == len(cols):
                rows.append(dict(zip(cols, (int(x) for x in v))))
    return freq, rows


def reps(freq, rows):
    out = []
    for i, r in enumerate(rows):
        ms = lambda t: t * 1000.0 / freq
        d = {'submit': ms(r['kick'] - r['start']),
             'sem': ms(r['semaphore_seen'] - r['kick']) if r['semaphore_seen'] else None,
             'read': ms(r['read_ticks']),
             'idle': ms(r['start'] - rows[i - 1]['kick']) if i else None}
        out.append(d)
    return out


def summarize(rp, split):
    slow = [r for r in rp if r['submit'] > split]
    fast = [r for r in rp if r['submit'] <= split]
    med = lambda v: median(v) if v else float('nan')
    s = {'n': len(rp), 'slow': len(slow),
         'submit_all': med([r['submit'] for r in rp]),
         'submit_fast': med([r['submit'] for r in fast]),
         'submit_slow': med([r['submit'] for r in slow]),
         'sem_fast': med([r['sem'] for r in fast if r['sem'] is not None]),
         'sem_slow': med([r['sem'] for r in slow if r['sem'] is not None]),
         'cost_fast': med([r['submit'] + (r['sem'] or 0) + r['read'] for r in fast]),
         'cost_slow': med([r['submit'] + (r['sem'] or 0) + r['read'] for r in slow]),
         'cost_mean': sum(r['submit'] + (r['sem'] or 0) + r['read'] for r in rp)
         / max(1, len(rp))}
    tr = {'ff': 0, 'fs': 0, 'sf': 0, 'ss': 0}
    for a, b in zip(rp, rp[1:]):
        tr[('s' if a['submit'] > split else 'f') +
           ('s' if b['submit'] > split else 'f')] += 1
    s['tr'] = tr
    s['p_s_after_s'] = tr['ss'] / max(1, tr['ss'] + tr['sf'])
    s['p_s_after_f'] = tr['fs'] / max(1, tr['fs'] + tr['ff'])
    return s


def show(name, s):
    print('   %-17s reps=%d slow=%d (%.0f%%) | submit median all=%.1f fast=%.1f '
          'slow=%.1f | kick->sem fast=%.3f slow=%.3f | rep cost fast=%.1f '
          'slow=%.1f mean=%.1f'
          % (name, s['n'], s['slow'], 100.0 * s['slow'] / max(1, s['n']),
             s['submit_all'], s['submit_fast'], s['submit_slow'], s['sem_fast'],
             s['sem_slow'], s['cost_fast'], s['cost_slow'], s['cost_mean']))
    t = s['tr']
    print('   %-17s after a slow rep: slow %d, fast %d (%.0f%% slow) | after a '
          'fast rep: slow %d, fast %d (%.0f%% slow)'
          % ('', t['ss'], t['sf'], 100 * s['p_s_after_s'], t['fs'], t['ff'],
             100 * s['p_s_after_f']))


def selftest():
    """Ten reps at 1 kHz ticks: fast, slow, slow, fast, ... with a semaphore
    that is late only on fast reps, and one rep with no semaphore."""
    lines = ['freq_hz 1000', 'start\tkick\tsemaphore_seen\tread_ticks']
    t = 0
    kinds = 'fssfssfssf'
    for i, k in enumerate(kinds):
        sub = 8 if k == 'f' else 90
        sem = 7 if k == 'f' else 1
        seen = 0 if i == 9 else t + sub + sem
        lines.append('%d\t%d\t%d\t%d' % (t, t + sub, seen, 2))
        t += 300
    freq, rows = parse('\n'.join(lines))
    s = summarize(reps(freq, rows), 40)
    want = [(s['n'], 10), (s['slow'], 6), (s['submit_fast'], 8),
            (s['submit_slow'], 90), (s['sem_fast'], 7), (s['sem_slow'], 1),
            (s['cost_slow'], 93), (s['tr']['ss'], 3), (s['tr']['sf'], 3),
            (s['tr']['fs'], 3), (s['tr']['ff'], 0), (s['submit_all'], 90)]
    bad = [(i, g, w) for i, (g, w) in enumerate(want) if abs(g - w) > 1e-6]
    for i, g, w in bad:
        print('selftest FAIL field %d: got %r, want %r' % (i, g, w))
    print('selftest %s' % ('FAIL' if bad else 'ok: %d fields' % len(want)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', type=float, default=40.0)
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('runs', nargs='*')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    for run in a.runs:
        print(run)
        for t in TESTS:
            p = R + run + '/captures1/Signal_timing::' + t + '.txt'
            if not os.path.exists(p):
                print('   %-17s no file' % t)
                continue
            freq, rows = parse(open(p, errors='replace').read())
            if not freq or not rows:
                print('   %-17s unreadable (freq=%r rows=%d)' % (t, freq, len(rows)))
                continue
            show(t, summarize(reps(freq, rows), a.split))


if __name__ == '__main__':
    main()
