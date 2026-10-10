#!/usr/bin/env python3
"""NFS Most Wanted race start: frame period, VBLANK histogram and the report
trace, per run and pooled (#433, lane.reportasync1010).

    raread.py <result dir> [...] [--window LO,HI] [--post LO,HI] [--label X]

Reads logcat.txt. The route writes `hakuX-route: mark gameplay` (start 1, cold:
menus -> load -> race) and `mark go2` .. `mark go12` (warm restarts), each about
1.5 s before GO. Every 60 guest flips the build prints

  hakuX-pace  f=F v0=.. v1=.. v2=.. v3=.. v4=.. vb=.. max=.. ms=MS

MS is the wall time of those 60 flips (exact, not an EMA) and vK the flips
that took K VBLANKs (v4 = four or more). A pace line whose PRINT TIME falls in
[mark+LO, mark+HI] counts for that start. Default countdown window -2,1.5 (the
restart's OK is at mark-2.1, GO at mark+1.5), as phaseread.py
(docs/lanes/nfs30plan1010) selects it; post-GO window 1.5,12.

Period = sum(ms) / sum(60) over the selected lines, so a start with two lines
weighs twice. The histogram is the share of those flips in each vK.

With HAKUX_REPORT_TRACE=1 the build also prints, on hakuX-lane every 2 s,
`[rtrace] w ...` (reports.c rt_window_locked); those lines are summed over the
countdown + post-GO span of every start (mark+LO .. mark+post HI) and over the
whole run, into the step-1 table.

A start counts only if the route's inputs for it went through. run.log (the
host side of the route) is read for the span from the previous start's g11
shot to this start's mark: a `pad.sh ... failed` line, or an input (press,
axis) whose next route line comes more than INPUT_HUNG_S later (adb hung), and
the start is dropped from every table, with the reason printed. Pilot
1-1791656656 lost two starts that way (start 4: the restart's A never arrived,
the frame at g11 is the restart prompt; start 9: left-to-OK failed, the frame
is STANDINGS), and its countdown windows were menus. A failed screenshot does
not drop a start.

    raread.py <run> [...] --expect docs/testing/predictions/reportasync1010-nfs.json

judges the A/B: a run is ON when its request.json env holds every entry of the
prediction's b_env, OFF when it holds none of them, and the build's own log
lines (expect V_on_logs, default `[reportasync] on`) must be present on ON
and absent on OFF. Legs: V (every run has V_min_marks marks and at least
V_min_valid_starts valid starts, each arm >= V_min_warm_lines warm pace lines,
the label agrees), W (warm countdown period: off inside [W_off_min,
W_off_max], on <= W_on_max, on - off <= W_d_max), C (cold start 1: off inside
[C_off_min, C_off_max], on <= C_on_max), H (warm v2 share on - off >=
H_dv2_min points), and, when the prediction names P_on_max, P (post-GO warm
period, mark+1.5 .. mark+12: off inside [P_off_min, P_off_max], on <=
P_on_max).
"""
import argparse
import json
import os
import re
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
PACE = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) '
                  r'max=([\d.]+) ms=([\d.]+)')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
RTW = re.compile(r'\[rtrace\] w mode=(\w+) (.*)$')
ON = re.compile(r'\[reportasync\] on')
ROUTE = re.compile(r'^ROUTE (\d+):(\d+):([\d.]+) (.*)$')
INPUT_HUNG_S = 3.0

HIST = ['e', 'f', 'w', 'flip', 'next']
FOUR = ['fle', 'flw']
COUNTS = ['n', 'late', 'flipb4w', 'noflip', 'reuse', 'reuseb4w', 'armed', 'stchg', 'tsours']
EDGES = ['<0.25', '<0.5', '<1', '<2', '<4', '<8', '<16.7', '<33.3', '<66.7', '>=66.7']


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def parse_w(s):
    out = {}
    for tok in s.split():
        if '=' not in tok:
            continue
        k, v = tok.split('=', 1)
        if k in HIST or k in FOUR:
            out[k] = [int(x) for x in v.split(',')]
        elif k in ('gate', 'wait'):
            a, b = v.split('/')
            out[k] = (int(a), int(b))
        elif k in COUNTS:
            out[k] = int(v)
    return out


