#!/usr/bin/env python3
"""Print result.json and request.json of named result dirs (lane.uberspike569)."""
import json
import os
import sys

d = os.environ.get('DISPATCH_DIR') or os.path.expanduser('~/hakux-work/dispatch')
for rid in sys.argv[1:]:
    p = os.path.join(d, 'results', rid)
    print('====', rid)
    for f in ('result.json', 'request.json'):
        fp = os.path.join(p, f)
        if os.path.exists(fp):
            j = json.load(open(fp))
            print('--', f)
            print(json.dumps(j, indent=None, sort_keys=True)[:2500])
