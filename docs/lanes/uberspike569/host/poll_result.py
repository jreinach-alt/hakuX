#!/usr/bin/env python3
"""Wait (up to N seconds) for a dispatch request to reach results/ with a DONE file.

    poll_result.py <id> [max_seconds]

Prints where the request sits each minute (queue, running, results, with or
without a priority prefix) and the queue length ahead of it.
"""
import glob
import os
import sys
import time

d = os.environ.get('DISPATCH_DIR') or os.path.expanduser('~/hakux-work/dispatch')
rid = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else 540
t0 = time.time()
while True:
    hits = []
    for sub in ('queue', 'running', 'results'):
        hits += glob.glob(os.path.join(d, sub, rid + '*')) + glob.glob(os.path.join(d, sub, '*-' + rid + '*'))
    res = [h for h in hits if '/results/' in h and os.path.exists(os.path.join(h, 'DONE'))]
    q = sorted(os.listdir(os.path.join(d, 'queue')))
    print('%s +%4.0fs %s queue=%d' % (time.strftime('%H:%M:%S'), time.time() - t0,
                                      [os.path.relpath(h, d) for h in hits], len(q)), flush=True)
    if res:
        print('DONE', res[0])
        break
    if time.time() - t0 > limit:
        print('TIMEOUT')
        break
    time.sleep(60)
