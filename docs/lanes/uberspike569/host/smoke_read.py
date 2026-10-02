#!/usr/bin/env python3
"""Read a smoke soak's result dir: status, crash lines, and the uber/gpl counters."""
import json
import sys

D = '/home/justin/hakux-work/dispatch/results/'
PATS = ['FATAL', 'SIGSEGV', 'SIGABRT', 'Abort', 'vsh-uber', 'uber569', 'gpl569',
        'VK_ERROR', 'hakuX-pace', 'Validation']

for rid in sys.argv[1:]:
    p = D + rid
    r = json.load(open(p + '/result.json'))
    print('==', rid, json.dumps(r)[:600])
    print(open(p + '/run.log', errors='replace').read()[-800:])
    lines = open(p + '/logcat.txt', errors='replace').read().splitlines()
    print('logcat lines', len(lines))
    for pat in PATS:
        m = [l for l in lines if pat in l]
        print('  %s: %d' % (pat, len(m)))
        for l in (m[:3] + ['   ...'] + m[-4:] if len(m) > 7 else m):
            print('     ', l[:300])