def bad_starts(d):
    """{mark name: reason} for starts whose route inputs did not go through."""
    try:
        lines = open(os.path.join(d, 'run.log'), errors='replace').read().splitlines()
    except OSError:
        return {}
    route = []
    for ln in lines:
        m = ROUTE.match(ln)
        if m:
            route.append((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), m.group(4)))
    bad, span = {}, []
    for i, (t, cmd) in enumerate(route):
        mk = re.match(r'mark (gameplay|go\d+)$', cmd)
        if mk:
            why = []
            for j, (tj, cj) in span:
                if 'failed' in cj.lower() and not cj.startswith('shot '):
                    why.append(cj)
                elif re.match(r'(press|axis) ', cj) and j + 1 < len(route) and route[j + 1][0] - tj > INPUT_HUNG_S:
                    why.append(f'{cj} took {route[j + 1][0] - tj:.1f} s')
            if why:
                bad[mk.group(1)] = '; '.join(why)
            span = []
            continue
        if re.match(r'shot s\d+-g11', cmd):
            span = []
            continue
        span.append((i, (t, cmd)))
    return bad


def read(d):
    marks, pace, rtw = [], [], []
    mode_on = False
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            if 'hakuX-route' in ln:
                k = MARK.search(ln)
                if k:
                    marks.append((t, k.group(1)))
                continue
            p = PACE.search(ln)
            if p:
                pace.append((t, [int(p.group(i)) for i in range(2, 7)], float(p.group(9))))
                continue
            if '[rtrace] w' in ln:
                w = RTW.search(ln)
                if w:
                    rtw.append((t, w.group(1), parse_w(w.group(2))))
                continue
            if ON.search(ln):
                mode_on = True
    return marks, pace, rtw, mode_on


def has_log(d, rx):
    r = re.compile(rx)
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        return any(r.search(ln) for ln in f)


def valid(marks, bad):
    return [mk for mk in marks if mk[1] not in bad]


def sel(evs, marks, lo, hi, which):
    out = []
    for t0, name in marks:
        if which == 'cold' and name != 'gameplay':
            continue
        if which == 'warm' and name == 'gameplay':
            continue
        out += [e for e in evs if t0 + lo <= e[0] <= t0 + hi]
    return out


def period(lines):
    return sum(x[2] for x in lines) / (60 * len(lines)) if lines else None


def vshare(lines, k):
    return 100 * sum(x[1][k] for x in lines) / (60 * len(lines)) if lines else None


def arm_of(d, b_env):
    """'on' if the run's env holds every b_env entry, 'off' if it holds none."""
    try:
        env = json.load(open(os.path.join(d, 'request.json'))).get('env') or []
    except (OSError, ValueError):
        return None
    have = [x in env for x in b_env]
    if all(have):
        return 'on'
    return 'off' if not any(have) else None


