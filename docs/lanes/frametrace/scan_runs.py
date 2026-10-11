#!/usr/bin/env python3
"""List recent dispatcher results for titles matching a pattern.

    scan_runs.py [pattern ...] [--n 600]

Prints id | title | requested device / ran on | route | status, newest last.
Read-only over $DISPATCH_DIR/results.
"""
import json
import os
import sys

R = os.path.join(os.environ.get('DISPATCH_DIR',
                                '/home/justin/hakux-work/dispatch'), 'results')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
n = 600
if '--n' in sys.argv:
    n = int(sys.argv[sys.argv.index('--n') + 1])
    args = [a for a in args if a != str(n)]
pats = [a.lower() for a in args] or ['simpson', 'forza', 'tron', 'nightfire']


def mtime(e):
    try:
        return os.path.getmtime(os.path.join(R, e))
    except OSError:
        return 0


ents = sorted(os.listdir(R), key=mtime)[-n:]
for e in ents:
    try:
        j = json.load(open(os.path.join(R, e, 'request.json')))
    except Exception:
        continue
    t = j.get('title') or ''
    if not any(p in t.lower() for p in pats):
        continue
    res = {}
    try:
        res = json.load(open(os.path.join(R, e, 'result.json')))
    except Exception:
        pass
    ran = res.get('device') or res.get('device_label') or res.get('serial') or ''
    print(e, '|', t, '|', j.get('device') or '-', '/', ran, '|',
          (j.get("route") or "-").replace("\n", " ")[:90], "|", res.get("status") or res.get("verdict")
          or res.get('state') or '')
