#!/usr/bin/env python3
"""List every pgraph_vk_finish(VK_FINISH_REASON_SURFACE_DOWN*) call in the vk
renderer with its enclosing function and the OPT_STAT counter (if any) that
fires on the same path within 3 lines above it.

Usage: python3 docs/lanes/blinx372b/sites.py   (from the repo root)
"""
import glob
import re

FN = re.compile(r'^[A-Za-z_][\w\s\*]*?\b(\w+)\s*\(')
for path in sorted(glob.glob('hw/xbox/nv2a/pgraph/vk/*.c')):
    lines = open(path, errors='replace').read().split('\n')
    fn = '?'
    for i, ln in enumerate(lines):
        m = FN.match(ln)
        if m and not ln.rstrip().endswith(';'):
            fn = m.group(1)
        if 'pgraph_vk_finish(' in ln and 'SURFACE_DOWN' in ln:
            ctx = ' '.join(lines[max(0, i - 3):i])
            stat = re.findall(r'OPT_STAT_INC\((\w+)\)', ctx)
            print('%s:%d  %-45s  %s' % (path.split('/')[-1], i + 1, fn,
                                        ','.join(stat) or '(no counter)'))
