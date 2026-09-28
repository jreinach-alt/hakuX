"""Idle (pre-launch) net power per device from thermal.jsonl samples labelled
before the app runs, and the in-run samples for comparison."""
import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import os, json, collections, statistics as st
D = RUNS
by = collections.defaultdict(list)
labels = collections.Counter()
for run in sorted(os.listdir(D)):
    p = os.path.join(D, run)
    try:
        v = json.load(open(os.path.join(p, 'verdict.json')))
    except Exception:
        continue
    dev = v.get('device')
    for l in open(os.path.join(p, 'thermal.jsonl')):
        try: j = json.loads(l)
        except Exception: continue
        lab = j.get('label'); labels[lab] += 1
        pw = j.get('pw') or {}
        b = pw.get('battery') or {}; u = pw.get('usb') or {}
        try:
            bw = -b['current_now'] * b['voltage_now'] / 1e12  # + discharging
            uw = (u.get('current_now') or 0) * (u.get('voltage_now') or 0) / 1e12 if u.get('online') else 0.0
        except Exception:
            continue
        by[(dev, lab)].append((bw + uw, run))
print(labels)
for k in sorted(by, key=str):
    xs = [x for x, _ in by[k]]
    print(k, len(xs), 'median net W %.2f  p10 %.2f p90 %.2f' % (st.median(xs), sorted(xs)[len(xs)//10], sorted(xs)[9*len(xs)//10]))
