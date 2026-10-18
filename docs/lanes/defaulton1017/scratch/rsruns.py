#!/usr/bin/env python3
"""Every result dir of a RalliSport route (route_name starting rallisport-804): ref, env, device, time,
how many d-shots it kept. Answers: which master run of rallisport-804g is RS's comparison?"""
import glob
import json
import os
import time

R = '/home/justin/hakux-work/dispatch/results'
for d in sorted(glob.glob(R + '/*'), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0):
    try:
        req = json.load(open(d + '/request.json'))
    except Exception:
        continue
    rn = str(req.get('route_name'))
    if not rn.startswith('rallisport-804'):
        continue
    rf = glob.glob(d + '/route-frames/*-d*.png')
    print('%s %s ref %s env [%s] %s d-shots %d' % (
        os.path.basename(d), rn, req.get('ref'), ' '.join(req.get('env') or []),
        time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(d))), len(rf)))
