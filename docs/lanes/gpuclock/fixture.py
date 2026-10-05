#!/usr/bin/env python3
"""A known-answer pair for gpuclock.py: GPU ms = C + K/MHz exactly (plus
noise), so the reader must return e near K/MHz's share and a fit of c ~ C,
k ~ K. Frame time = 1.6 gms + 2: the frame is GPU-paced, so b must say the
frame follows the GPU (dF = 1.6 dGPU).

    fixture.py <out dir>      writes <out>/lo and <out>/hi
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
