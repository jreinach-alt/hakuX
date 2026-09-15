#!/usr/bin/env python3
"""Baseline the Blend_tests suite and pivot the residual by blend equation and
by blend factor.

Reproduces the tables in
docs/investigations/blend-tests-is-two-signed-equations.md: 91.3% of the suite's
residual is the two SIGNED equations (SADD, SREVSUB), which gl/constants.h:129
and vk/constants.h:74 both alias to their unsigned counterparts; the other five
are a +/-2 rounding floor and MAX is byte-exact in all fifteen captures.
Pivoted by factor the residual is flat, so the factor plays no part.

Usage:  blend_equation_baseline.py <ours_dir> <goldens_dir>

  ours_dir     holds "Blend_tests::#spot_1_ADD.png" etc.
  goldens_dir  holds "Blend_tests/#spot_1_ADD.png" etc.
"""
import os
import sys

import numpy as np
from PIL import Image

if len(sys.argv) != 3:
    sys.exit(__doc__)
OURS = sys.argv[1]
GOLD = os.path.join(sys.argv[2], 'Blend_tests')

rows=[]
missing=[]
for f in sorted(os.listdir(OURS)):
    if not f.startswith('Blend_tests::'): continue
    name=f.split('::',1)[1]
    g=os.path.join(GOLD,name)
    if not os.path.exists(g): missing.append(name); continue
    a=np.asarray(Image.open(os.path.join(OURS,f)).convert('RGB')).astype(np.int16)
    b=np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
    if a.shape!=b.shape: missing.append(name+' SHAPE'); continue
    d=np.abs(a-b)
    stem=name[:-4].replace('#spot_','')
    eq=stem.rsplit('_',1)[1]; fac=stem.rsplit('_',1)[0]
    rows.append(dict(name=stem, eq=eq, fac=fac,
                     diff=int((d>0).sum()), total=d.size,
                     absum=int(d.sum()), maxd=int(d.max()),
                     gt16=int((d>16).sum())))
print(f"{len(rows)} captures scored, {len(missing)} missing golden")
if missing: print("  missing:", missing[:5])
print(f"TOTAL differing channels: {sum(r['diff'] for r in rows):,}   abs-sum {sum(r['absum'] for r in rows):,}")
exact=[r for r in rows if r['diff']==0]
print(f"EXACT captures: {len(exact)}" + (f"  -> {[r['name'] for r in exact]}" if exact else ""))

def pivot(key, title):
    b={}
    for r in rows: b.setdefault(r[key],[]).append(r)
    print(f"\n--- by {title} ---")
    print(f"{title:<12} {'n':>3} {'differing':>12} {'share':>7} {'abs-sum':>13} {'max|d|':>7} {'exact':>6}")
    tot=sum(r['diff'] for r in rows)
    for k,v in sorted(b.items(), key=lambda kv:-sum(r['diff'] for r in kv[1])):
        d=sum(r['diff'] for r in v)
        print(f"{k:<12} {len(v):3d} {d:12,} {100*d/tot:6.1f}% {sum(r['absum'] for r in v):13,} "
              f"{max(r['maxd'] for r in v):7d} {sum(1 for r in v if r['diff']==0):6d}")
pivot('eq','equation')
pivot('fac','factor')
