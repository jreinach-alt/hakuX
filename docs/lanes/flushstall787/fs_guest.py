#!/usr/bin/env python3
"""Where the guest's time goes in a set of [rr425] windows, from [tpc787].

[tpc787] samples 1 in 64 dispatches and charges each its run time against
its entry pc. Scaling the sampled us by the window's [rr425] tbus / sampled
us gives an estimate of the real TB time per entry pc. Prints, per window:
tbus, the share in --spin (the title's wait loop), the scaled time outside
it, the kernel idle loop's time (8001b02e/f/30), [rr425w] idle_us, and the
top non-spin pcs.

usage: fs_guest.py <result_dir> <w>[-<w>] ... [--spin 000a8330] [--top 6]
"""
import re
import sys

args = sys.argv[1:]
spin = '000a8330'
top = 6
if '--spin' in args:
    i = args.index('--spin'); spin = args[i + 1]; del args[i:i + 2]
if '--top' in args:
    i = args.index('--top'); top = int(args[i + 1]); del args[i:i + 2]
d, specs = args[0], args[1:]
ws = []
for s in specs:
    a, _, b = s.partition('-')
    ws += list(range(int(a), int(b or a) + 1))

rr, tpc, idle = {}, {}, {}
for line in open(d + '/logcat.txt', errors='replace'):
    m = re.search(r'\[(rr425|tpc787|rr425w)\] w=(\d+) ', line)
    if not m:
        continue
    w = int(m.group(2))
    if m.group(1) == 'rr425':
        rr[w] = int(re.search(r' tbus=(\d+)', line).group(1))
    elif m.group(1) == 'rr425w':
        idle[w] = int(re.search(r' idle_us=(\d+)', line).group(1))
    else:
        tpc[w] = [(p, int(us)) for p, _, us, _ in
                  re.findall(r' ([0-9a-f]{8}):(\w+):(\d+):(\d+)', line)]
        tpc[w].append(('_sum', int(re.search(r' us=(\d+)', line).group(1))))

IDLE = ('8001b02e', '8001b02f', '8001b030')
print('w     tbus_ms spin%  nonspin_ms  kidle_ms  idle_us_ms  top non-spin (scaled ms)')
for w in ws:
    if w not in rr or w not in tpc:
        continue
    ent = dict(tpc[w])
    tot = ent.pop('_sum') or 1
    k = rr[w] / tot
    sp = ent.get(spin, 0)
    ki = sum(ent.get(p, 0) for p in IDLE)
    rest = sorted(((us, p) for p, us in ent.items()
                   if p != spin and p not in IDLE), reverse=True)[:top]
    print('%-5d %7.0f %5.0f %10.0f %9.0f %11.0f  %s' % (
        w, rr[w] / 1e3, 100.0 * sp / tot, (tot - sp - ki) * k / 1e3,
        ki * k / 1e3, idle.get(w, 0) / 1e3,
        ' '.join('%s:%.0f' % (p, us * k / 1e3) for us, p in rest)))
