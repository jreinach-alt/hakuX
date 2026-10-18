#!/usr/bin/env python3
"""perflog1016 (#433): list recent Nova soaks, to pick the A/B scene.

    python3 docs/lanes/perflog1016/scan_soaks.py [--since 2026-10-10] [--device nova]

One row per result dir with a title: queued time, ref, title, route, seconds,
perflog, env, verdict, and the seconds from soak start to the first
`mark gameplay` (or `mark play`) on hakuX-route.
"""
import argparse
import glob
import json
import os
import re

RES = '/home/justin/hakux-work/dispatch/results'
TS = re.compile(r'^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d+)')


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    _, _, h, mi, s, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0


def mark_offset(path):
    start = None
    try:
        with open(path, errors='replace') as f:
            for line in f:
                if 'hakuX-route' not in line:
                    continue
                if 'soak start' in line and start is None:
                    start = secs(line)
                elif re.search(r'mark (gameplay|play)\b', line) and start is not None:
                    t = secs(line)
                    return None if t is None else round(t - start)
    except OSError:
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='2026-10-10')
    ap.add_argument('--device', default='nova')
    a = ap.parse_args()
    rows = []
    for rq in glob.glob(os.path.join(RES, '*', 'request.json')):
        d = os.path.dirname(rq)
        try:
            r = json.load(open(rq))
        except (OSError, ValueError):
            continue
        if not r.get('title') or (r.get('queued_utc') or '') < a.since:
            continue
        if r.get('device') and r.get('device') != a.device:
            continue
        v = {}
        try:
            v = json.load(open(os.path.join(d, 'verdict.json')))
        except (OSError, ValueError):
            pass
        verdict = v.get('verdict') or v.get('result') or ''
        rows.append((r.get('queued_utc', ''), os.path.basename(d),
                     r.get('ref', '')[:10], r.get('title', '')[:40],
                     r.get('route_name', ''), r.get('seconds'),
                     r.get('perflog') or '-', verdict,
                     mark_offset(os.path.join(d, 'logcat.txt'))))
    for row in sorted(rows):
        print('\t'.join(str(x) for x in row))


if __name__ == '__main__':
    main()
