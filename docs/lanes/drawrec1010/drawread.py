#!/usr/bin/env python3
"""Judge HAKUX_DRAWREC=1 at the NFS Most Wanted race start (#433, lane.drawrec1010).

    drawread.py <result dir> [...] [--expect docs/testing/predictions/drawrec1010-nfs.json]
                [--window -2,1.5]

Each run's state comes from its request.json: HAKUX_DRAWREC=1 in `env` is ON,
anything else OFF. Plain and perflog runs may be mixed; the pace legs read the
plain runs only when there are plain runs in both states, the per-draw leg reads
the perflog runs only.

Windows are selected by PRINT TIME inside [mark+LO, mark+HI] for each
`hakuX-route: mark gameplay|goN`, as phaseread.py (docs/lanes/nfs30plan1010/)
does; the default -2,1.5 is the countdown. `gameplay` is the cold start (the
first race after the menus), go2..go12 the warm restarts.

  hakuX-pace  f=F v0= .. v4= ... ms=MS   F cumulative; MS = wall ms over the v0+..+v4 (60) flips
  hakuX-perf  [rdc] f=F ... vtx=calls/us/pages/hits ...   the vertex sync's TLB walks
  hakuX-phase ... Draw:.. [.. Syn:.. Pipe:..(.. Sh:..) Desc:.. .. Mfp:..] ...   perflog only
  xemu-work   BE:N                                N = draws in the last frame
  hakuX-stall [drawrec1010] drawrec=D vtx=V shc=S  once, when the switch is read
  hakuX-stall [drawrec] f=F vtx dirty= redo= redoKB= walks=FLIP+BUDGET runs= pages= shc=

Legs (the names in the prediction's `expect`):
  V  every run: 12 marks, no fatal signal, the switch line agrees with the
     request's env, at least V_min_pace countdown pace lines per state.
  R  [rdc] vtx walks per flip in the countdown, pooled per state: ON <=
     R_on_max, OFF >= R_off_min. The mechanism: the walks are deferred.
  U  perflog runs: Draw ms / draws per frame in the countdown, ON/OFF - 1 in
     [U_min, U_max]; ON's Syn <= U_syn_on_max ms/frame.
  P  plain runs, warm countdown: pace ms per frame ON - OFF in [P_min, P_max].
  H  plain runs, warm countdown: v2 share ON - OFF >= H_dv2_min points.
  T  the brief's targets, reported, not judged: warm ON <= T_warm_on_max,
     cold ON <= T_cold_on_max, v2 share up >= T_dv2_min points.
"""
import argparse
import json
import os
import re
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
PACE = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) .* ms=([\d.]+)')
RDC = re.compile(r'\[rdc\] f=(\d+) .* vtx=(\d+)/(\d+)/(\d+)/(\d+)')
PHASE = re.compile(r'hakuX-phase\(\s*\d+\): (.*) ms$')
WORK = re.compile(r'xemu-work\(\s*\d+\): BE:(\d+) ')
SWITCH = re.compile(r'\[drawrec1010\] drawrec=(\d) vtx=(\d) shc=(\d)')
DREC = re.compile(r'\[drawrec\] f=(\d+) vtx dirty=(\d+) redo=(\d+) redoKB=(\d+) walks=(\d+)\+(\d+) '
                  r'runs=(\d+) pages=(\d+) shc=(\d+)')
FATAL = re.compile(r'Fatal signal|FATAL EXCEPTION|Abort message')
FIELD = re.compile(r'([A-Za-z]+):(-?[\d.]+)')
PH = ['Draw', 'Syn', 'Pipe', 'Sh', 'Desc', 'Setup', 'Mfp']


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def read_run(d):
    req = json.load(open(os.path.join(d, 'request.json')))
    env = req.get('env') or []
    run = {'dir': d, 'name': os.path.basename(d), 'on': 'HAKUX_DRAWREC=1' in env,
           'perflog': str(req.get('perflog', '')).lower() == 'true',
           'marks': [], 'pace': [], 'rdc': [], 'phase': [], 'work': [], 'drec': [],
           'switch': None, 'fatal': 0, 'apk': ''}
    try:
        run['apk'] = json.load(open(os.path.join(d, 'result.json'))).get('apk_sha', '')
    except (OSError, ValueError):
        pass
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for ln in f:
            if FATAL.search(ln):
                run['fatal'] += 1
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            for key, rx in (('pace', PACE), ('rdc', RDC), ('drec', DREC), ('work', WORK)):
                q = rx.search(ln)
                if q:
                    run[key].append((t,) + tuple(float(x) for x in q.groups()))
                    break
            else:
                q = MARK.search(ln)
                if q:
                    run['marks'].append((t, q.group(1)))
                    continue
                q = PHASE.search(ln)
                if q:
                    vals = {}
                    for fm in FIELD.finditer(q.group(1)):
                        vals.setdefault(fm.group(1), float(fm.group(2)))
                    run['phase'].append((t, vals))
                    continue
                q = SWITCH.search(ln)
                if q and run['switch'] is None:
                    run['switch'] = tuple(int(x) for x in q.groups())
    return run


