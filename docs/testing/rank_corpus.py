"""Rank every suite in the single-binary corpus by PER-CAPTURE residual.

Usage:  rank_corpus.py <corpus_root> <goldens_root>

Two traps this encodes, both of which bit me:

* Only the DIRS list is scored. /tmp/pgraph-run holds ~140 other score_* dirs
  spanning days of different binaries; a glob of "score_*" silently mixes them.
  That is not a style point -- globbing score_* and taking the first hit made
  Window_clip read as 92/92 byte-exact off an OLD binary when the corpus binary
  is 8/92.
* Rank by PER CAPTURE, not by total. A suite's share of the corpus total is a
  statement about how many captures it has as much as about the defect.
"""
import os, sys, collections
import numpy as np
from PIL import Image
ROOT=sys.argv[1] if len(sys.argv)>1 else '/tmp/pgraph-run'
GD=sys.argv[2] if len(sys.argv)>2 else '/tmp/goldens/results'
DIRS=['score_cx_aborts','score_cx_attr','score_cx_blend','score_cx_bump','score_cx_clip11',
      'score_cx_fmt','score_cx_fog','score_cx_light','score_cx_line','score_cx_risk',
      'score_cx_signed','score_cx_solo_bumpenvmap','score_cx_tex3','score_cx_vsr',
      'score_surfbase','score_lfix']
seen={}; dup=0; missing=0; shape=0
for d in DIRS:
    base=os.path.join(ROOT,d)
    subs=[os.path.join(base,s) for s in os.listdir(base)] if os.path.isdir(base) else []
    for sub in subs:
        if not os.path.isdir(sub): continue
        for f in sorted(os.listdir(sub)):
            if not f.endswith('.png') or '::' not in f: continue
            key=f[:-4]
            if key in seen: dup+=1; continue
            suite,name=key.split('::',1)
            g=os.path.join(GD,suite,name+'.png')
            if not os.path.exists(g): missing+=1; continue
            try:
                a=np.asarray(Image.open(os.path.join(sub,f)).convert('RGB')).astype(np.int16)
                b=np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
            except Exception: missing+=1; continue
            if a.shape!=b.shape: shape+=1; continue
            dd=np.abs(a-b)
            seen[key]=(suite,int((dd>0).sum()),int(dd.sum()))
print(f'scored {len(seen)}  dup-skipped {dup}  no-golden {missing}  shape-mismatch {shape}')
agg=collections.defaultdict(lambda:[0,0,0])
for suite,ch,tot in seen.values():
    e=agg[suite]; e[0]+=1; e[1]+=ch; e[2]+=tot
rows=sorted(agg.items(), key=lambda kv:-(kv[1][1]//max(kv[1][0],1)))
print(f'{"suite":42s} {"n":>4s} {"channels":>10s} {"per-cap":>9s} {"mean|d|":>7s}')
for s,(n,ch,tot) in rows:
    if ch==0: continue
    print(f'{s:42s} {n:4d} {ch:10d} {ch//n:9d} {tot/ch:7.2f}')
nz=[s for s,(n,ch,t) in agg.items() if ch==0]
print(f'\nBYTE-EXACT SUITES ({len(nz)}): ' + ', '.join(sorted(nz)))
