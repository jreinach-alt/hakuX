#!/usr/bin/env python3
"""NFS Most Wanted cold race start, submit ring depth 2 vs 3 (#433, lane.coldstart1010).

    coldread.py <run> [...] --expect docs/testing/predictions/coldstart1010-depth.json
    coldread.py <run> [...]                       per-run table only, no verdict

Arms come from request.json env, as postput1010's ppread.py reads them: B holds every b_env entry, A every
a_env entry and none of the b_env entries a_env lacks. Both arms run the six switches and HAKUX_PROBE_WAITS=1;
B adds HAKUX_SUBMIT_FRAMES=3.

Pace is ppread.pace_run's (raread.py's windows and selection): cold = start 1 (`mark gameplay`) -2 .. +1.5 s,
warm = go2 .. go12 over the same window, post-GO = +1.5 .. +12 s. An arm's figure is the mean of its runs'.

Mechanism: the `[probe1010]` lines (drawrec1010 proberead.read_probe, one per 60 flips) printed in
[gameplay + MLO, gameplay + MHI] (default -4,3.5: a 60-flip line is ~2 s, and the 3.5 s pace window holds
one or two). Per frame: rotations, blocking rotations (a fence wait >= 100 us), and ms blocked. Warm is
the same over go2 .. go12.

Legs, the prediction's `expect` keys:
  V   every run: ppread's checks (12 marks, valid starts, no boot input failure, warm pace lines, a g11
      frame for every valid warm start, perflog as registered, arm from env, the six switches' lines), and
      `[probe1010] waits=1`, and `[postput] on` when a_env holds HAKUX_POSTED_PUT=1 (coldstart1010-stack.json);
      B: `[coldstart1010] submit_frames=3` and buffer_init's `(3 frames`; A: neither the first, and
      `(2 frames`. Motion in the g11 frames: by eye, NOTES.md.
  K   the brief's target: cold B <= K_b_max ms, OR cold v2 share B - A >= K_dv2_min points
  C   cold B - A <= C_d_max ms
  W   warm countdown B - A <= W_d_max ms
  G   post-GO B - A <= G_d_max ms
  M   cold ms per frame blocked in rotation fence waits, B <= M_frac x A
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'postput1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'drawrec1010'))
import ppread  # noqa: E402
import proberead  # noqa: E402
import raread  # noqa: E402  (ppread puts reportasync1010 on the path)

LOG_PROBE = r'\[probe1010\] waits=1'
LOG_B = r'\[coldstart1010\] submit_frames=3 '
LOG_B_FRAMES = r'per-frame staging created \(3 frames'
LOG_A_FRAMES = r'per-frame staging created \(2 frames'


def probe_window(d, mlo, mhi):
    _, rows = proberead.read_probe(d)
    marks, _, _, _ = raread.read(d)
    good = raread.valid(marks, raread.bad_starts(d))
    out = {}
    for which in ('cold', 'warm'):
        sel = raread.sel([(r['t'], r) for r in rows], good, mlo, mhi, which)
        s = proberead.probe_stats([r for _, r in sel])
        out[which] = s
    return out


def pf(s, k, w=5, p=2):
    return f'{s[k]:{w}.{p}f}' if s else ' ' * (w - 1) + '-'


def logs_ok(d, arm, exp):
    out = []
    seen = raread.has_log(d, LOG_PROBE)
    out.append((seen, f'/{LOG_PROBE}/ {"seen" if seen else "NOT seen"}'))
    if 'HAKUX_POSTED_PUT=1' in (exp.get('a_env') or []):
        seen = raread.has_log(d, ppread.LOG_B)
        out.append((seen, f'/{ppread.LOG_B}/ {"seen" if seen else "NOT seen"}'))
    seen = raread.has_log(d, LOG_B)
    out.append((seen == (arm == 'B'), f'/{LOG_B}/ {"seen" if seen else "not seen"} on {arm}'))
    rx = LOG_B_FRAMES if arm == 'B' else LOG_A_FRAMES
    seen = raread.has_log(d, rx)
    out.append((seen, f'/{rx}/ {"seen" if seen else "NOT seen"} on {arm}'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--post', default='1.5,12')
    ap.add_argument('--mwindow', default='-4,3.5')
    ap.add_argument('--expect')
    a = ap.parse_args()
    exp = json.load(open(a.expect)) if a.expect else {}
    lo, hi = (float(x) for x in a.window.split(','))
    plo, phi = (float(x) for x in a.post.split(','))
    mlo, mhi = (float(x) for x in a.mwindow.split(','))
    e = exp.get('expect', {})

    # ppread's per-run table and V checks; its own pace legs are not in this prediction's expect.
    legs, per, runs = [], {'A': [], 'B': []}, []
    print(f"{'run':40s} arm  cold1  warm  post   cold v2   warm v2/v3/v4   valid")
    for d in a.dirs:
        name = os.path.basename(d.rstrip('/'))
        arm = ppread.arm_of(d, exp) if exp else None
        r = ppread.pace_run(d, lo, hi, plo, phi)
        r['cold_v2'] = raread.vshare(r['cold'], 2)
        r['probe'] = probe_window(d, mlo, mhi)
        runs.append((d, r))
        cv2 = f"{r['cold_v2']:5.0f} %" if r['cold_v2'] is not None else '    - '
        print(f"{name:40s} {arm or '?':3s} {ppread.fmt(r['cold_ms'])} {ppread.fmt(r['warm_ms'])} "
              f"{ppread.fmt(r['post_ms'])}   {cv2}   {ppread.hist(r['warm']):14s}  "
              f"{len(r['good'])}/{len(r['marks'])}")
        if not exp:
            continue
        legs.append(('V', arm is not None, f'{name}: arm {arm} from request.json env {ppread.request(d).get("env")}'))
        legs.append(('V', ppread.perflog_of(d) == bool(exp.get('perflog')), f'{name}: perflog {ppread.perflog_of(d)}'))
        for rx in ppread.logs_always(exp):
            seen = raread.has_log(d, rx)
            legs.append(('V', seen, f'{name}: /{rx}/ {"seen" if seen else "NOT seen"}'))
        for ok, what in logs_ok(d, arm, exp):
            legs.append(('V', ok, f'{name}: {what}'))
        legs.append(('V', len(r['marks']) >= e['V_min_marks'], f'{name}: {len(r["marks"])} marks'))
        legs.append(('V', len(r['good']) >= e['V_min_valid_starts'],
                     f'{name}: {len(r["good"])} valid starts >= {e["V_min_valid_starts"]}'
                     + ''.join(f'; dropped {k} ({v})' for k, v in r['bad'].items())))
        legs.append(('V', 'gameplay' not in r['bad'],
                     f'{name}: boot inputs went through before `mark gameplay`'
                     + (f' -- NO: {r["bad"]["gameplay"]}' if 'gameplay' in r['bad'] else '')))
        legs.append(('V', len(r['warm']) >= e['V_min_warm_lines'],
                     f'{name}: {len(r["warm"])} warm pace lines >= {e["V_min_warm_lines"]}'))
        legs.append(('V', r['probe']['cold'] is not None, f'{name}: [probe1010] lines in the cold window'))
        fr = ppread.g11(d)
        want = [ppread.start_no(mk[1]) for mk in r['good'] if mk[1] != 'gameplay']
        miss = [n for n in want if n not in fr]
        legs.append(('V', not miss, f'{name}: g11 frames for {len(want) - len(miss)} of {len(want)} valid warm starts'
                     + (f', missing s{miss}' if miss else '') + ' (motion: by eye, NOTES.md)'))
        if arm:
            per[arm].append(r)

    print(f"\n[probe1010] per frame, lines printed in mark{mlo:+.1f} .. mark{mhi:+.1f} s"
          f"\n{'run':40s} which  frames   rot    blk   ms blk   mid/f  mid ms/f")
    for d, r in runs:
        for which in ('cold', 'warm'):
            s = r['probe'][which]
            print(f"{os.path.basename(d.rstrip('/')):40s} {which:5s} {pf(s, 'frames', 6, 0)} {pf(s, 'rot')} "
                  f"{pf(s, 'blk')} {pf(s, 'rot_ms', 7)}  {pf(s, 'mid')} {pf(s, 'mid_ms', 7)}")
    if not exp:
        return 0

    for arm in ('A', 'B'):
        legs.append(('V', len(per[arm]) == exp.get('runs_per_arm', 2),
                     f'{arm}: {len(per[arm])} runs, registered {exp.get("runs_per_arm", 2)}'))
    m = {arm: {k: ppread.mean([r[k + '_ms'] for r in per[arm]]) for k in ('cold', 'warm', 'post')}
         for arm in ('A', 'B')}
    if any(m[x][k] is None for x in m for k in m[x]):
        ppread.verdict(legs)
        print('VERDICT: VOID -- an arm has no pace lines in a window')
        return 2
    cv2 = {arm: ppread.mean([r['cold_v2'] for r in per[arm]]) for arm in ('A', 'B')}
    blk = {arm: ppread.mean([r['probe']['cold']['rot_ms'] for r in per[arm] if r['probe']['cold']])
           for arm in ('A', 'B')}
    print(f"\nmean of runs   cold1  warm  post   cold v2   cold ms/f blocked in rotation")
    for arm in ('A', 'B'):
        print(f"  {arm}           {ppread.fmt(m[arm]['cold'])} {ppread.fmt(m[arm]['warm'])} "
              f"{ppread.fmt(m[arm]['post'])}   {cv2[arm]:5.1f} %   {blk[arm] if blk[arm] is not None else float('nan'):.2f}")
    print('\nJUDGE (' + exp.get('registered_utc', '?') + ')')
    ca, cb = m['A']['cold'], m['B']['cold']
    dv2 = cv2['B'] - cv2['A']
    legs.append(('K', cb <= e['K_b_max'] or dv2 >= e['K_dv2_min'],
                 f"cold B {cb:.2f} ms <= {e['K_b_max']}, or cold v2 B - A {dv2:+.1f} points >= {e['K_dv2_min']}"))
    legs.append(('C', cb - ca <= e['C_d_max'], f"cold A {ca:.2f} B {cb:.2f}, B - A {cb - ca:+.2f} ms <= {e['C_d_max']}"))
    wa, wb = m['A']['warm'], m['B']['warm']
    legs.append(('W', wb - wa <= e['W_d_max'], f"warm countdown A {wa:.2f} B {wb:.2f}, B - A {wb - wa:+.2f} ms <= {e['W_d_max']}"))
    ga, gb = m['A']['post'], m['B']['post']
    legs.append(('G', gb - ga <= e['G_d_max'], f"post-GO A {ga:.2f} B {gb:.2f}, B - A {gb - ga:+.2f} ms <= {e['G_d_max']}"))
    if blk['A'] is None or blk['B'] is None:
        legs.append(('V', False, 'cold [probe1010] lines on both arms'))
    else:
        legs.append(('M', blk['B'] <= e['M_frac'] * blk['A'],
                     f"cold ms/frame blocked in rotation fence waits A {blk['A']:.2f} B {blk['B']:.2f} "
                     f"<= {e['M_frac']} x A"))
    return ppread.verdict(legs)


if __name__ == '__main__':
    sys.exit(main())