def windows(run, lo, hi, which):
    """Events of each kind printed inside the countdown windows of the chosen starts."""
    out = {k: [] for k in ('pace', 'rdc', 'phase', 'work')}
    for mt, name in run['marks']:
        if which == 'cold' and name != 'gameplay':
            continue
        if which == 'warm' and name == 'gameplay':
            continue
        for k in out:
            out[k] += [e for e in run[k] if mt + lo <= e[0] <= mt + hi]
    return out


def pace_stats(pace):
    """f= on the pace line is cumulative; the window's flips are v0+..+v4 (60)."""
    v = [sum(p[2 + i] for p in pace) for i in range(5)]
    n = sum(v) or 1
    return {'n': len(pace), 'ms': mean([p[7] / (sum(p[2:7]) or 1) for p in pace]),
            'v2': 100.0 * v[2] / n, 'v3': 100.0 * v[3] / n, 'v4+': 100.0 * v[4] / n, 'flips': sum(v)}


def rdc_stats(rdc):
    f = sum(r[1] for r in rdc) or float('nan')
    return {'n': len(rdc), 'walks': sum(r[2] for r in rdc) / f, 'us': sum(r[3] for r in rdc) / f,
            'hits': sum(r[5] for r in rdc) / f}


def phase_stats(ph, work):
    be = mean([w[1] for w in work])
    vals = {k: mean([p[1].get(k, 0.0) for p in ph]) for k in PH}
    vals['n'] = len(ph)
    vals['draws'] = be
    vals['us_draw'] = 1000.0 * vals['Draw'] / be if be == be and be else float('nan')
    return vals


