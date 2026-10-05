#!/usr/bin/env python3
"""The CPU side of the performance_mode knob, per run: the share of the soak's
`hold` thermal samples (30 s apart, thermal.jsonl) at which each CPU policy's
first core read its maximum, and the clocks it read.

    cpu7share.py RUN [RUN ...]

performance_mode raises the CPU floors along with the GPU floor (NOTES 1). The
vCPU's core is in policy7; if the default arm's cpu7 reads under its maximum
while the max arm's reads it, the pair moved the vCPU's clock too and the fps
difference is not the GPU's alone.
"""
import collections, json, os, sys

R = '/home/justin/hakux-work/dispatch/results/'
for i in sys.argv[1:]:
    d = i if os.path.isdir(i) else R + i
    try:
        regimen = json.load(open(d + '/perf_regimen.json')).get('regimen')
    except Exception:
        regimen = '?'
    per = collections.defaultdict(list)
    for l in open(d + '/thermal.jsonl'):
        s = json.loads(l)
        if s.get('label') != 'hold':
            continue
        for cpu, v in (s.get('clk') or {}).items():
            if cpu.startswith('cpu') and v.get('scaling_cur_freq'):
                per[cpu].append((v['scaling_cur_freq'] // 1000, v.get('cpuinfo_max_freq', 0) // 1000))
    cells = []
    for cpu in sorted(per):
        xs = per[cpu]
        top = sum(1 for c, m in xs if c >= m)
        cells.append('%s at max %d/%d (%s)' % (cpu, top, len(xs), ','.join(str(c) for c, _ in xs)))
    print('%s %-8s %s' % (os.path.basename(d), regimen, ' | '.join(cells)))
