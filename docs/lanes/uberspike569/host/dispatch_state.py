#!/usr/bin/env python3
"""Holds, running requests and the queue head of the dispatcher (lane.uberspike569, read only)."""
import json
import os

d = os.environ.get('DISPATCH_DIR') or os.path.expanduser('~/hakux-work/dispatch')
for sub in ('hold', 'running'):
    p = os.path.join(d, sub)
    print('==', sub)
    if os.path.isdir(p):
        for n in sorted(os.listdir(p)):
            fp = os.path.join(p, n)
            body = ''
            if os.path.isfile(fp):
                body = open(fp, errors='replace').read()[:300].replace('\n', ' | ')
            print(' ', n, body)
print('== queue')
q = os.path.join(d, 'queue')
for n in sorted(os.listdir(q)):
    try:
        j = json.load(open(os.path.join(q, n)))
        print(' ', n, j.get('device'), j.get('priority'), j.get('requester'), (j.get('title') or j.get('program') or '')[:40])
    except Exception as e:  # noqa: BLE001
        print(' ', n, 'unreadable', e)
log = os.path.join(d, 'logs', 'dispatcher.log')
if os.path.exists(log):
    print('== dispatcher.log tail')
    print(''.join(open(log, errors='replace').readlines()[-15:]))
