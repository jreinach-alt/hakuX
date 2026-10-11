# Probe-gate: replay the labelled stored triplets through the old and candidate change measures.
# Decision rule (same shape as confirm()): accept when the input change is at least PROBE_MOVED and beyond
# 1.5x the idle change (self-moving scenes, ctrl > SELF_MOVING, skip the ratio test, as confirm() does).
import json, os, sys
import numpy as np
sys.path.insert(0, 'docs/testing/titles')
import pathfind as pf
import classify

PM = pf.PROBE_MOVED
SELF = pf.SELF_MOVING
MS = classify.MOTION_SIZE

def grey_small(path):
    g = pf.grey(path).resize(MS, classify.Image.BILINEAR)
    return np.asarray(g, dtype=np.float64)

def frac(x, y, step):
    return float((np.abs(x - y) > step).mean())

def contrast_step(a):
    # the step scales with the frame's own contrast: dark scenes need a smaller grey step
    s = float(a.std())
    return min(classify.MOTION_PIXEL, max(4.0, 0.6 * s))

def shift_px(x, y):
    # phase correlation at 160x120: the integer translation of y relative to x and the peak height
    X = np.fft.fft2(x - x.mean())
    Y = np.fft.fft2(y - y.mean())
    R = X * np.conj(Y)
    R = R / (np.abs(R) + 1e-9)
    r = np.fft.ifft2(R).real
    idx = np.unravel_index(np.argmax(r), r.shape)
    dy, dx = idx
    if dy > r.shape[0] // 2: dy -= r.shape[0]
    if dx > r.shape[1] // 2: dx -= r.shape[1]
    return int(dx), int(dy), float(r.max())

def measures(a_png, b_png, c_png):
    A, B, C = grey_small(a_png), grey_small(b_png), grey_small(c_png)
    out = {}
    # old: classify.motion's fixed 16-level step
    ctrl_old = frac(A, B, classify.MOTION_PIXEL)
    mov_old = frac(B, C, classify.MOTION_PIXEL)
    out['old'] = (ctrl_old, mov_old)
    # N1: contrast-scaled step (per frame a's std)
    st = contrast_step(A)
    out['n1'] = (frac(A, B, st), frac(B, C, st))
    # N2: N1 plus a global-shift test (a camera pan or a whole-scene move counts even with few pixel steps)
    dx, dy, pk = shift_px(B, C)
    glob = (abs(dx) >= 1 or abs(dy) >= 1) and pk > 0.15
    mov_n2 = out['n1'][1]
    if glob:
        mov_n2 = max(mov_n2, 0.05)
    out['n2'] = (out['n1'][0], mov_n2)
    out['shift'] = (dx, dy, round(pk, 3), glob)
    # N3: normalised difference: each frame z-scored by its own mean/std, step = a quarter sd
    def z(x):
        return (x - x.mean()) / (x.std() + 1e-6)
    za, zb, zc = z(A), z(B), z(C)
    out['n3'] = (frac(za, zb, 0.25), frac(zb, zc, 0.25))
    out['std_a'] = round(float(A.std()), 1)
    return out

def accept(ctrl, mov):
    if mov < PM:
        return False
    if ctrl > SELF:
        return True
    return mov >= 1.5 * ctrl

def main():
    trip = json.load(open('scratch/probegate/triplets.json'))
    labels = json.load(open('scratch/probegate/labels.json'))
    s1 = json.load(open('scratch/probegate/sample.json'))
    s2 = json.load(open('scratch/probegate/sample2.json'))
    rows = []
    for k, case in enumerate(s1):
        lab = labels['sample1'].get('%02d' % (k + 1))
        rows.append(('s1', k + 1, case, lab))
    for k, case in enumerate(s2):
        lab = labels['sample2'].get('%02d' % (k + 1))
        rows.append(('s2', k + 1, case, lab))
    res = []
    for s, n, case, lab in rows:
        m = measures(case['a'], case['b'], case['c'])
        rec = {'set': s, 'n': n, 'run': case['run'], 'pre': case['pre'], 'label': lab,
               'old_verdict': case.get('verdict'), 'shift': m['shift'], 'std_a': m['std_a']}
        for key in ('old', 'n1', 'n2', 'n3'):
            ctrl, mov = m[key]
            rec[key] = {'ctrl': round(ctrl, 4), 'moved': round(mov, 4), 'accept': accept(ctrl, mov)}
        res.append(rec)
    json.dump(res, open('scratch/probegate/gate_results.json', 'w'), indent=1)
    print('set n label run pre | std | old ctrl/mov acc | n1 | n2 | n3 | shift')
    for r in res:
        def f(key):
            v = r[key]
            return '%.3f/%.3f %s' % (v['ctrl'], v['moved'], 'A' if v['accept'] else '.')
        print('%s %02d %s %-30s %s | %5.1f | %s | %s | %s | %s | %s' % (
            r['set'], r['n'], r['label'] or '-', r['run'][:30], r['pre'], r['std_a'],
            f('old'), f('n1'), f('n2'), f('n3'), r['shift']))

if __name__ == '__main__':
    main()
