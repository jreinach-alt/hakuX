#!/usr/bin/env python3
"""Wait (foreground, bounded) until one of the named dispatch requests has a
DONE marker that was not there at the start, then print the state of all.

    waitdone.py [--max-s 560] <request id> [...]
"""
import os
import sys
import time

D = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch')
args = sys.argv[1:]
max_s = 560
if args and args[0] == '--max-s':
    max_s, args = int(args[1]), args[2:]


def done(rid):
    return os.path.exists(os.path.join(D, 'results', rid, 'DONE'))


def state(rid):
    if done(rid):
        return 'DONE'
    if os.path.exists(os.path.join(D, 'running', rid + '.req')):
        return 'RUNNING'
    if os.path.exists(os.path.join(D, 'queue', rid + '.req')):
        return 'QUEUED'
    return 'ELSEWHERE'


before = {r for r in args if done(r)}
t0 = time.time()
while time.time() - t0 < max_s:
    if any(done(r) and r not in before for r in args):
        break
    time.sleep(10)
hold = os.path.join(D, 'hold', 'nova')
print(time.strftime('%H:%M:%S'), 'nova hold:',
      open(hold).read().strip() if os.path.exists(hold) else '-')
for r in args:
    print(r, state(r))
