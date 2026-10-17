#!/usr/bin/env python3
"""Every result dir on disk with Texture_shadow_comparator captures: apk, ref, env, device, time; then, for
each apk with two or more such runs, how many of the 288 captures differ in bytes between each pair.
Answers: is A against A movement in the broken suite seen without the RalliSport push that overlapped TSC1?"""
import glob
import hashlib
import itertools
import json
import os

R = '/home/justin/hakux-work/dispatch/results'
runs = []
for d in sorted(glob.glob(R + '/*')):
    caps = glob.glob(d + '/captures*/Texture_shadow_comparator::*.png')
    if not caps:
        continue
    try:
        res = json.load(open(d + '/result.json'))
        req = json.load(open(d + '/request.json'))
    except Exception:
        continue
    h = {}
    for c in caps:
        k = os.path.basename(c).split('::', 1)[1]
        h.setdefault(k, hashlib.sha256(open(c, 'rb').read()).hexdigest())
    runs.append(dict(name=os.path.basename(d), apk=res.get('apk_sha'), ref=res.get('ref'),
                     env=' '.join(req.get('env') or []), dev=res.get('device_label'),
                     t=os.path.getmtime(d + '/DONE') if os.path.exists(d + '/DONE') else 0, h=h))
print('%d result dirs with the suite\'s captures' % len(runs))
by = {}
for r in runs:
    by.setdefault(r['apk'], []).append(r)
for apk, rs in by.items():
    print('\napk %s, %d runs' % (apk, len(rs)))
    for r in rs:
        print('  %s ref %s dev %s caps %d env [%s]' % (r['name'], r['ref'], r['dev'], len(r['h']), r['env']))
    for a, b in itertools.combinations(rs, 2):
        keys = set(a['h']) & set(b['h'])
        moved = sum(1 for k in keys if a['h'][k] != b['h'][k])
        print('    %s vs %s: %d of %d moved' % (a['name'][-22:], b['name'][-22:], moved, len(keys)))
