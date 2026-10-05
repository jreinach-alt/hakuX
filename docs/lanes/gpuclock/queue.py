#!/usr/bin/env python3
"""What the dispatcher holds right now: queued and running requests (device,
requester, title, seconds) and the device holds. Read-only.

    queue.py [requester substring]
"""
import json, os, sys

D = '/home/justin/hakux-work/dispatch'
want = sys.argv[1] if len(sys.argv) > 1 else ''
for sub in ('running', 'queue'):
    for f in sorted(os.listdir(os.path.join(D, sub))):
        if not f.endswith('.req'):
            continue
        try:
            r = json.load(open(os.path.join(D, sub, f)))
        except Exception:
            continue
        if want and want not in f:
            continue
        print('%-7s %-62s %-5s %-34s %s %s' % (sub, f[:62], r.get('device'), str(r.get('title') or r.get('suites') or '')[:34],
                                            r.get('seconds'), ','.join(r.get('env') or [])))
for f in sorted(os.listdir(os.path.join(D, 'hold'))):
    p = os.path.join(D, 'hold', f)
    if os.path.isfile(p):
        print('hold', f, open(p, errors='replace').read().strip()[:200])
