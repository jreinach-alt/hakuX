#!/usr/bin/env python3
"""NFS Most Wanted race start with and without the posted DMA_PUT store (#433, lane.postput1010).

    ppread.py <run> [...] --expect docs/testing/predictions/postput1010-nfs.json
    ppread.py <A> <B> --expect docs/testing/predictions/postput1010-ftpair.json
    ppread.py <run> [...]                       per-run table only, no verdict

Both arms run HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1 (the prediction's a_env); B adds HAKUX_POSTED_PUT=1.
A run's arm is read from its request.json env: B when it holds every b_env entry, A when it holds every
a_env entry and none of the b_env entries that a_env lacks. The build's own lines must agree on every run:
`[reportasync] on` and `[texscan] on` always, `[postput] on` on B only.

Pace (a prediction with perflog false). Windows and selection are raread.py's (docs/lanes/reportasync1010),
which phaseread.py (docs/lanes/nfs30plan1010) also uses: a `hakuX-pace` line counts for a start when its
print time falls in [mark+LO, mark+HI]; countdown -2 .. +1.5 s, post-GO +1.5 .. +12 s; cold = start 1
(`mark gameplay`), warm = go2 .. go12. A start whose route input failed or hung (raread.bad_starts) is left
out. A run's period over a window is sum(ms) / (60 x lines); an arm's is the MEAN OF ITS RUNS' periods
(the brief's rule), so each run weighs the same whatever its line count. Legs:

  V  every run: >= V_min_marks marks, >= V_min_valid_starts valid starts, >= V_min_warm_lines warm pace
     lines, an `s*-g11` frame for every valid warm start, perflog as registered, the arm read from env,
     and the log lines above. The frames are listed, not read: whether the car moves in them is checked
     by eye and written in NOTES.md, and V is not passed without that.
  P  warm countdown, B - A <= P_d_max
  T  warm countdown, B <= T_b_max
  G  post-GO warm, B - A <= G_d_max
  C  cold start 1, B <= A + C_d_max

Frametrace (a prediction with perflog true): one run per arm, read by ftpair.load (reportasync1010), the
frame's END in the window. Prints ftpair's PFIFO account and ftbuckets's guest line for cold, warm and
post-GO, all frames and heavy (vb >= 3), then judges:

  V  marks, valid starts, >= V_min_warm_frames warm frames per run, env, perflog, log lines
  L  all warm frames, the guest's wait for pfifo.lock to store DMA_PUT (lockw), ms per frame:
     A >= L_a_min, B <= L_b_max. The mechanism: the posted store removes that wait.
  Q  all warm frames, the share where the guest is busy (work + v_blk, ftbuckets.gbusy) past 2 VBLANKs:
     A >= Q_a_min %, B <= Q_b_max %. The guest leaves the critical path rather than waiting elsewhere.
All warm frames, not heavy ones: B is meant to turn heavy frames into light ones, so its remaining heavy
frames are a different selection from A's.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reportasync1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs30plan1010'))
import raread  # noqa: E402

LOGS_ALWAYS = [r'\[reportasync\] on', r'\[texscan\] on']
LOG_B = r'\[postput\] on'


def request(d):
    try:
        return json.load(open(os.path.join(d, 'request.json')))
    except (OSError, ValueError):
        return {}


def arm_of(d, exp):
    env = request(d).get('env') or []
    a_env, b_env = exp.get('a_env') or [], exp.get('b_env') or []
    if all(x in env for x in b_env):
        return 'B'
    if all(x in env for x in a_env) and not any(x in env for x in b_env if x not in a_env):
        return 'A'
    return None


def logs_ok(d, arm):
    out = []
    for rx in LOGS_ALWAYS:
        seen = raread.has_log(d, rx)
        out.append((seen, f'/{rx}/ {"seen" if seen else "NOT seen"}'))
    seen = raread.has_log(d, LOG_B)
    out.append((seen == (arm == 'B'), f'/{LOG_B}/ {"seen" if seen else "not seen"} on {arm}'))
    return out


def g11(d):
    out = {}
    for p in glob.glob(os.path.join(d, 'route-frames', '*-s*-g11.png')):
        m = re.search(r'-s(\d+)-g11\.png$', p)
        if m:
            out[int(m.group(1))] = os.path.basename(p)
    return out


def start_no(name):
    return 1 if name == 'gameplay' else int(name[2:])


def perflog_of(d):
    return str(request(d).get('perflog') or '') == 'true'


def pace_run(d, lo, hi, plo, phi):
    marks, pace, _, _ = raread.read(d)
    bad = raread.bad_starts(d)
    good = raread.valid(marks, bad)
    r = {'marks': marks, 'bad': bad, 'good': good,
         'cold': raread.sel(pace, good, lo, hi, 'cold'),
         'warm': raread.sel(pace, good, lo, hi, 'warm'),
         'post': raread.sel(pace, good, plo, phi, 'warm')}
    for k in ('cold', 'warm', 'post'):
        r[k + '_ms'] = raread.period(r[k])
    return r


def hist(lines):
    if not lines:
        return '-'
    return '/'.join(f'{raread.vshare(lines, k):.0f}' for k in (2, 3, 4)) + ' %'


def fmt(x):
    return f'{x:5.1f}' if x is not None else '    -'


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def pace_judge(dirs, exp, lo, hi, plo, phi):
    e = exp.get('expect', {})
    legs, per = [], {'A': [], 'B': []}
    print(f"{'run':40s} arm  cold1  warm  post   warm v2/v3/v4   post v2/v3/v4   valid")
    for d in dirs:
        name = os.path.basename(d.rstrip('/'))
        arm = arm_of(d, exp)
        r = pace_run(d, lo, hi, plo, phi)
        print(f"{name:40s} {arm or '?':3s} {fmt(r['cold_ms'])} {fmt(r['warm_ms'])} {fmt(r['post_ms'])}   "
              f"{hist(r['warm']):14s}  {hist(r['post']):14s}  {len(r['good'])}/{len(r['marks'])}")
        if not exp:
            continue
        legs.append(('V', arm is not None, f'{name}: arm {arm} from request.json env {request(d).get("env")}'))
        legs.append(('V', perflog_of(d) == bool(exp.get('perflog')), f'{name}: perflog {perflog_of(d)}'))
        for ok, what in logs_ok(d, arm):
            legs.append(('V', ok, f'{name}: {what}'))
        legs.append(('V', len(r['marks']) >= e['V_min_marks'], f'{name}: {len(r["marks"])} marks'))
        legs.append(('V', len(r['good']) >= e['V_min_valid_starts'],
                     f'{name}: {len(r["good"])} valid starts >= {e["V_min_valid_starts"]}'
                     + ''.join(f'; dropped {k} ({v})' for k, v in r['bad'].items())))
        legs.append(('V', len(r['warm']) >= e['V_min_warm_lines'],
                     f'{name}: {len(r["warm"])} warm pace lines >= {e["V_min_warm_lines"]}'))
        fr = g11(d)
        want = [start_no(mk[1]) for mk in r['good'] if mk[1] != 'gameplay']
        miss = [n for n in want if n not in fr]
        legs.append(('V', not miss, f'{name}: g11 frames for {len(want) - len(miss)} of {len(want)} valid warm starts'
                     + (f', missing s{miss}' if miss else '') + ' (motion: by eye, NOTES.md)'))
        if arm:
            per[arm].append(r)
    if not exp:
        return 0
    for arm in ('A', 'B'):
        legs.append(('V', len(per[arm]) == exp.get('runs_per_arm', 2),
                     f'{arm}: {len(per[arm])} runs, registered {exp.get("runs_per_arm", 2)}'))
    m = {arm: {k: mean([r[k + '_ms'] for r in per[arm]]) for k in ('cold', 'warm', 'post')} for arm in ('A', 'B')}
    if any(m[a][k] is None for a in m for k in m[a]):
        for leg, ok, what in legs:
            print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
        print('VERDICT: VOID -- an arm has no pace lines in a window')
        return 2
    print(f"\nmean of runs   cold1  warm  post   (pooled warm v2/v3/v4)")
    for arm in ('A', 'B'):
        pool = [ln for r in per[arm] for ln in r['warm']]
        print(f"  {arm}           {fmt(m[arm]['cold'])} {fmt(m[arm]['warm'])} {fmt(m[arm]['post'])}   ({hist(pool)})")
    dw, dp = m['B']['warm'] - m['A']['warm'], m['B']['post'] - m['A']['post']
    legs.append(('P', dw <= e['P_d_max'],
                 f"warm countdown A {m['A']['warm']:.2f} B {m['B']['warm']:.2f}, B - A {dw:+.2f} ms <= {e['P_d_max']}"))
    legs.append(('T', m['B']['warm'] <= e['T_b_max'], f"warm countdown B {m['B']['warm']:.2f} ms <= {e['T_b_max']}"))
    legs.append(('G', dp <= e['G_d_max'],
                 f"post-GO warm A {m['A']['post']:.2f} B {m['B']['post']:.2f}, B - A {dp:+.2f} ms <= {e['G_d_max']}"))
    legs.append(('C', m['B']['cold'] <= m['A']['cold'] + e['C_d_max'],
                 f"cold start 1 A {m['A']['cold']:.2f} B {m['B']['cold']:.2f}, B - A "
                 f"{m['B']['cold'] - m['A']['cold']:+.2f} ms <= {e['C_d_max']}"))
    return verdict(legs)


def verdict(legs):
    for leg, ok, what in legs:
        print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
    if not all(ok for leg, ok, _ in legs if leg == 'V'):
        print('VERDICT: VOID -- a validity check failed')
        return 2
    rest = [ok for leg, ok, _ in legs if leg != 'V']
    print(f'VERDICT: {"PASS" if all(rest) else "FAIL"} -- {sum(rest)} of {len(rest)} checks hold '
          '(V also needs the moving car confirmed by eye)')
    return 0 if all(rest) else 1


def ft_judge(da, db, exp):
    import ftbuckets
    import ftpair
    ra, rb = ftpair.load(da), ftpair.load(db)
    if not ra or not rb:
        print(f'missing frametrace or marks: A {bool(ra)} B {bool(rb)}')
        return 2
    for name, _, lo, hi in ftpair.WINDOWS:
        ftpair.show(ftpair.account(ra[name]), ftpair.account(rb[name]),
                    f'{name}: frame end in mark{lo:+.1f} .. mark{hi:+.1f} s, all frames')
        ha = [r for r in ra[name] if (r.get('vb') or 0) >= 3]
        hb = [r for r in rb[name] if (r.get('vb') or 0) >= 3]
        ftpair.show(ftpair.account(ha), ftpair.account(hb), f'{name}: heavy frames (vb >= 3)')
        for k, d, r in (('A', da, ra), ('B', db, rb)):
            print(f' {k} {os.path.basename(d.rstrip("/"))}')
            print(ftbuckets.line('all', r[name]))
            print(ftbuckets.line('heavy', [f for f in r[name] if (f.get('vb') or 0) >= 3]))
    if not exp:
        return 0
    e = exp['expect']
    legs = []
    for k, d, r in (('A', da, ra), ('B', db, rb)):
        name = os.path.basename(d.rstrip('/'))
        arm = arm_of(d, exp)
        legs.append(('V', arm == k, f'{name}: arm {arm} from request.json env {request(d).get("env")}'))
        legs.append(('V', perflog_of(d) == bool(exp.get('perflog')), f'{name}: perflog {perflog_of(d)}'))
        for ok, what in logs_ok(d, arm):
            legs.append(('V', ok, f'{name}: {what}'))
        legs.append(('V', r['marks'] >= e['V_min_marks'], f'{name}: {r["marks"]} marks'))
        legs.append(('V', r['marks'] - len(r['bad']) >= e['V_min_valid_starts'],
                     f'{name}: {r["marks"] - len(r["bad"])} valid starts'
                     + ''.join(f'; dropped {m} ({v})' for m, v in r['bad'].items())))
        legs.append(('V', len(r['warm']) >= e['V_min_warm_frames'], f'{name}: {len(r["warm"])} warm frames'))
    wa, wb = ra['warm'], rb['warm']
    if not wa or not wb:
        print('VERDICT: VOID -- no warm frames on an arm')
        return 2
    la, lb = ftbuckets.ms(wa, lambda f: f['lockw']), ftbuckets.ms(wb, lambda f: f['lockw'])
    past = lambda f: ftbuckets.gbusy(f) > 2 * f['vbp']  # noqa: E731
    qa, qb = ftbuckets.pct(wa, past), ftbuckets.pct(wb, past)
    legs.append(('L', la >= e['L_a_min'] and lb <= e['L_b_max'],
                 f'warm lockw A {la:.2f} (>= {e["L_a_min"]}), B {lb:.2f} (<= {e["L_b_max"]}) ms/frame'))
    legs.append(('Q', qa >= e['Q_a_min'] and qb <= e['Q_b_max'],
                 f'warm frames with the guest busy past 2 VBLANKs: A {qa:.0f} % (>= {e["Q_a_min"]}), '
                 f'B {qb:.0f} % (<= {e["Q_b_max"]})'))
    print('\nJUDGE (' + exp.get('registered_utc', '?') + ')')
    return verdict(legs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--post', default='1.5,12')
    ap.add_argument('--expect')
    ap.add_argument('--ft', action='store_true', help='frametrace pair without a prediction')
    a = ap.parse_args()
    exp = json.load(open(a.expect)) if a.expect else {}
    if a.ft or exp.get('perflog'):
        if len(a.dirs) != 2:
            ap.error('a frametrace pair is two runs, A then B')
        return ft_judge(a.dirs[0], a.dirs[1], exp)
    lo, hi = (float(x) for x in a.window.split(','))
    plo, phi = (float(x) for x in a.post.split(','))
    return pace_judge(a.dirs, exp, lo, hi, plo, phi)


if __name__ == '__main__':
    sys.exit(main())
