#!/usr/bin/env python3
"""Print one line per event: the local gradle build ending, and each of this
lane's dispatch requests starting and finishing. Exits when all have ended.

usage: watch.py <gradle output file> <request id>...
"""
import os
import re
import sys
import time

R = '/home/justin/hakux-work/dispatch'
build, ids = sys.argv[1], sys.argv[2:]
seen = set()
while True:
    if 'build' not in seen and os.path.exists(build):
        txt = open(build, errors='replace').read()
        if re.search(r'GRADLE_EXIT=|BUILD FAILED|BUILD SUCCESSFUL', txt):
            lines = [l for l in txt.splitlines()
                     if re.search(r'GRADLE_EXIT=|BUILD FAILED|BUILD SUCCESS'
                                  r'|error:', l) and 'adrenotools' not in l]
            print('BUILD', ' | '.join(lines[-5:]), flush=True)
            seen.add('build')
    for i in ids:
        if i + 'run' not in seen and os.path.exists('%s/running/%s.req' % (R, i)):
            print('RUNNING', i, flush=True)
            seen.add(i + 'run')
        if i + 'done' not in seen and os.path.exists('%s/results/%s/DONE' % (R, i)):
            print('DONE', i, flush=True)
            seen.add(i + 'done')
        if i + 'done' not in seen and os.path.exists('%s/queue/withdrawn/%s.req' % (R, i)):
            print('WITHDRAWN', i, flush=True)
            seen.add(i + 'done')
    if 'build' in seen and all(i + 'done' in seen for i in ids):
        sys.exit(0)
    time.sleep(20)
