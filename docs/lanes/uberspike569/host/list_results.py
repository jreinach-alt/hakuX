#!/usr/bin/env python3
"""List this lane's result dirs with their result.json headline (lane.uberspike569)."""
import json
import os
import sys

d = os.environ.get('DISPATCH_DIR') or os.path.expanduser('~/hakux-work/dispatch')
keys = ('status', 'device', 'ref', 'sha', 'finished', 'exit', 'rc', 'void', 'title', 'req_id')
res = sorted(x for x in os.listdir(os.path.join(d, 'results')) if 'uberspike' in x)
for r in res:
    p = os.path.join(d, 'results', r)
    rj = os.path.join(p, 'result.json')
    info = {}
    if os.path.exists(rj):
        j = json.load(open(rj))
        info = dict((k, j[k]) for k in keys if k in j)
        if len(sys.argv) > 1 and sys.argv[1] == '-v':
            info = j
    print(r, sorted(os.listdir(p))[:14], info)
for extra in sys.argv[1:]:
    if extra != '-v' and os.path.exists(extra):
        print('----', extra)
        print(open(extra).read()[:3000])
