#!/usr/bin/env python3
"""Per-line price bound for Blinx's demo eviction waits (lane.blinx372c, #372).

For every hakuX-stall RPBreaks line whose cDef count equals its evict[dl]
count and is non-zero (the demo stretch), pair it with the next hakuX-phase
and gfps lines and print:

  Tot   ms of renderer time per guest frame (phase line)
  Sub   ms in pgraph_vk_finish's submit phase. For a non-deferred finish
        that includes qemu_event_wait on the render thread, i.e. the
        GPU-completion wait. The demo's other finishes are deferred
        (stl == stlDef), so Sub bounds the eviction waits from ABOVE.
  GPU   ms of GPU time per frame (timestamp queries)
  floor max(Tot - Sub, GPU): no hunk that only removes the waits can make a
        frame shorter than the CPU work left or the GPU work that remains.
  cap   1000 / floor, an fps CEILING, not a prediction.

Usage: demobound.py <logcat.txt>
"""
import re
import statistics
import sys

STALL = re.compile(r'hakuX-stall.*RPBreaks:.*sd\[ev\d+ noCb\d+ dl\d+ cDef(\d+)')
EVICT = re.compile(r'hakuX-stall.*evict\[dl:(\d+) unshelve:(\d+) stale:(\d+)')
PHASE = re.compile(r'hakuX-phase.*Fin:([\d.]+)\(Sub:([\d.]+) Fen:([\d.]+)\).*'
                   r'Tot:([\d.]+) GPU:([\d.]+)')
GFPS = re.compile(r'hakuX-perf.*gfps=(\d+)')


def rows(lines):
    cur = None
    for l in lines:
        m = STALL.search(l)
        if m:
            cur = {'t': l[6:18], 'cdef': int(m.group(1))}
            continue
        if cur is None:
            continue
        m = EVICT.search(l)
        if m:
            cur['evdl'], cur['unshelve'], cur['stale'] = map(int, m.groups())
            continue
        m = GFPS.search(l)
        if m and 'gfps' not in cur:
            cur['gfps'] = int(m.group(1))
            continue
        m = PHASE.search(l)
        if m:
            fin, sub, fen, tot, gpu = map(float, m.groups())
            cur.update(fin=fin, sub=sub, fen=fen, tot=tot, gpu=gpu)
            if cur['cdef'] and cur.get('evdl') == cur['cdef']:
                yield cur
            cur = None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rs = list(rows(open(sys.argv[1], errors='replace').read().splitlines()))
    if not rs:
        sys.exit('no demo lines (cDef == evict dl > 0)')
    print('time          cDef evdl stale gfps   Tot   Sub  Fen   GPU  floor  cap')
    for r in rs:
        r['floor'] = max(r['tot'] - r['sub'], r['gpu'])
        r['cap'] = 1000.0 / r['floor']
        print('%s %4d %4d %5d %4s %5.1f %5.1f %4.1f %5.1f %6.1f %4.1f' % (
            r['t'], r['cdef'], r['evdl'], r['stale'], r.get('gfps', '-'),
            r['tot'], r['sub'], r['fen'], r['gpu'], r['floor'], r['cap']))
    med = lambda k: statistics.median(r[k] for r in rs)
    print('median over %d lines: Tot %.1f Sub %.1f Fen %.1f GPU %.1f '
          'floor %.1f cap %.1f fps; now %.1f fps (1000/Tot)' % (
              len(rs), med('tot'), med('sub'), med('fen'), med('gpu'),
              med('floor'), med('cap'), 1000.0 / med('tot')))


if __name__ == '__main__':
    main()