def drec_stats(run):
    if not run['marks']:
        return None
    t0 = run['marks'][0][0]
    rows = [r for r in run['drec'] if r[0] >= t0]
    f = sum(r[1] for r in rows)
    if not f:
        return None
    s = [sum(r[i] for r in rows) / f for i in range(2, 10)]
    return dict(zip(('dirty', 'redo', 'redoKB', 'wflip', 'wbudget', 'runs', 'pages', 'shc'), s), n=len(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--expect')
    ap.add_argument('--window', default='-2,1.5')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    exp = json.load(open(a.expect)).get('expect', {}) if a.expect else {}
    runs = [read_run(d) for d in a.dirs]
    verdict = {}

    print(f"window: print time in mark{lo:+.1f} .. mark{hi:+.1f} s")
    print(f"{'run':44s} {'state':5s} {'build':7s} {'apk':12s} marks fatal switch")
    v_ok = True
    for r in runs:
        sw = r['switch']
        sw_ok = sw is not None and bool(sw[0]) == r['on'] and (not r['on'] or (sw[1] and sw[2]))
        ok = len(r['marks']) >= exp.get('V_marks', 12) and r['fatal'] == 0 and sw_ok
        v_ok &= ok
        print(f"{r['name']:44s} {'ON' if r['on'] else 'off':5s} {'perflog' if r['perflog'] else 'plain':7s} "
              f"{r['apk']:12s} {len(r['marks']):5d} {r['fatal']:5d} {sw}  {'ok' if ok else 'VOID'}")

    def pooled(state, perflog, which):
        sel = [r for r in runs if r['on'] == state and (perflog is None or r['perflog'] == perflog)]
        out = {k: [] for k in ('pace', 'rdc', 'phase', 'work')}
        for r in sel:
            w = windows(r, lo, hi, which)
            for k in out:
                out[k] += w[k]
        return sel, out

    print("\nCountdown, pooled per state")
    have_plain = all(any(r['on'] == s and not r['perflog'] for r in runs) for s in (True, False))
    pace_build = False if have_plain else None
    res = {}
    for state in (False, True):
        for which in ('cold', 'warm'):
            sel, w = pooled(state, pace_build, which)
            ps = pace_stats(w['pace'])
            _, wa = pooled(state, None, which)
            rs = rdc_stats(wa['rdc'])
            res[(state, which)] = (ps, rs)
            print(f"  {'ON ' if state else 'off'} {which}: runs {len(sel)} ({'plain' if have_plain else 'all'}), "
                  f"pace lines {ps['n']}: {ps['ms']:.1f} ms/frame, v2 {ps['v2']:.1f}% v3 {ps['v3']:.1f}% "
                  f"v4+ {ps['v4+']:.1f}% | [rdc] vtx (all runs, n={rs['n']}): {rs['walks']:.1f} walks/flip, "
                  f"{rs['us'] / 1000:.2f} ms/flip, {rs['hits']:.1f} re-armed/flip")
        n_pace = sum(res[(state, w)][0]['n'] for w in ('cold', 'warm'))
        if n_pace < exp.get('V_min_pace', 15):
            v_ok = False
            print(f"  VOID: {n_pace} countdown pace lines for {'ON' if state else 'off'}")
    verdict['V'] = v_ok

    perf = {}
    for state in (False, True):
        sel, w = pooled(state, True, 'all')
        if sel and w['phase']:
            perf[state] = phase_stats(w['phase'], w['work'])
            p = perf[state]
            print(f"  {'ON ' if state else 'off'} perflog ({len(sel)} runs, {p['n']} phase samples): draws/frame "
                  f"{p['draws']:.0f}, {p['us_draw']:.2f} us/draw | " +
                  ' '.join(f"{k} {p[k]:.2f}" for k in PH))

    print("\n[drawrec] counters, ON runs, from the first mark on, per flip")
    for r in runs:
        if r['on']:
            s = drec_stats(r)
            if s:
                print(f"  {r['name']}: dirty {s['dirty']:.1f} redo {s['redo']:.1f} ({s['redoKB']:.0f} KB) walks "
                      f"{s['wflip']:.2f}+{s['wbudget']:.2f} runs {s['runs']:.1f} pages {s['pages']:.0f} "
                      f"shc {s['shc']:.1f}  (n={s['n']})")
            else:
                print(f"  {r['name']}: no [drawrec] line after the first mark")

    print("\nLegs")

    def leg(name, ok, text):
        verdict[name] = ok
        print(f"  {name}: {'PASS' if ok else ('SKIP' if ok is None else 'FAIL')}  {text}")

    leg('V', v_ok, 'marks, no fatal, switch line matches env, enough pace lines')
    off_w = rdc_stats(pooled(False, None, 'all')[1]['rdc'])['walks']
    on_w = rdc_stats(pooled(True, None, 'all')[1]['rdc'])['walks']
    leg('R', on_w <= exp.get('R_on_max', 20) and off_w >= exp.get('R_off_min', 100),
        f"[rdc] vtx walks/flip: off {off_w:.1f} (>= {exp.get('R_off_min', 100)}), "
        f"ON {on_w:.1f} (<= {exp.get('R_on_max', 20)})")
    if False in perf and True in perf:
        d = perf[True]['us_draw'] / perf[False]['us_draw'] - 1
        ok = exp.get('U_min', -0.40) <= d <= exp.get('U_max', -0.20) and perf[True]['Syn'] <= exp.get('U_syn_on_max', 1.5)
        leg('U', ok, f"us/draw off {perf[False]['us_draw']:.2f} ON {perf[True]['us_draw']:.2f} ({100 * d:+.1f}%, "
            f"in [{100 * exp.get('U_min', -0.40):+.0f}, {100 * exp.get('U_max', -0.20):+.0f}]%); "
            f"Syn off {perf[False]['Syn']:.2f} ON {perf[True]['Syn']:.2f} (<= {exp.get('U_syn_on_max', 1.5)})")
    else:
        leg('U', None, 'no perflog run in both states')
    off, on = res[(False, 'warm')][0], res[(True, 'warm')][0]
    dp, dv2 = on['ms'] - off['ms'], on['v2'] - off['v2']
    leg('P', exp.get('P_min', -6.0) <= dp <= exp.get('P_max', -1.0),
        f"warm countdown pace off {off['ms']:.1f} ON {on['ms']:.1f} ms/frame: {dp:+.1f} "
        f"(in [{exp.get('P_min', -6.0)}, {exp.get('P_max', -1.0)}])")
    leg('H', dv2 >= exp.get('H_dv2_min', 5.0),
        f"warm v2 share off {off['v2']:.1f}% ON {on['v2']:.1f}%: {dv2:+.1f} points (>= {exp.get('H_dv2_min', 5.0)})")
    cold_on = res[(True, 'cold')][0]
    print(f"  T (brief's targets, not judged): warm ON {on['ms']:.1f} <= {exp.get('T_warm_on_max', 38)}: "
          f"{'met' if on['ms'] <= exp.get('T_warm_on_max', 38) else 'not met'}; cold ON {cold_on['ms']:.1f} "
          f"(n={cold_on['n']}) <= {exp.get('T_cold_on_max', 52)}: "
          f"{'met' if cold_on['ms'] <= exp.get('T_cold_on_max', 52) else 'not met'}; v2 {dv2:+.1f} >= "
          f"{exp.get('T_dv2_min', 10)}: {'met' if dv2 >= exp.get('T_dv2_min', 10) else 'not met'}")
    judged = [v for v in verdict.values() if v is not None]
    print(f"\nVERDICT: {'CONFIRMED' if v_ok and all(judged) else ('VOID' if not v_ok else 'REFUTED')} "
          f"({', '.join(k + '=' + ('skip' if v is None else 'pass' if v else 'FAIL') for k, v in verdict.items())})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
