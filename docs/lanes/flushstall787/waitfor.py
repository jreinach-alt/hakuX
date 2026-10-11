#!/usr/bin/env python3
"""Block until one of this lane's request ids changes state (running, done,
withdrawn) or the gradle output ends, or --max seconds pass. Prints the state.
A foreground wait in chunks under the Bash tool's limit.

usage: waitfor.py --max 560 <gradle output or -> <request id>...
"""
import os
import re
import sys
import time

R = '/home/justin/hakux-work/dispatch'
mx = float(sys.argv[sys.argv.index('--max') + 1])
args = [a for a in sys.argv[1:] if a not in ('--max', sys.argv[sys.argv.index('--max') + 1])]
build, ids = args[0], args[1:]


def state():
    s = []
    if build != '-' and os.path.exists(build):
        txt = open(build, errors='replace').read()
        m = re.findall(r'GRADLE_EXIT=\d+|BUILD FAILED|BUILD SUCCESSFUL', txt)
        s.append('build:' + (m[-1] if m else 'running'))
    for i in ids:
        if os.path.exists('%s/results/%s/DONE' % (R, i)):
            s.append(i + ':done')
        elif os.path.exists('%s/running/%s.req' % (R, i)):
            s.append(i + ':running')
        elif os.path.exists('%s/queue/%s.req' % (R, i)):
            s.append(i + ':queued')
        else:
            s.append(i + ':gone')
    return s


t0 = time.time()
s0 = state()
while time.time() - t0 < mx:
    time.sleep(15)
    if state() != s0:
        break
print('\n'.join(state()))
print('waited %d s' % (time.time() - t0))
