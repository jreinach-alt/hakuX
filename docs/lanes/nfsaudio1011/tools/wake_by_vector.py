#!/usr/bin/env python3
"""What wakes the idle guest, by interrupt source, from a soak's [rr425w] lines.

    wake_by_vector.py <result id>...

For each run, per 10 s bin: the guest's idle share, and for each vector the
wakes from idle (n) and the interrupts taken while busy (nb), per second.
Vectors are 0x30 + IRQ (the Xbox kernel's HalGetInterruptVector): 0x30 PIT,
0x33 NV2A, 0x35 APU, 0x36 ACI, 0x3e IDE. Then the whole-run totals by vector.

The question it answers for nfsaudio1011: does the APU's interrupt (0x35)
pace the guest at all? If the game's audio writer were woken by APU
notifications, 0x35 would carry wakes in the idle windows.
"""
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
KV = re.compile(r'(\w+)=(-?\d+)')
WK = re.compile(r' ([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):(\d+)'
                r':(\d+)/(\d+)/(\d+)/(\d+):(\d+)/(\d+)/(\d+)/(\d+):(\d+)')
NAME = {0x30: 'PIT', 0x31: 'USB0', 0x33: 'NV2A', 0x34: 'NIC', 0x35: 'APU',
        0x36: 'ACI', 0x39: 'USB1', 0x3b: 'SMBus', 0x3e: 'IDE', 0x3f: 'IDE2',
        0xff: 'non-PIC'}


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f').timestamp()


for rid in sys.argv[1:]:
    path = rid if os.path.isfile(rid) else R + rid + '/logcat.txt'
    lines = open(path, errors='replace').read().splitlines()
    t0 = None
    bins = defaultdict(lambda: [0, 0, Counter(), Counter(), 0])
    tot_n, tot_nb = Counter(), Counter()
    for ln in lines:
        if t0 is None and re.match(r'\d\d-\d\d ', ln):
            t0 = ts(ln)
        if '[rr425w]' not in ln:
            continue
        body = ln.split('[rr425w]', 1)[1]
        head = dict((k, int(v)) for k, v in KV.findall(body.split(' 3')[0]))
        b = int((ts(ln) - t0) // 10) * 10
        acc = bins[b]
        acc[0] += head.get('idle_us', 0)
        acc[1] += head.get('busy_us', 0)
        acc[4] += 1
        for m in WK.finditer(body):
            vec = int(m.group(1), 16)
            n, nb = int(m.group(3)), int(m.group(14))
            acc[2][vec] += n
            acc[3][vec] += nb
            tot_n[vec] += n
            tot_nb[vec] += nb
    print('==', rid)
    vecs = sorted(set(tot_n) | set(tot_nb))
    print('   bin    idle%  ' + '  '.join('%-13s' % ('%02x %s' % (v, NAME.get(v, '?')))
                                        for v in vecs) + '   (n/s from idle, nb/s busy)')
    for b in sorted(bins):
        idle, busy, n, nb, k = bins[b]
        secs = (idle + busy) / 1e6 or 1
        print('   %3d s  %5.1f  ' % (b, 100.0 * idle / max(idle + busy, 1)) +
              '  '.join('%5.0f/%-7.0f' % (n[v] / secs, nb[v] / secs) for v in vecs))
    print('   total wakes from idle: ' + ', '.join('%02x %s %d' % (v, NAME.get(v, '?'), tot_n[v]) for v in vecs))
    print('   total taken busy:      ' + ', '.join('%02x %s %d' % (v, NAME.get(v, '?'), tot_nb[v]) for v in vecs))
