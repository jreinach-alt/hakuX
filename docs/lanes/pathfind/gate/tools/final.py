# Score the full chain (new routing + strong-model confirm) against the current labels.
import json
from collections import defaultdict

labels = json.load(open('scratch/probegate/labels.json'))
gate = json.load(open('scratch/probegate/gate_results.json'))
rep = json.load(open('scratch/probegate/replay_results.json'))
lab = {}
for g in gate:
    key = g['run'] + '/' + g['pre']
    lab[key] = labels['sample1' if g['set'] == 's1' else 'sample2'].get('%02d' % g['n'])

rows = []
for key, r in rep.items():
    L = lab.get(key)
    if L not in ('R', 'U', 'C', 'M', 'P'):
        continue
    rows.append((L, key, r))

rtot = sum(1 for L, _, _ in rows if L == 'R')
racc = sum(1 for L, _, r in rows if L == 'R' and r['accepted'])
catn = defaultdict(int)
catacc = defaultdict(int)
for L, key, r in rows:
    if L != 'R':
        catn[L] += 1
        catacc[L] += int(r['accepted'])
nonr = sum(catn.values())
nonr_acc = sum(catacc.values())
agree = (racc + nonr - nonr_acc) / (rtot + nonr)
print('labelled cases in replay: %d (R %d, non-R %d)' % (len(rows), rtot, nonr))
print('real control accepted by the full chain: %d/%d' % (racc, rtot))
print('non-control accepted: %d/%d  (U %d/%d, C %d/%d, M %d/%d, P %d/%d)' % (
    nonr_acc, nonr,
    catacc['U'], catn['U'], catacc['C'], catn['C'], catacc['M'], catn['M'], catacc['P'], catn['P']))
print('agreement %.0f%%' % (100 * agree))
print()
print('route counts:')
rc = defaultdict(int)
for L, key, r in rows:
    rc[r['route'].split(' (')[0]] += 1
for k, v in sorted(rc.items()):
    print('  %-42s %d' % (k, v))
print()
print('non-control accepted (the cases to explain):')
for L, key, r in rows:
    if L != 'R' and r['accepted']:
        print('  %s %-40s %s | %s' % (L, key, r['route'][:30], (r.get('answer') or {}).get('why', '')[:150]))
print()
print('real control refused (the cases to explain):')
for L, key, r in rows:
    if L == 'R' and not r['accepted']:
        print('  R %-40s %s | ctrl %.3f mov %.3f | %s' % (key, r['route'][:30], r['ctrl'], r['moved'], (r.get('answer') or {}).get('why', '')[:150]))
