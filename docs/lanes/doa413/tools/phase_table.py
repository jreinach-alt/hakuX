"""Tabulate a perflog soak: one row per hakuX-phase line (60 flips), with the gfps line
before it and the hakuX-stall counters before it.  Usage: phase_table.py <logcat.txt>"""
import re
import sys

L = open(sys.argv[1], errors='replace').read().splitlines()


def num(k, s):
    m = re.search(r'\b' + k + r':(-?[\d.]+)', s)
    return float(m.group(1)) if m else None


rows = []
stall = {}
cur = {}
for l in L:
    t = l[6:18]
    if 'hakuX-stall' in l and 'Finish:' in l:
        stall = {'fin': int(re.search(r'Finish:(\d+)', l).group(1)),
                 'sd': int(re.search(r'\(vtx\d+ sc\d+ sd(\d+)', l).group(1)),
                 'rpb': int(re.search(r'RPBreaks:(\d+)', l).group(1))}
        m = re.search(r'sd\[ev(\d+) noCb(\d+) dl(\d+)', l)
        stall.update(ev=int(m.group(1)), sddl=int(m.group(3)))
    elif 'hakuX-stall' in l and 'evict[' in l:
        m = re.search(r'evict\[dl:(\d+) unshelve:(\d+)', l)
        stall.update(evdl=int(m.group(1)), unsh=int(m.group(2)))
    elif 'gfps=' in l:
        g = re.search(r'gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\)', l)
        cur = {'t': t, 'gfps': int(g.group(1)), 'G': float(g.group(2)),
               'Gmax': float(g.group(4)), 'Ri': num('Ri', l)}
    elif 'hakuX-phase' in l:
        r = dict(cur)
        r.update(stall)
        for k in ('Surf', 'Draw', 'Pipe', 'Fin', 'Sub', 'Fen', 'Idle', 'Tot', 'GPU'):
            r[k] = num(k, l)
        rows.append(r)

cols = ['t', 'gfps', 'G', 'Gmax', 'Ri', 'Tot', 'Surf', 'Draw', 'Pipe', 'Fin', 'Sub', 'Fen',
        'Idle', 'GPU', 'fin', 'sd', 'ev', 'sddl', 'evdl', 'unsh', 'rpb']
print(' '.join('%7s' % c for c in cols))
for r in rows:
    out = []
    for c in cols:
        v = r.get(c)
        out.append('%7s' % ('%.1f' % v if isinstance(v, float) else v))
    print(' '.join(out))
