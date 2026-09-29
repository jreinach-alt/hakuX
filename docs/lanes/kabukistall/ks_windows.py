#!/usr/bin/env python3
"""lane.kabukistall: one row per 60-guest-frame perf window of a soak's logcat.

Usage: ks_windows.py <result dir> [--all]

Joins, per window (the hakuX-perf gfps line and the lines logged with it):
  wall s since `mark gameplay`, window ms, gfps, G max (ms between guest flips),
  [shd413] dph/dpm (pipeline hits/misses) and dsh/dsm (shader), the phase line's
  Shd, Pipe and Tot ms/frame. Without --all only windows over 1500 ms print.
"""
import json, os, re, sys
from datetime import datetime


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f').timestamp()


def main():
    d = sys.argv[1]
    allrows = '--all' in sys.argv
    try:
        r = json.load(open(os.path.join(d, 'result.json')))
        print('# shader_cache:', r.get('shader_cache'), ' apk', r.get('apk_sha'),
              ' device', r.get('device_label'))
    except Exception as e:  # noqa
        print('# no result.json', e)
    L = open(os.path.join(d, 'logcat.txt'), errors='replace').read().splitlines()
    mark = None
    cur = {}
    rows = []
    for l in L:
        if len(l) < 20 or not l[0].isdigit():
            continue
        if 'mark gameplay' in l and mark is None:
            mark = ts(l)
        body = l.split('): ', 1)[-1]
        if body.startswith('gfps='):
            if cur:
                rows.append(cur)
            m = re.search(r'gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\)', body)
            cur = dict(t=ts(l), gfps=int(m.group(1)), gmax=float(m.group(4)))
        elif body.startswith('f=') and cur:
            m = re.search(r'ms=([\d.]+)', body)
            cur['ms'] = float(m.group(1))
        elif body.startswith('[shd413]') and cur:
            for k in ('dph', 'dpm', 'dsh', 'dsm'):
                cur[k] = int(re.search(r'\b%s=(\d+)' % k, body).group(1))
        elif body.startswith('Surf:') and cur:
            for k, pat in (('Shd', r'Shd:([\d.]+)'), ('Pipe', r'Pipe:([\d.]+)'),
                           ('Tot', r'Tot:([\d.]+)')):
                m = re.search(pat, body)
                cur[k] = float(m.group(1)) if m else None
    if cur:
        rows.append(cur)
    print('# mark', mark)
    print('%8s %8s %5s %8s %5s %5s %6s %6s %8s %8s %8s' % (
        't_mark', 'win_ms', 'gfps', 'Gmax', 'dph', 'dpm', 'dsh', 'dsm', 'Shd', 'Pipe', 'Tot'))
    for r in rows:
        if not allrows and r.get('ms', 0) < 1500:
            continue
        print('%8.1f %8.0f %5d %8.0f %5s %5s %6s %6s %8s %8s %8s' % (
            r['t'] - (mark or 0), r.get('ms', 0), r['gfps'], r['gmax'], r.get('dph'),
            r.get('dpm'), r.get('dsh'), r.get('dsm'), r.get('Shd'), r.get('Pipe'), r.get('Tot')))


main()
