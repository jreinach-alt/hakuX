#!/usr/bin/env python3
"""Zone temperatures at fixed minutes from `mark play`, for a Part C pair.

Usage: thor_pair_zones.py <result id>:<mark_from_start_s> ...
The mark offset is regimen_read.py's mark_from_start_s for that run.
"""
import json
import sys

B = '/home/justin/hakux-work/dispatch/results/'
KEYS = ('xo-therm', 'battery', 'usb-therm', 'pa', 'gpuss-0', 'cpu-1-0', 'ddr')

for arg in sys.argv[1:]:
    rid, mark = arg.rsplit(':', 1)
    mark = float(mark)
    rows = [json.loads(l) for l in open(B + rid + '/thermal.jsonl') if l.strip()]
    t0 = rows[0]['t']
    print(rid)
    seen = set()
    for r in rows:
        m = (r['t'] - t0 - mark) / 60
        k = round(m)
        if k in (-4, 0, 5, 10, 15, 20, 25, 30) and k not in seen:
            seen.add(k)
            tz = r['tz']
            z = {n: round(v / 1000, 1) for _, n, v in tz if n in KEYS}
            print('  min %5.1f' % m, z)
