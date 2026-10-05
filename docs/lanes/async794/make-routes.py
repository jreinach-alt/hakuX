#!/usr/bin/env python3
"""lane.async794's two route fixes, from fps20786's routes. Run from the repo root.

Counter-Strike: B after the loop's A. Run 1-1791086565-lane.fps20786-3338415
played live rounds with the weapon wheel open over a near-static view; B closes
it (pathfind's steps 12-13) and the loop had none. A stays first, for the
"Press A to continue" card (run 2876984).

Top Spin: no START after step 24. In run 1-1791080537-lane.fps20786-2538884 that
START landed in play and paused the match; the loop's first A took "Resume
game" (frame 192900). The match loads to the serve by itself (step 25).
"""
import os

SRC = 'docs/lanes/fps20786/routes/'
DST = 'docs/lanes/async794/routes/'


def body_of(path):
    lines = open(path).read().split('\n')[1:]
    while lines and lines[0].startswith('#'):
        lines.pop(0)
    return '\n'.join(lines)


os.makedirs(DST, exist_ok=True)

cs = body_of(SRC + 'fps786-cs.route')
old = 'repeat 4 {\npress A 120\nwait 0.6\n'
assert cs.count(old) == 1
cs = cs.replace(old, old + 'press B 120\nwait 0.6\n')
open(DST + 'async794-cs.route', 'w').write(
    '# state: first-run\n'
    '# Counter-Strike (4D530036), lane.async794: fps20786\'s fps786-cs.route\n'
    '# with B after the loop\'s A, to close the weapon wheel (make-routes.py).\n'
    + cs)

ts = body_of(SRC + 'fps786-topspin.route')
mark = 'shot s24-loading\n'
i = ts.index(mark) + len(mark)
comment, after = ts[i:].split('\n', 1)
start = 'press START 120\nwait 0.6\n'
assert after.startswith(start), after[:60]
ts = (ts[:i] + comment + '\n# (async794: no START here; it paused the match)\n'
      'wait 0.6\n' + after[len(start):])
open(DST + 'async794-topspin.route', 'w').write(
    '# state: first-run\n'
    '# Top Spin (4D530035), lane.async794: fps20786\'s fps786-topspin.route\n'
    '# without the START after step 24, which paused the match (make-routes.py).\n'
    + ts)
print('wrote', DST + 'async794-cs.route', DST + 'async794-topspin.route')
