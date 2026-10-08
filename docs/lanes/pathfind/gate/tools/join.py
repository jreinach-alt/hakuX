# Join every stored triplet to its probe step record (old verdict, old numbers).
import json, random
from collections import Counter

trip = json.load(open('scratch/probegate/triplets.json'))
ROOT = {'scratch/runs': 'scratch/runs', 'docs/lanes/pathfind/runs': 'docs/lanes/pathfind/runs'}
for t in trip:
    run_dir = None
    for root in ROOT:
        cand = root + '/' + t['run']
        import os
        if os.path.isdir(cand):
            run_dir = cand
            break
    t['verdict'] = None
    t['old_ctrl'] = None
    t['old_moved'] = None
    t['steps_file'] = None
    if run_dir and os.path.exists(run_dir + '/steps.jsonl'):
        n = int(t['pre'])
        for line in open(run_dir + '/steps.jsonl'):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get('state') == 'probe' and r.get('n') == n:
                t['verdict'] = (r.get('verdict') or 'no verdict')[:90]
                t['steps_file'] = run_dir + '/steps.jsonl'
                why = r.get('why', '')
                # 'control X, under input Y'
                try:
                    parts = why.replace('control', '').replace('under input', '').split(',')
                    t['old_ctrl'] = float(parts[0])
                    t['old_moved'] = float(parts[1])
                except Exception:
                    pass
                break
json.dump(trip, open('scratch/probegate/triplets.json', 'w'), indent=1)
print(Counter((t['verdict'] or 'NONE').split(':')[0][:20] for t in trip).most_common(12))
