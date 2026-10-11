#!/usr/bin/env python3
"""Where threads ran and how they left the CPU, from `simpleperf dump`.

    cpusw.py <perf.data> <tid> [<tid> ...]

Switch records carry the CPU and misc: 0x2000 = switch-out, 0x4000 =
preempted (PERF_RECORD_MISC_SWITCH_OUT_PREEMPT: the thread was still
runnable). Per tid: on-CPU ms per CPU, and off-CPU ms split into voluntary
(it slept) and preempted (runnable, waiting for a CPU), with the preempted
intervals by length.
"""
import collections, glob, os, subprocess, sys

sp = sorted(glob.glob(os.path.expanduser('~/Android/Sdk/ndk/*')))[-1] + '/simpleperf/bin/linux/x86_64/simpleperf'
data, tids = sys.argv[1], set(sys.argv[2:])
p = subprocess.Popen([sp, 'dump', data], stdout=subprocess.PIPE, text=True, errors='replace')
ev = collections.defaultdict(list)    # tid -> [(time, out, preempt, cpu)]
cur = None
for line in p.stdout:
    if line.startswith('record '):
        if cur and cur.get('tid') in tids and 'time' in cur:
            ev[cur['tid']].append((cur['time'], cur['out'], cur['pre'], cur.get('cpu')))
        if line.startswith('record switch:'):
            misc = int(line.split('misc ')[1].split(',')[0], 16)
            cur = {'out': bool(misc & 0x2000), 'pre': bool(misc & 0x4000)}
        else:
            cur = None
        continue
    if cur is None:
        continue
    s = line.strip()
    if s.startswith('sample_id: pid'):
        cur['tid'] = s.split('tid ')[1].strip()
    elif s.startswith('sample_id: time'):
        cur['time'] = int(s.split()[-1])
    elif s.startswith('sample_id: cpu'):
        cur['cpu'] = int(s.split()[2].rstrip(','))
if cur and cur.get('tid') in tids and 'time' in cur:
    ev[cur['tid']].append((cur['time'], cur['out'], cur['pre'], cur.get('cpu')))

bins = [0.1, 1, 5, 10, 20, 1e9]
for tid in sys.argv[2:]:
    e = sorted(ev[tid])
    oncpu = collections.Counter()
    vol = pre = 0.0
    preb = collections.Counter()
    for a, b in zip(e, e[1:]):
        d = (b[0] - a[0]) / 1e6
        if not a[1] and b[1]:
            oncpu[a[3]] += d
        elif a[1] and not b[1]:
            if a[2]:
                pre += d
                preb[next(x for x in bins if d < x)] += d
            else:
                vol += d
    span = (e[-1][0] - e[0][0]) / 1e6 if e else 0
    tot = sum(oncpu.values())
    print(f'tid {tid}: span {span:.0f} ms, on {tot:.0f} ms, off voluntary {vol:.0f} ms, '
          f'off PREEMPTED {pre:.0f} ms')
    print('   on-CPU by cpu: ' + '  '.join(f'cpu{c}:{oncpu[c]:.0f}' for c in sorted(oncpu, key=lambda x: (x is None, x))))
    print('   preempted by length: ' + '  '.join(f'<{b}ms:{preb[b]:.0f}' for b in bins))
