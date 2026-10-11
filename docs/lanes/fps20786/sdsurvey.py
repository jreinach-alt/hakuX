#!/usr/bin/env python3
"""How common are synchronous surface-download finishes? (lane.fps20786)

    sdsurvey.py <dispatch results dir> [--days 10]

For every perflog soak in the results dir (request.json "perflog" true, a
title, a logcat with hakuX-stall lines), the medians over the run's
hakuX-stall lines of: surface-download finishes per flip (sd/flip), where
the download came from (dirtyIf, completion-deferred), and from
hakuX-phase the finish wait (Fin) and GPU ms per frame, plus the guest
frame rate (gfps). One row per run, sorted by title. The whole logcat
is read (menus included), so this ranks titles; it does not judge one.
"""
import argparse, json, os, re, statistics, time

ap = argparse.ArgumentParser()
ap.add_argument('results')
ap.add_argument('--days', type=float, default=10)
a = ap.parse_args()


def med(xs):
    return statistics.median(xs) if xs else float('nan')


rows = []
for d in os.listdir(a.results):
    p = os.path.join(a.results, d)
    try:
        if os.path.getmtime(p) < time.time() - a.days * 86400:
            continue
        rq = json.load(open(os.path.join(p, 'request.json')))
    except Exception:
        continue
    if str(rq.get('perflog')).lower() != 'true' or not rq.get('title'):
        continue
    lc = os.path.join(p, 'logcat.txt')
    if not os.path.exists(lc):
        continue
    sd, dirty, cdef, fin, gpu, gfps = [], [], [], [], [], []
    for line in open(lc, errors='replace'):
        if 'RPBreaks' in line:
            m = re.search(r'sd(\d+) buf\d+ fb\d+ pres\d+ flip(\d+)', line)
            if m and int(m.group(2)) > 0:
                fl = int(m.group(2))
                sd.append(int(m.group(1)) / fl)
                dirty.append(int(re.search(r'dirtyIf(\d+)', line).group(1)) / fl)
                cdef.append(int(re.search(r'cDef(\d+)', line).group(1)) / fl)
        elif 'hakuX-phase' in line:
            m = re.search(r'Fin:([\d.]+)', line)
            g = re.search(r'GPU:([\d.]+)', line)
            if m:
                fin.append(float(m.group(1)))
            if g:
                gpu.append(float(g.group(1)))
        elif 'gfps=' in line:
            gfps.append(int(re.search(r'gfps=(\d+)', line).group(1)))
    if sd:
        rows.append((rq['title'][:40], d, med(sd), med(dirty), med(cdef), med(fin), med(gpu), med(gfps)))
print('%-40s %-44s %6s %6s %6s %6s %6s %5s' % ('title', 'run', 'sd/fl', 'dirty', 'cDef', 'Fin', 'GPU', 'gfps'))
for r in sorted(rows):
    print('%-40s %-44s %6.2f %6.2f %6.2f %6.1f %6.1f %5.0f' % r)
