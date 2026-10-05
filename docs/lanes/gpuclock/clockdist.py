#!/usr/bin/env python3
"""Every GPU clock step and ceiling the 30 s thermal sampler has read, per
device and per performance_mode, over the newest N result dirs.

    clockdist.py [N]

Answers: which steps does each handheld's kgsl ladder have, what ceiling
(max_gpuclk) does it report, and how often does the stock governor leave
the mode's floor at all, over every kind of run (menus, loads, gameplay).
"""
import ast, collections, json, os, sys

D = '/home/justin/hakux-work/dispatch/results'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 900


def lit(v):
    if isinstance(v, str):
        try:
            return ast.literal_eval(v)
        except Exception:
            return None
    return v


seen = collections.defaultdict(collections.Counter)
cap = collections.defaultdict(collections.Counter)
runs = collections.Counter()
for d in sorted(os.listdir(D))[-N:]:
    p = os.path.join(D, d)
    try:
        r = json.load(open(os.path.join(p, 'result.json')))
    except Exception:
        continue
    dev = r.get('device_label')
    if dev not in ('nova', 'thor') or not os.path.exists(os.path.join(p, 'thermal.jsonl')):
        continue
    pm = None
    try:
        pm = json.load(open(os.path.join(p, 'perf_regimen.json'))).get('perf_mode')
    except Exception:
        pass
    key = '%s pm=%s' % (dev, pm)
    runs[key] += 1
    for line in open(os.path.join(p, 'thermal.jsonl')):
        try:
            s = json.loads(line)
        except ValueError:
            continue
        g = (lit(s.get('clk')) or {}).get('gpu') or {}
        if isinstance(g.get('gpuclk'), int):
            seen[key][g['gpuclk'] // 1000000] += 1
        if isinstance(g.get('max_gpuclk'), int):
            cap[key][g['max_gpuclk'] // 1000000] += 1
for k in sorted(seen):
    tot = sum(seen[k].values())
    print('%-14s runs=%-4d samples=%-6d' % (k, runs[k], tot),
          ' '.join('%d:%.1f%%' % (m, 100.0 * n / tot) for m, n in sorted(seen[k].items())),
          '| ceiling', dict(sorted(cap[k].items())))
