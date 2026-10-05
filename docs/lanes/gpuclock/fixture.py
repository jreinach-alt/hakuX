#!/usr/bin/env python3
"""A known-answer pair for gpuclock.py: GPU ms = C + K/MHz exactly (plus
noise), so the reader must return e near K/MHz's share and a fit of c ~ C,
k ~ K. Frame time = 1.6 gms + 2: the frame is GPU-paced, so b must say the
frame follows the GPU (dF = 1.6 dGPU).

    fixture.py <out dir>      writes <out>/lo and <out>/hi, and <out>/blocks:
                              one session switched 0 2 2 0 0 2 2 0 every 60 s
                              (capture_simpsons_gpuclock.sh's logcat shape),
                              with a `state=menu` stretch inside one pm=2 block
                              that the reader must drop
"""
import json, os, random, sys

C, K = 4.0, 6000.0
out = sys.argv[1]
random.seed(1)
for name, mhz in (('lo', 401), ('hi', 615)):
    d = os.path.join(out, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'run.log'), 'w').write('ROUTE 10:00:00.000 mark gameplay\n')
    json.dump(dict(regimen='default' if name == 'lo' else 'max', perf_mode=0 if name == 'lo' else 2, fan_mode=4),
              open(os.path.join(d, 'perf_regimen.json'), 'w'))
    json.dump(dict(device_label='thor', ref='fixture', env=[]), open(os.path.join(d, 'result.json'), 'w'))
    lines = ['10-05 09:59:59.000 I hakuX-perf: [gpuclk433] init period_us=100000 floor=401 ceil=680 gov=msm-adreno-tz err=none']
    t = 0.0
    for i in range(60):
        gms = C + K / mhz + random.gauss(0, 0.3)
        F = 1.6 * gms + 2
        t += 60 * F / 1000
        n = int(60 * F / 100)
        seq = ','.join('%d/%d' % (mhz, 95 if k % 3 == 0 else 70) for k in range(n))
        m = int(t // 60)
        lines.append('10-05 10:%02d:%06.3f I hakuX-perf: [gpuclk433] f=%d frames=60 fr=60 gms=%.2f grn=%.2f '
                     'floor=%d ceil=680 ns=%d dr=0 seq=%s' % (m, t - 60 * m, i * 60, gms, gms * .8,
                                                             mhz if name == 'hi' else 401, n, seq))
    open(os.path.join(d, 'logcat.txt'), 'w').write('\n'.join(lines) + '\n')
print('expect: lo gms %.2f hi gms %.2f, e %.2f, fit c %.1f k %.0f' % (
    C + K / 401, C + K / 615, __import__('math').log((C + K / 401) / (C + K / 615)) / __import__('math').log(615 / 401), C, K))

# blocks: one logcat, the clock switched by `gpuclock pm=` lines
d = os.path.join(out, 'blocks')
os.makedirs(d, exist_ok=True)
lines = ['10-05 09:59:58.000 I hakuX-route: mark gameplay',
         '10-05 09:59:59.000 I hakuX-perf: [gpuclk433] init period_us=100000 floor=401 ceil=680 gov=msm-adreno-tz err=none']
t, i = 0.0, 0


def stamp(t):
    m = int(t // 60)
    return '10-05 10:%02d:%06.3f' % (m, t - 60 * m)


for b, pm in enumerate([0, 2, 2, 0, 0, 2, 2, 0]):
    mhz = 615 if pm == 2 else 401
    lines.append('%s I hakuX-route: gpuclock pm=%d fan=4 floor=%d' % (stamp(t + 0.01), pm, mhz))
    end = t + 60
    if b == 5:
        lines.append('%s I hakuX-route: state=menu t=1' % stamp(t + 20))
        lines.append('%s I hakuX-route: state=play t=2' % stamp(t + 40))
    while t < end:
        gms = C + K / mhz + random.gauss(0, 0.3)
        F = 1.6 * gms + 2
        if b == 5 and 20 < (t - (end - 60)) < 40:
            gms = 1.0       # a menu: the reader must not see it
        t += 60 * F / 1000
        n = int(60 * F / 100)
        seq = ','.join('%d/%d' % (mhz, 80) for k in range(n))
        lines.append('%s I hakuX-perf: [gpuclk433] f=%d frames=60 fr=60 gms=%.2f grn=%.2f floor=%d ceil=680 ns=%d dr=0 seq=%s'
                     % (stamp(t), i * 60, gms, gms * .8, mhz, n, seq))
        i += 1
open(os.path.join(d, 'logcat.txt'), 'w').write('\n'.join(sorted(lines)) + '\n')
