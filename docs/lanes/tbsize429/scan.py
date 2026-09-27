#!/usr/bin/env python3
"""Inventory the per-window counter lines of dispatch soak logs.

usage: scan.py tags <id>...          count line tags per run
       scan.py grep <pattern> <id>... print matching lines (first/last 3)
"""
import collections
import glob
import os
import re
import sys

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def log(rid):
    if os.path.isfile(rid):
        return rid
    d = glob.glob(R + '*' + rid + '*')
    return os.path.join(d[0], 'logcat.txt')


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == 'tags':
        for rid in args:
            c = collections.Counter()
            for ln in open(log(rid), errors='replace'):
                for t in re.findall(r'hakuX-[A-Za-z0-9]+|\[[a-z0-9]+\]', ln):
                    c[t] += 1
            print('==', rid)
            for t, n in c.most_common(25):
                print('  %6d %s' % (n, t))
    elif mode == 'pages':
        keys = ['ev', 'ov', 'sp', 'em', 'di', 'cg', 'ins', 'iv', 'ih']
        print('%-40s %4s ' % ('run', 'win') + ' '.join('%10s' % k for k in keys)
              + ' %7s %7s' % ('ins/cg', 'ov/vis'))
        for rid in args:
            tot = collections.Counter()
            n = 0
            for ln in open(log(rid), errors='replace'):
                if 'hakuX-pages' not in ln or 'inval ev=' not in ln:
                    continue
                n += 1
                for k, v in re.findall(r'\b([a-z]+)=(\d+)(?=[ /]|$)', ln):
                    if k in keys:
                        tot[k] += int(v)
            vis = tot['ov'] + tot['sp']
            print('%-40s %4d ' % (rid, n) + ' '.join('%10d' % tot[k] for k in keys)
                  + ' %7.2f %7.4f' % (tot['ins'] / max(tot['cg'], 1),
                                      tot['ov'] / max(vis, 1)))
    elif mode == 'tail':
        # Windows after the route's gameplay mark (or the second half of the
        # log when there is none): per-120-frame medians of the counters that
        # decide #429 -- real codegens, overlapping-store discards, empties.
        keys = ['ev', 'ov', 'em', 'di', 'cg', 'ins', 'iv', 'ih']
        print('%-40s %4s %5s ' % ('run', 'win', 'from') + ' '.join('%8s' % k for k in keys))
        for rid in args:
            rows, mark = [], None
            for ln in open(log(rid), errors='replace'):
                if 'hakuX-route' in ln and 'gameplay' in ln and mark is None:
                    mark = 'mark'
                    rows = []
                if 'hakuX-pages' in ln and 'inval ev=' in ln:
                    rows.append({k: int(v) for k, v in
                                 re.findall(r'\b([a-z]+)=(\d+)(?=[ /]|$)', ln)})
            if mark is None:
                rows = rows[len(rows) // 2:]
            med = {k: sorted(r.get(k, 0) for r in rows)[len(rows) // 2] if rows else -1
                   for k in keys}
            print('%-40s %4d %5s ' % (rid, len(rows), mark or 'half')
                  + ' '.join('%8d' % med[k] for k in keys))
    elif mode == 'grep':
        pat = re.compile(args[0])
        for rid in args[1:]:
            hits = [ln.rstrip() for ln in open(log(rid), errors='replace') if pat.search(ln)]
            print('==', rid, len(hits))
            for ln in hits[:3] + ['...'] + hits[-3:]:
                print('  ', ln[:400])


main()
