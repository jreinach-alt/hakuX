#!/usr/bin/env python3
"""Every Top Spin run of route fps1015-topspin on disk: ref, apk, env, and whether the route got past controller
select (shot s14 differs from s13, i.e. the A press at s13 took) and reached a match (an [s2tcvt] line or
tsread's play signature). Answers: did the A at controller select ever drop on a build without this lane's
switches?"""
import glob
import json
import os
import sys

from PIL import Image

R = '/home/justin/hakux-work/dispatch/results'


def small(p):
    return list(Image.open(p).convert('L').resize((64, 48)).getdata())


def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


ref13 = None
for d in sorted(glob.glob(R + '/*'), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0):
    try:
        req = json.load(open(d + '/request.json'))
    except Exception:
        continue
    if 'Top_Spin' not in str(req.get('title')) or 'topspin' not in str(req.get('route_name')):
        continue
    try:
        res = json.load(open(d + '/result.json'))
    except Exception:
        res = {}
    sh = {}
    for f in sorted(glob.glob(d + '/route-frames/*.png')):
        lab = os.path.basename(f).split('-', 1)[1].rsplit('.', 1)[0]
        sh.setdefault(lab, f)
    s13, s14 = sh.get('s13-submenu'), sh.get('s14-submenu')
    took = '-'
    if s13 and s14:
        took = '%.1f' % mad(small(s13), small(s14))
    lc = open(d + '/logcat.txt', errors='replace').read() if os.path.exists(d + '/logcat.txt') else ''
    print('%s %s ref %s apk %s env [%s] s13->s14 %s s2t %s fldcw-chain %s rearly %s' % (
        os.path.basename(d), req.get('route_name'), req.get('ref'), res.get('apk_sha'), req.get('env'), took,
        lc.count('[s2tcvt] on'), '[fldcw1018] chain=1' in lc, '[rearly1018] early=1' in lc))
