#!/usr/bin/env python3
"""NFS Most Wanted cold race start, the lock-free wake (#433, lane.lockwake1011).

    wakeread.py <run> [...] --expect docs/testing/predictions/lockwake1011-lockfree_wake.json
    wakeread.py <run> [...]                       per-run table only, no verdict

coldstart1010's coldread.py, re-legged for this A/B. coldread.py tells its arms apart by the submit ring depth,
which both arms here share, so its V fails every A run. Arms come from request.json env, as ppread.py reads
them: B holds every b_env entry, A every a_env entry and none of the b_env entries a_env lacks. Both arms run
the stacked configuration (six switches, HAKUX_PROBE_WAITS=1, HAKUX_POSTED_PUT=1, HAKUX_SUBMIT_FRAMES=3); B
adds HAKUX_LOCKFREE_WAKE=1.

Pace is ppread.pace_run's (raread.py's windows and selection): cold = start 1 (`mark gameplay`) -2 .. +1.5 s,
warm = go2 .. go12 over the same window, post-GO = +1.5 .. +12 s. An arm's figure is the mean of its runs'.
The `[probe1010]` table is printed as coldread.py prints it, for reading; no leg uses it.

Legs, the prediction's `expect` keys:
  V   every run: ppread's checks (valid starts, no boot input failure, warm pace lines, a g11 frame for every
      valid warm start, perflog as registered, arm from env, the six switches' lines), `[probe1010] waits=1`,
      `[postput] on`, `[coldstart1010] submit_frames=3` and buffer_init's `(3 frames`; B: `[lockwake] on`,
      A: no `[lockwake]` line. A: V_min_marks marks. Motion in the g11 frames: by eye, NOTES.md.
  K   the brief's target: cold B <= K_b_max ms AND cold B - A <= K_d_max ms
  C   cold B - A <= C_d_max ms (K's second half alone: a K miss on the bar alone is told from no effect)
  W   warm countdown B - A <= W_d_max ms
  G   post-GO B - A <= G_d_max ms
  M   no hang: every B run reaches V_min_marks marks. Kept out of V, so a B run that stops reads FAIL, not VOID.
      A short B run still gets its cause named; one with a named cause outside the switch is a void.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'coldstart1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'postput1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'drawrec1010'))
import coldread  # noqa: E402
import ppread  # noqa: E402
import raread  # noqa: E402  (ppread puts reportasync1010 on the path)

LOG_WAKE_ON = r'\[lockwake\] on'
LOG_WAKE_ANY = r'\[lockwake\] '


def logs_ok(d, arm):
    out = []
    for rx in (coldread.LOG_PROBE, ppread.LOG_B, coldread.LOG_B, coldread.LOG_B_FRAMES):
        seen = raread.has_log(d, rx)
        out.append((seen, f'/{rx}/ {"seen" if seen else "NOT seen"}'))
    if arm == 'B':
        seen = raread.has_log(d, LOG_WAKE_ON)
        out.append((seen, f'/{LOG_WAKE_ON}/ {"seen" if seen else "NOT seen"} on B'))
    else:
        seen = raread.has_log(d, LOG_WAKE_ANY)
        out.append((not seen, f'/{LOG_WAKE_ANY}/ {"seen" if seen else "not seen"} on {arm}'))
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

    legs, per, runs, short_b = [], {'A': [], 'B': []}, [], []
    print(f"{'run':40s} arm  cold1  warm  post   cold v2   warm v2/v3/v4   valid")
    for d in a.dirs:
        name = os.path.basename(d.rstrip('/'))
        arm = ppread.arm_of(d, exp) if exp else None
        r = ppread.pace_run(d, lo, hi, plo, phi)
        r['cold_v2'] = raread.vshare(r['cold'], 2)
        r['probe'] = coldread.probe_window(d, mlo, mhi)
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
        for ok, what in logs_ok(d, arm):
            legs.append(('V', ok, f'{name}: {what}'))
        nm = len(r['marks'])
        if arm == 'B':
            if nm < e['V_min_marks']:
                short_b.append(f'{name} {nm}')
        else:
            legs.append(('V', nm >= e['V_min_marks'], f'{name}: {nm} marks'))
        legs.append(('V', len(r['good']) >= e['V_min_valid_starts'],
                     f'{name}: {len(r["good"])} valid starts >= {e["V_min_valid_starts"]}'
                     + ''.join(f'; dropped {k} ({v})' for k, v in r['bad'].items())))
        legs.append(('V', 'gameplay' not in r['bad'],
                     f'{name}: boot inputs went through before `mark gameplay`'
                     + (f' -- NO: {r["bad"]["gameplay"]}' if 'gameplay' in r['bad'] else '')))
        legs.append(('V', len(r['warm']) >= e['V_min_warm_lines'],
                     f'{name}: {len(r["warm"])} warm pace lines >= {e["V_min_warm_lines"]}'))
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
            pf = coldread.pf
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
    print(f"\nmean of runs   cold1  warm  post   cold v2 (read, not judged)")
    for arm in ('A', 'B'):
        print(f"  {arm}           {ppread.fmt(m[arm]['cold'])} {ppread.fmt(m[arm]['warm'])} "
              f"{ppread.fmt(m[arm]['post'])}   {cv2[arm]:5.1f} %")
    print('\nJUDGE (' + exp.get('registered_utc', '?') + ')')
    ca, cb = m['A']['cold'], m['B']['cold']
    legs.append(('K', cb <= e['K_b_max'] and cb - ca <= e['K_d_max'],
                 f"cold B {cb:.2f} ms <= {e['K_b_max']}, and B - A {cb - ca:+.2f} ms <= {e['K_d_max']}"))
    legs.append(('C', cb - ca <= e['C_d_max'], f"cold A {ca:.2f} B {cb:.2f}, B - A {cb - ca:+.2f} ms <= {e['C_d_max']}"))
    wa, wb = m['A']['warm'], m['B']['warm']
    legs.append(('W', wb - wa <= e['W_d_max'], f"warm countdown A {wa:.2f} B {wb:.2f}, B - A {wb - wa:+.2f} ms <= {e['W_d_max']}"))
    ga, gb = m['A']['post'], m['B']['post']
    legs.append(('G', gb - ga <= e['G_d_max'], f"post-GO A {ga:.2f} B {gb:.2f}, B - A {gb - ga:+.2f} ms <= {e['G_d_max']}"))
    legs.append(('M', not short_b, f"every B run reached {e['V_min_marks']} marks"
                 + (f" -- NO: {', '.join(short_b)}" if short_b else '')))
    return ppread.verdict(legs)


if __name__ == '__main__':
    sys.exit(main())
