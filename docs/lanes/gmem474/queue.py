#!/usr/bin/env python3
"""Queue lane.gmem474 runs exactly as their prediction registers them.

    python3 docs/lanes/gmem474/queue.py <doa|auf|crimson> <run> [<run> ...]

<run> is A1, B, C, D or A2. Title, device, route, seconds, ref, env and pull
glob are all read from docs/testing/predictions/gmem474-<key>.json, so a
queued run cannot drift from the registered one. Release priority
(HAKUX_RELEASE_PRIO=1): #474 is on the critical path. Prints request.sh's
output; the request id is on its `queued` line.
"""
import json
import os
import subprocess
import sys

key, runs = sys.argv[1], sys.argv[2:]
pred = 'docs/testing/predictions/gmem474-%s.json' % key
d = json.load(open(pred))
for r in runs:
    run = d['runs'][r]
    cmd = ['docs/testing/request.sh', '--who', 'lane.gmem474',
           '--purpose', '#474 gmem474 %s %s: %s' % (key, r, run['arm']),
           '--issue', '474', '--title', d['title'], '--device', d['device'],
           '--route', d['route'], '--seconds', str(d['seconds']), '--perflog',
           '--ref', d['a_ref'], '--pull', run['pull'], '--expect', pred]
    for e in run['env']:
        cmd += ['--env', e]
    env = dict(os.environ, HAKUX_RELEASE_PRIO='1')
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print('== %s %s rc=%d' % (key, r, p.returncode))
    print(p.stdout.strip())
    if p.returncode:
        print(p.stderr.strip())
        sys.exit(p.returncode)
    print('\n'.join(l for l in p.stderr.splitlines() if 'queued' in l or 'WARN' in l or 'pilot' in l.lower()))
