import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import os, re, json, collections
D = RUNS
best = collections.defaultdict(list)
for run in sorted(os.listdir(D)):
    try:
        v = json.load(open(os.path.join(D, run, 'verdict.json')))
    except Exception:
        continue
    mx = 0; last = None
    for l in open(os.path.join(D, run, 'logcat.txt'), errors='replace'):
        if '[surf413]' in l:
            m = re.search(r'invalid=(\d+)', l)
            if m:
                mx = max(mx, int(m.group(1))); last = int(m.group(1))
    if last is not None:
        best[(v.get('name') or '')[:22]].append((mx, run[-24:], v.get('gameplay_s')))
for k, xs in sorted(best.items()):
    xs.sort(reverse=True)
    print('%-22s max invalid %5d (%s, gameplay %ss); runs %d' % (k, xs[0][0], xs[0][1], xs[0][2], len(xs)))
