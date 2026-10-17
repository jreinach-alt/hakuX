#!/usr/bin/env python3
"""Mock A and C legs for speechread.py: a parser check, not a reading."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LANE = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'mock')
EXPECT = os.path.join(OUT, 'expect.json')

legs = {
    'A': ('', 0.0, 12),
    'C': ('cap', 4.0, 12),
}
os.makedirs(OUT, exist_ok=True)
json.dump({'expect': {'V_min_cine_shots': 2, 'V_min_speech_windows': 2, 'B_sm_min_db': 0.0,
                      'L_l1_max': 1.0, 'N_bed_drop_db': 3.0, 'N_sr_gain_db': 3.0,
                      'S_sslempty_min': 1, 'S_pause_slow_min': 1}}, open(EXPECT, 'w'))
args = []
for tag, (norm, drop, clipped) in legs.items():
    d = os.path.join(OUT, tag)
    os.makedirs(os.path.join(d, 'route-frames'), exist_ok=True)
    for s in ('230010-cine.png', '230020-cine.png'):
        open(os.path.join(d, 'route-frames', s), 'w').close()
    L = ['10-16 23:00:00.000 I/hakuX-audio( 1): apu_meter: on',
         '10-16 23:00:00.000 I/hakuX-audio( 1): hrtf_norm: %s' % (norm or 'l1 (default)'),
         '10-16 23:00:00.500 I/hakuX-route( 1): mark cinematic',
         '10-16 23:00:01.000 I/hakuX-audio( 1): apuhrtf v=4 h=12 l1=0.600/0.500 l2=0.300/0.250 dc=0.500/0.300 itd=3.00',
         '10-16 23:00:02.000 I/hakuX-pace( 1): f=60 v0 vb=1 max=34.1 ms=2000.0',
         '10-16 23:00:05.000 I/hakuX-audio( 1): apumeter w=0 3d=%.1f 2d=-29.0 top=65:-30.0,4:-33.0,85:-35.7 pause=-' % (-32.0 - drop),
         '10-16 23:00:06.000 I/hakuX-pace( 1): f=120 v0 vb=1 max=90.1 ms=4000.0',
         '10-16 23:00:10.000 I/hakuX-audio( 1): apumeter w=1 3d=%.1f 2d=-28.8 top=65:-29.8,4:-30.0,85:-35.7,86:-38.5 pause=65:2' % (-29.0 - drop),
         '10-16 23:00:11.000 I/hakuX-audio( 1): apuvoice sslempty v=65 ssl=A ssl_wr_age=1 f=2 t=3',
         '10-16 23:00:12.000 I/hakuX-pace( 1): f=180 v0 vb=1 max=34.1 ms=2000.0',
         '10-16 23:00:15.000 I/hakuX-audio( 1): apumeter w=2 3d=-17.9 2d=-30.2 top=15:-18.3,85:-31.1 pause=-',
         '10-16 23:00:16.000 I/hakuX-audio( 1): level L: 16.000 s  peak 30000 (-0.8 dBFS)  acrms -25.00 dBFS  dc 0.000 %%FS  p5/25/50/75/95 1/2/3/4/5  windows 9 counted 9 flat  clipped %d  zeros 0  wrap 0  maxjump 9' % clipped,
         '10-16 23:00:16.000 I/hakuX-audio( 1): level R: 16.000 s  peak 30000 (-0.8 dBFS)  acrms -25.00 dBFS  dc 0.000 %%FS  p5/25/50/75/95 1/2/3/4/5  windows 9 counted 9 flat  clipped %d  zeros 0  wrap 0  maxjump 9' % clipped]
    open(os.path.join(d, 'logcat.txt'), 'w').write('\n'.join(L) + '\n')
    args.append('%s=%s' % (tag, d))
sys.exit(subprocess.call([sys.executable, os.path.join(LANE, 'speechread.py'), '--expect', EXPECT] + args))
