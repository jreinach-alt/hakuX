#!/usr/bin/env python3
"""Summarise dispatch runs: request, verdict, and which perf tags the logcat carries."""
import glob, json, os, re, sys, collections

R = '/home/justin/hakux-work/dispatch/results'
pats = sys.argv[1:] or ['0-*tronhang672*', '1790970734-lanelocal-1022425', '1790981973-lanelocal-3657361']
for p in pats:
    for d in sorted(glob.glob(os.path.join(R, p))):
        print('==', os.path.basename(d))
        try:
            r = json.load(open(d + '/request.json'))
            print(' req', {k: r.get(k) for k in ('title', 'ref', 'seconds', 'device', 'route', 'env', 'who', 'mode', 'args')})
        except Exception as e:
            print(' req err', e)
        try:
            v = json.load(open(d + '/verdict.json'))
            print(' verdict', json.dumps(v)[:700])
        except Exception as e:
            print(' verdict err', e)
        tags = collections.Counter()
        with open(d + '/logcat.txt', errors='replace') as f:
            for line in f:
                m = re.search(r'\[(\w+)\]', line)
                if m:
                    tags[m.group(1)] += 1
                if 'hakuX-pace' in line:
                    tags['hakuX-pace'] += 1
        print(' tags', tags.most_common(30))
