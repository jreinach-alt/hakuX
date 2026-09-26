#!/usr/bin/env python3
"""One-screen summary of a result dir: run.log, result.json essentials, the
logcat's span, crash-looking lines, and any [tlb68] lines.

    python3 runinfo.py <result-id-or-suffix> [...]
"""
import json
import os
import sys

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
CRASH = ('hakuX-crash', 'libc', 'DEBUG', 'unhandled', 'tombstone', 'SIGSEGV', 'abort')

for r in sys.argv[1:]:
    cands = sorted(d for d in os.listdir(R) if d == r or d.endswith(r) or r in d)
    for run in cands:
        p = R + run + '/'
        print('==', run, 'DONE' if os.path.exists(p + 'DONE') else
              ('ERROR' if os.path.exists(p + 'ERROR') else 'running'))
        if os.path.exists(p + 'run.log'):
            print('  run.log:', open(p + 'run.log').read().strip()[:200])
        if os.path.exists(p + 'result.json'):
            j = json.load(open(p + 'result.json'))
            for k in ('apk_sha', 'ref', 'logcat_lines', 'shader_cache', 'frames'):
                print('  %s: %s' % (k, j.get(k)))
        fr = p + 'frames'
        if os.path.isdir(fr):
            print('  frames:', len(os.listdir(fr)))
        if not os.path.exists(p + 'logcat.txt'):
            continue
        L = open(p + 'logcat.txt', errors='replace').read().splitlines()
        if len(L) > 1:
            print('  logcat lines %d, first %s, last %s' % (len(L), L[1][:18], L[-1][:18]))
        bad = [l for l in L if any(t in l for t in CRASH)]
        print('  crash-looking lines:', len(bad))
        for x in bad[:10]:
            print('    ' + x[:220])
        tl = [l for l in L if 'tlb68' in l]
        print('  [tlb68] lines:', len(tl))
        for x in tl[:2] + tl[-2:]:
            print('    ' + x[19:300])
