# Score decision rules over gate_results.json: real-control acceptance and non-control acceptance by category.
import json
from collections import defaultdict

res = json.load(open('scratch/probegate/gate_results.json'))
labelled = [r for r in res if r['label'] in ('R', 'U', 'C', 'M', 'P')]

def rule(ctrl, mov, floor, ratio, selfmove_exc):
    if mov < floor:
        return False
    if ctrl > 0.15 and selfmove_exc:
        return True
    return mov >= ratio * ctrl

RULES = {
    'old (0.03 floor, selfmove skips ratio)': ('old', 0.03, 1.5, True),
    'n1 contrast step (floor 0.03)': ('n1', 0.03, 1.5, True),
    'n1 floor 0.004, selfmove skips ratio': ('n1', 0.004, 1.5, True),
    'n1 floor 0.004, ratio always': ('n1', 0.004, 1.5, False),
    'n2 (n1+shift) floor 0.004, ratio always': ('n2', 0.004, 1.5, False),
    'n3 z-score floor 0.004, ratio always': ('n3', 0.004, 1.5, False),
    'n3 z-score floor 0.03, selfmove skips': ('n3', 0.03, 1.5, True),
}

print('%-44s %8s %8s  %s' % ('rule', 'R acc', 'nonR acc', 'non-R accepted by category'))
for name, (key, floor, ratio, exc) in RULES.items():
    racc = 0
    rtot = 0
    cat = defaultdict(int)
    catn = defaultdict(int)
    for r in labelled:
        ctrl, mov = r[key]['ctrl'], r[key]['moved']
        acc = rule(ctrl, mov, floor, ratio, exc)
        if r['label'] == 'R':
            rtot += 1
            racc += acc
        else:
            catn[r['label']] += 1
            if acc:
                cat[r['label']] += 1
    nonr = sum(catn.values())
    nonr_acc = sum(cat.values())
    detail = ' '.join('%s %d/%d' % (k, cat[k], catn[k]) for k in ('U', 'C', 'M', 'P'))
    agree = (racc + (nonr - nonr_acc)) / (rtot + nonr)
    print('%-44s %3d/%-4d %3d/%-4d  %s  agree %.0f%%' % (name, racc, rtot, nonr_acc, nonr, detail, 100 * agree))
