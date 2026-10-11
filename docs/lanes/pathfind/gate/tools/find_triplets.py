# Enumerate every stored probe triplet (a, b, c) with the old pathfind verdict.
import glob, json, os
from collections import Counter

ROOTS = ['scratch/runs', 'docs/lanes/pathfind/runs']
out = []
for root in ROOTS:
    for fdir in sorted(glob.glob(os.path.join(root, '*', 'frames'))):
        run = os.path.dirname(fdir)
        name = os.path.basename(run)
        for p in sorted(glob.glob(os.path.join(fdir, '*-probe-a.jpg'))):
            pre = os.path.basename(p)[:-len('-probe-a.jpg')]
            b = os.path.join(fdir, pre + '-probe-b.jpg')
            c = os.path.join(fdir, pre + '-probe-c.jpg')
            if not (os.path.exists(b) and os.path.exists(c)):
                continue
            rec = {'run': name, 'pre': pre, 'a': p, 'b': b, 'c': c}
            for side in ('left', 'right'):
                q = os.path.join(fdir, pre + '-probe-' + side + '.jpg')
                rec[side] = q if os.path.exists(q) else None
            out.append(rec)
json.dump(out, open('scratch/probegate/triplets.json', 'w'), indent=1)
print(len(out), 'triplets')
print(Counter(t['run'] for t in out))
