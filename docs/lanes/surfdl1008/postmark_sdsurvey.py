#!/usr/bin/env python3
"""Post-mark sd/flip, dirtyIf, cDef, and sdcall-caller medians (lane.surfdl1008).

    postmark_sdsurvey.py <results dir> <run id>

fps20786/sdsurvey.py's RPBreaks regex and async794/sdcallers.py's [sdcall]
caller split, both applied as written, but restricted to logcat lines at or
after the "mark gameplay" hakuX-route line -- those scripts read the whole
logcat (menus included) by their own documented caveat, which this brief's
mark-based reads elsewhere (decompose.py, extras.py) do not do. Same
regexes, same per-flip/per-frame method, mark-restricted.
"""
import os
import re
import statistics
import sys

TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def med(xs):
    return statistics.median(xs) if xs else 0.0


base, rid = sys.argv[1], sys.argv[2]
p = os.path.join(base, rid, 'logcat.txt')
mark = None
sd, dirty, cdef = [], [], []
calls = {}
nsd = 0
with open(p, errors='replace') as f:
    for line in f:
        if 'hakuX-route' in line and 'mark gameplay' in line:
            m = TS.match(line)
            if m:
                mark = secs(*m.groups())
        if mark is None:
            continue
        m = TS.match(line)
        if not m or secs(*m.groups()) < mark:
            continue
        if 'RPBreaks' in line:
            mm = re.search(r'sd(\d+) buf\d+ fb\d+ pres\d+ flip(\d+)', line)
            if mm and int(mm.group(2)) > 0:
                fl = int(mm.group(2))
                sd.append(int(mm.group(1)) / fl)
                dirty.append(int(re.search(r'dirtyIf(\d+)', line).group(1)) / fl)
                cdef.append(int(re.search(r'cDef(\d+)', line).group(1)) / fl)
        elif '[sdcall]' in line:
            mm = re.search(r'frames=(\d+)', line)
            fr = int(mm.group(1)) if mm else 60
            nsd += 1
            for name, fin, fence, pre, dl, ms in re.findall(
                    r' (\w+)=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms', line):
                c = calls.setdefault(name, {'fin': [], 'ms': []})
                c['fin'].append(int(fin) / fr)
                c['ms'].append(float(ms) / fr)

print('== %s  mark at %s s; RPBreaks rows post-mark %d, sdcall lines post-mark %d'
      % (rid, mark, len(sd), nsd))
print('sd/flip median %.2f  dirtyIf/flip median %.2f  cDef/flip median %.2f' % (
    med(sd), med(dirty), med(cdef)))
for name, c in sorted(calls.items(), key=lambda kv: -med(kv[1]['ms'])):
    pad = nsd - len(c['ms'])
    ms = c['ms'] + [0.0] * pad
    fin = c['fin'] + [0.0] * pad
    print('   %-8s fin/fr %.2f  wait %.2f ms/frame' % (name, med(fin), med(ms)))
