"""List soaks of the lane's titles: device, seconds, route, env, and where `mark gameplay` fell."""
import json
import os
import re
import sys

D = '/home/justin/hakux-work/dispatch/results'
pat = re.compile(sys.argv[1] if len(sys.argv) > 1 else
                 r'Crimson|Grand Theft Auto|San Andreas|MechAssault 2|MechAssault_2|Lone Wolf', re.I)
rows = []
for rid in os.listdir(D):
    p = os.path.join(D, rid, 'request.json')
    try:
        q = json.load(open(p))
    except Exception:
        continue
    t = q.get('title') or ''
    if not pat.search(t):
        continue
    try:
        r = json.load(open(os.path.join(D, rid, 'result.json')))
    except Exception:
        r = {}
    dev = r.get('device_label') or q.get('device')
    marks = []
    lg = os.path.join(D, rid, 'run.log')
    if os.path.exists(lg):
        for line in open(lg, errors='replace'):
            if 'mark ' in line or 'COOLDOWN' in line or 'PERF: regimen' in line:
                marks.append(line.strip()[:110])
    rows.append((os.path.getmtime(p), rid, dev, q.get('seconds'), q.get('route_name'),
                 q.get('env'), t[:45], marks[:6]))
for row in sorted(rows)[-int(os.environ.get('N', '25')):]:
    print(*row[1:7], sep=' | ')
    for m in row[7]:
        print('     ', m)
