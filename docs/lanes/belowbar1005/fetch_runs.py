#!/usr/bin/env python3
"""Copy a set of pathfind run directories' text artifacts into scratch/ for
offline reading (the run dirs live in another lane's worktree)."""
import os
import shutil
import sys

SRC = '/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs'
FILES = ['logcat.txt', 'run.log', 'request.json', 'screen-logcat.txt',
         'verdict.json', 'result.json', 'heldrun.log', 'hdd.json']

for run in sys.argv[1:]:
    dst = os.path.join('scratch', run)
    os.makedirs(dst, exist_ok=True)
    got = []
    for f in FILES:
        p = os.path.join(SRC, run, f)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(dst, f))
            got.append('%s=%d' % (f, os.path.getsize(p)))
    print(run, ' '.join(got))
