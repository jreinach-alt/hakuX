#!/usr/bin/env python3
"""List dispatch results by device and time window, or by title substring, with
the build (ref / apk_sha), env and fps figures each one carries.

    find_results.py --device nova --since '2026-10-04 18:00' --until '2026-10-05 00:00'
    find_results.py --title buffy
"""
import argparse
import glob
import json
import os
import time

D = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch')

ap = argparse.ArgumentParser()
ap.add_argument('--device')
ap.add_argument('--since')
ap.add_argument('--until')
ap.add_argument('--title')
args = ap.parse_args()


def ts(s):
    return time.mktime(time.strptime(s, '%Y-%m-%d %H:%M')) if s else None


since, until = ts(args.since), ts(args.until)
rows = []
for rdir in glob.glob(os.path.join(D, 'results', '*')):
    try:
        mt = os.path.getmtime(rdir)
    except OSError:
        continue
    if since and mt < since or until and mt > until:
        continue
    req, res, ver = {}, {}, {}
    for name, into in (('request.json', req), ('result.json', res),
                       ('verdict.json', ver)):
        p = os.path.join(rdir, name)
        if os.path.exists(p):
            try:
                into.update(json.load(open(p)))
            except Exception:
                pass
    dev = res.get('device') or req.get('device') or ver.get('device') or ''
    if args.device and args.device not in dev:
        continue
    title = req.get('title') or res.get('title') or ver.get('title') or ''
    if args.title and args.title.lower() not in title.lower():
        continue
    rows.append((mt, os.path.basename(rdir), dev, title[:34],
                 (req.get('ref') or res.get('ref') or '')[:10],
                 (res.get('apk_sha') or ver.get('apk_sha') or '')[:12],
                 req.get('env') or '', req.get('route') and 'route' or '',
                 ver.get('fps_window_median'), ver.get('fps_ok_share'),
                 req.get('seconds') or ''))
for r in sorted(rows):
    print(time.strftime('%m-%d %H:%M', time.localtime(r[0])), *r[1:], sep=' | ')