def judge(dirs, exp, lo, hi, plo, phi):
    e = exp['expect']
    b_env = exp.get('b_env') or ['HAKUX_REPORT_ASYNC=1']
    on_logs = e.get('V_on_logs') or [r'\[reportasync\] on']
    arms = {a: {'cold': [], 'warm': [], 'post': []} for a in ('on', 'off')}
    legs = []
    for d in dirs:
        marks, pace, _, _ = read(d)
        bad = bad_starts(d)
        good = valid(marks, bad)
        arm = arm_of(d, b_env)
        name = os.path.basename(d.rstrip('/'))
        for rx in on_logs:
            seen = has_log(d, rx)
            legs.append(('V', arm is not None and seen == (arm == 'on'),
                         f'{name}: arm {arm}, /{rx}/ {"seen" if seen else "not seen"}'))
        legs.append(('V', len(marks) >= e['V_min_marks'], f'{name}: {len(marks)} marks'))
        n_min = e.get('V_min_valid_starts', e['V_min_marks'])
        legs.append(('V', len(good) >= n_min,
                     f'{name}: {len(good)} valid starts >= {n_min}'
                     + ''.join(f'; dropped {k} ({v})' for k, v in bad.items())))
        if arm:
            arms[arm]['cold'] += sel(pace, good, lo, hi, 'cold')
            arms[arm]['warm'] += sel(pace, good, lo, hi, 'warm')
            arms[arm]['post'] += sel(pace, good, plo, phi, 'warm')
    for arm in ('off', 'on'):
        n = len(arms[arm]['warm'])
        legs.append(('V', n >= e['V_min_warm_lines'], f'{arm}: {n} warm pace lines'))
    w_off, w_on = period(arms['off']['warm']), period(arms['on']['warm'])
    c_off, c_on = period(arms['off']['cold']), period(arms['on']['cold'])
    p_off, p_on = period(arms['off']['post']), period(arms['on']['post'])
    v2_off, v2_on = vshare(arms['off']['warm'], 2), vshare(arms['on']['warm'], 2)
    if None in (w_off, w_on, c_off, c_on, v2_off, v2_on) or ('P_on_max' in e and None in (p_off, p_on)):
        print('VERDICT: VOID -- an arm has no pace lines in the window')
        return 2
    legs.append(('W', e['W_off_min'] <= w_off <= e['W_off_max'],
                 f'warm off {w_off:.1f} ms in [{e["W_off_min"]}, {e["W_off_max"]}]'))
    legs.append(('W', w_on <= e['W_on_max'], f'warm on {w_on:.1f} ms <= {e["W_on_max"]}'))
    legs.append(('W', w_on - w_off <= e['W_d_max'], f'warm on - off {w_on - w_off:+.1f} ms <= {e["W_d_max"]}'))
    legs.append(('C', e['C_off_min'] <= c_off <= e['C_off_max'],
                 f'cold off {c_off:.1f} ms in [{e["C_off_min"]}, {e["C_off_max"]}]'))
    legs.append(('C', c_on <= e['C_on_max'], f'cold on {c_on:.1f} ms <= {e["C_on_max"]}'))
    legs.append(('H', v2_on - v2_off >= e['H_dv2_min'],
                 f'warm v2 share {v2_off:.0f}% -> {v2_on:.0f}%, {v2_on - v2_off:+.1f} points >= {e["H_dv2_min"]}'))
    if 'P_on_max' in e:
        legs.append(('P', e['P_off_min'] <= p_off <= e['P_off_max'],
                     f'post-GO warm off {p_off:.1f} ms in [{e["P_off_min"]}, {e["P_off_max"]}]'))
        legs.append(('P', p_on <= e['P_on_max'], f'post-GO warm on {p_on:.1f} ms <= {e["P_on_max"]}'))
    for leg, ok, what in legs:
        print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
    v_ok = all(ok for leg, ok, _ in legs if leg == 'V')
    rest = [ok for leg, ok, _ in legs if leg != 'V']
    if not v_ok:
        print('VERDICT: VOID -- a validity check failed')
        return 2
    print(f'VERDICT: {"PASS" if all(rest) else "FAIL"} -- {sum(rest)} of {len(rest)} checks hold')
    return 0 if all(rest) else 1


def pace_line(lines):
    if not lines:
        return 'no pace lines'
    flips = 60 * len(lines)
    ms = sum(x[2] for x in lines) / flips
    v = [sum(x[1][k] for x in lines) for k in range(5)]
    share = ' '.join(f'v{k} {100 * v[k] / flips:.0f}%' for k in range(1, 5))
    return f'{ms:5.1f} ms/frame ({1000 / ms:4.1f} fps), {len(lines):2d} lines; {share}'


def add_w(acc, w):
    for k, v in w.items():
        if k in HIST or k in FOUR:
            a = acc.setdefault(k, [0] * len(v))
            for i, x in enumerate(v):
                a[i] += x
        elif k in ('gate', 'wait'):
            a = acc.setdefault(k, [0, 0])
            a[0] += v[0]
            a[1] += v[1]
        else:
            acc[k] = acc.get(k, 0) + v


def pct(a, b):
    return f'{100 * a / b:.1f}%' if b else '-'


def median_bucket(h):
    n = sum(h)
    if not n:
        return '-'
    c = 0
    for i, x in enumerate(h):
        c += x
        if c * 2 >= n:
            return EDGES[i]
    return EDGES[-1]


