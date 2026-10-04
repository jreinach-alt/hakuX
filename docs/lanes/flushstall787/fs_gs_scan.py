#!/usr/bin/env python3
"""Which titles pay for unchained two-page TBs, across every soak on disk.

[rr425] gs counts dispatches into a TB that spans two guest pages, which QEMU
never chains into, so each costs a trip through the dispatch loop. Kabuki's
w=92 made 3.78M of them for a loop gap of 372 ms against a 19 ms median:
~95 ns each (NOTES.md 5.1). This reads every results dir whose logcat has
[rr425] lines and prints, per title: runs, windows, the windows with
gs >= --hot (default 1M, ~95 ms of a 2-s window), the largest gs, and the
estimated loop time those dispatches cost per run (gs x --ns).

usage: fs_gs_scan.py [--results DIR] [--hot 1000000] [--ns 95]
"""
import collections
import json
import os
import re
import sys

args = sys.argv[1:]
res = '/home/justin/hakux-work/dispatch/results'
hot, ns = 1000000, 95.0
if '--results' in args:
    i = args.index('--results'); res = args[i + 1]; del args[i:i + 2]
if '--hot' in args:
    i = args.index('--hot'); hot = int(args[i + 1]); del args[i:i + 2]
if '--ns' in args:
    i = args.index('--ns'); ns = float(args[i + 1]); del args[i:i + 2]

PAT = re.compile(rb'\[rr425\] w=(\d+) .* gs=(\d+) ')
by = collections.defaultdict(list)
for rid in sorted(os.listdir(res)):
    lc = os.path.join(res, rid, 'logcat.txt')
    if not os.path.exists(lc):
        continue
    gs = {}
    with open(lc, 'rb') as f:
        for line in f:
            if b'[rr425] w=' not in line:
                continue
            m = PAT.search(line)
            if m:
                gs[int(m.group(1))] = int(m.group(2))
    if not gs:
        continue
    try:
        req = json.load(open(os.path.join(res, rid, 'request.json')))
    except (OSError, ValueError):
        req = {}
    title = req.get('title') or req.get('suites') or '?'
    if isinstance(title, list):
        title = ','.join(title)
    v = list(gs.values())
    by[title].append((rid, len(v), sum(1 for x in v if x >= hot), max(v),
                      sum(x for x in v if x >= hot) * ns / 1e6))

print('%-48s %4s %6s %5s %10s %9s' % ('title', 'runs', 'wins', 'hot',
                                      'max_gs', 'hot_ms/run'))
rows = []
for t, rs in by.items():
    rows.append((sum(r[4] for r in rs) / len(rs), t, rs))
for ms, t, rs in sorted(rows, reverse=True):
    print('%-48s %4d %6d %5d %10d %9.0f' % (
        t[:48], len(rs), sum(r[1] for r in rs), sum(r[2] for r in rs),
        max(r[3] for r in rs), ms))
