"""Per hakuX-phase window: Surf/Tot beside the workload line (xemu-work), the render-pass
break split (hakuX-rpbrk), the pusher's method time (hakuX-cpu) and the surface-miss
counters (xemu-sfp).  Usage: work_table.py <logcat.txt>"""
import re
import sys

last = {}
print('%12s %5s %5s %5s %5s %5s %5s %6s %6s %5s %5s %6s' % (
    't', 'Surf', 'Tot', 'GPU', 'BE', 'SBnd', 'RP', 'rpSrf', 'rpAll', 'Mth', 'noRp', 'shC'))
for l in open(sys.argv[1], errors='replace'):
    t = l[6:18]
    if 'hakuX-phase' in l:
        last = {'t': t,
                'Surf': float(re.search(r'Surf:([\d.]+)', l).group(1)),
                'Tot': float(re.search(r'Tot:([\d.]+)', l).group(1)),
                'GPU': float(re.search(r'GPU:([\d.]+)', l).group(1))}
    elif 'hakuX-cpu' in l and last:
        m = re.search(r'Mth:([\d.]+)', l)
        last['Mth'] = float(m.group(1)) if m else -1
    elif 'xemu-work' in l and last:
        last['BE'] = int(re.search(r'BE:(\d+)', l).group(1))
        last['SBnd'] = int(re.search(r'SBnd:(\d+)', l).group(1))
        last['RP'] = int(re.search(r' RP:(\d+)', l).group(1))
    elif 'xemu-sfp' in l and last:
        last['noRp'] = int(re.search(r'noRp(\d+)', l).group(1))
        last['shC'] = int(re.search(r'shC(\d+)', l).group(1))
    elif 'hakuX-rpbrk' in l and last:
        last['rpSrf'] = int(re.search(r'srf(\d+)', l).group(1))
        last['rpAll'] = int(re.search(r'RP:(\d+)', l).group(1))
        print('%12s %5.1f %5.1f %5.1f %5s %5s %5s %6s %6s %5s %5s %6s' % tuple(
            last.get(k, '-') for k in ('t', 'Surf', 'Tot', 'GPU', 'BE', 'SBnd', 'RP',
                                       'rpSrf', 'rpAll', 'Mth', 'noRp', 'shC')))
        last = {}