def trace_table(name, acc):
    n = acc.get('n', 0)
    if not n:
        print(f'  {name}: no [rtrace] records')
        return
    print(f'  {name}: {n} reports written')
    for k, label in (('e', 'queued -> handed off (finish)'), ('f', 'queued -> fence passed'),
                     ('w', 'queued -> written'), ('flip', 'queued -> next flip'),
                     ('next', 'queued -> next GET_REPORT, same offset')):
        h = acc.get(k, [0] * 10)
        tot = sum(h)
        cum, row = 0, []
        for i in range(len(h)):
            cum += h[i]
            row.append(f'{EDGES[i]} {pct(cum, tot)}')
        print(f'    {label:40s} n={tot:6d} median {median_bucket(h):7s} cum: ' + ', '.join(row[3:9]))
    fle, flw = acc.get('fle', [0] * 4), acc.get('flw', [0] * 4)
    print(f'    flips between queue and hand-off: 0 {pct(fle[0], n)}, 1 {pct(fle[1], n)}, 2 {pct(fle[2], n)}, '
          f'3+ {pct(fle[3], n)}')
    print(f'    flips between queue and write:    0 {pct(flw[0], n)}, 1 {pct(flw[1], n)}, 2 {pct(flw[2], n)}, '
          f'3+ {pct(flw[3], n)}')
    print(f'    written after a flip the hand-off preceded (late): {acc.get("late", 0)} = {pct(acc.get("late", 0), n)}')
    print(f'    next flip before the write (flipb4w): {acc.get("flipb4w", 0)} = {pct(acc.get("flipb4w", 0), n)}'
          f'  (no flip seen yet: {acc.get("noflip", 0)})')
    reuse = acc.get('reuse', 0)
    print(f'    offset reused: {reuse}; reused before the previous write landed: {acc.get("reuseb4w", 0)} '
          f'= {pct(acc.get("reuseb4w", 0), reuse)}')
    print(f'    status word nonzero at GET_REPORT (armed): {acc.get("armed", 0)}; changed between queue and write: '
          f'{acc.get("stchg", 0)}; previous value was ours (timestamp): {acc.get("tsours", 0)}')
    g, w = acc.get('gate', [0, 0]), acc.get('wait', [0, 0])
    print(f'    finishing thread: gate waits {g[0]} ({g[1] / 1000:.1f} ms total), report waits {w[0]} '
          f'({w[1] / 1000:.1f} ms total)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--post', default='1.5,12')
    ap.add_argument('--label', default='')
    ap.add_argument('--starts', action='store_true', help='one countdown and one post-GO line per start')
    ap.add_argument('--expect', help='judge the A/B against this registered prediction')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    plo, phi = (float(x) for x in a.post.split(','))
    if a.expect:
        return judge(a.dirs, json.load(open(a.expect)), lo, hi, plo, phi)
    print(f'countdown: pace lines printed in mark{lo:+.1f} .. mark{hi:+.1f} s; post-GO mark{plo:+.1f} .. '
          f'mark{phi:+.1f} s {a.label}')
    pool = {'cold': [], 'warm': [], 'post_cold': [], 'post_warm': []}
    tr_race, tr_all = {}, {}
    for d in a.dirs:
        marks, pace, rtw, on = read(d)
        name = os.path.basename(d.rstrip('/'))
        bad = bad_starts(d)
        print(f'{name}: {len(marks)} marks, async log {"seen" if on else "not seen"}, '
              f'{len(marks) - len(valid(marks, bad))} dropped')
        for k, v in bad.items():
            print(f'  dropped {k}: {v}')
        marks = valid(marks, bad)
        if not marks:
            continue
        if a.starts:
            for mk in marks:
                c, p = sel(pace, [mk], lo, hi, 'all'), sel(pace, [mk], plo, phi, 'all')
                print(f'    {mk[1]:9s} countdown {pace_line(c)}')
                print(f'    {"":9s} post-GO   {pace_line(p)}')
        rows = {'cold': sel(pace, marks, lo, hi, 'cold'), 'warm': sel(pace, marks, lo, hi, 'warm'),
                'post_cold': sel(pace, marks, plo, phi, 'cold'), 'post_warm': sel(pace, marks, plo, phi, 'warm')}
        for k in rows:
            pool[k] += rows[k]
            print(f'  {k:9s} {pace_line(rows[k])}')
        r1, r2 = {}, {}
        for t, mode, w in rtw:
            add_w(r2, w)
        for t, mode, w in sel(rtw, marks, lo, phi, 'all'):
            add_w(r1, w)
        add_w(tr_race, r1)
        add_w(tr_all, r2)
        if rtw:
            trace_table(f'trace, race starts ({rtw[0][1]})', r1)
    if len(a.dirs) > 1:
        print('POOLED:')
        for k in pool:
            print(f'  {k:9s} {pace_line(pool[k])}')
        trace_table('trace, race starts, pooled', tr_race)
        trace_table('trace, whole runs, pooled', tr_all)


if __name__ == '__main__':
    sys.exit(main())
