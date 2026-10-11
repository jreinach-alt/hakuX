#!/usr/bin/env python3
"""Which caller pays each title's synchronous surface-download wait? (lane.async794)

    sdcallers.py <results dir> <run id> [<run id> ...]

fps20786's sdsurvey.py ranks titles by surface-download finishes per flip.
This splits the wait by the caller that submitted it, from the [sdcall] lines
(vk/surface.c sdcall_log, perflog builds): per caller, finishes of its own
(fin), waits on an earlier submit (fence) or the flip's pre-download (pre),
per 60 guest frames, and the wall time of those waits per frame. It adds
hakuX-stall's download-if-dirty sources (dif[...], dlSrc dirtyIf) and the
texture bind's direct downloads (txr dl, a dirtyIf with no dif counter).
Medians over the run's lines; whole logcat, menus included.
"""
import os, re, statistics, sys

base = sys.argv[1]


def med(xs):
    return statistics.median(xs) if xs else 0.0


for rid in sys.argv[2:]:
    p = os.path.join(base, rid, 'logcat.txt')
    if not os.path.exists(p):
        print(rid, 'no logcat')
        continue
    calls = {}
    nsd = 0
    dirty, txdl, flips, difs = [], [], [], {}
    for line in open(p, errors='replace'):
        if '[sdcall]' in line:
            m = re.search(r'frames=(\d+)', line)
            fr = int(m.group(1)) if m else 60
            nsd += 1
            for name, fin, fence, pre, dl, ms in re.findall(
                    r' (\w+)=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms', line):
                c = calls.setdefault(name, {'fin': [], 'fence': [], 'pre': [], 'ms': []})
                c['fin'].append(int(fin) / fr)
                c['fence'].append(int(fence) / fr)
                c['pre'].append(int(pre) / fr)
                c['ms'].append(float(ms) / fr)
        elif 'RPBreaks' in line:
            m = re.search(r'flip(\d+)', line)
            fl = int(m.group(1)) if m else 0
            if fl:
                flips.append(fl)
                dirty.append(int(re.search(r'dirtyIf(\d+)', line).group(1)) / fl)
                d = re.search(r'dif\[([^\]]*)\]', line)
                if d:
                    for k, v in re.findall(r'([a-zA-Z]+)(\d+)', d.group(1)):
                        difs.setdefault(k, []).append(int(v) / fl)
        elif 'txr[' in line:
            m = re.search(r'txr\[ct\d+ bt\d+/\d+ dl(\d+)/', line)
            if m and flips:
                txdl.append(int(m.group(1)) / flips[-1])
    print('== %s  (%d sdcall lines)' % (rid, nsd))
    for name, c in sorted(calls.items(), key=lambda kv: -med(kv[1]['ms'])):
        # A caller absent from a line had no waits in it; pad with zeros.
        pad = nsd - len(c['ms'])
        ms = c['ms'] + [0.0] * pad
        print('   %-8s fin/fr %.2f fence/fr %.2f pre/fr %.2f  wait %.2f ms/frame'
              % (name, med(c['fin'] + [0.0] * pad), med(c['fence'] + [0.0] * pad),
                 med(c['pre'] + [0.0] * pad), med(ms)))
    print('   dirtyIf/flip %.2f  txr dl/flip %.2f  dif/flip %s' % (
        med(dirty), med(txdl),
        ' '.join('%s%.2f' % (k, med(v)) for k, v in difs.items() if med(v) > 0)))
