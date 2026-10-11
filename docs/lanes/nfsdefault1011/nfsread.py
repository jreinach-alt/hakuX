#!/usr/bin/env python3
"""NFS Most Wanted race start, app default (ON: the three switches folded into
"Fast renderer paths" plus Submit frame buffering=3) vs the pre-lane shipped
behaviour (OFF: HAKUX_POSTED_PUT=0 HAKUX_LOCKFREE_WAKE=0 HAKUX_SUBMIT_FRAMES=2)
(#433, lane.nfsdefault1011).

    nfsread.py <run> [...] --expect docs/testing/predictions/nfsdefault1011-nfs.json
    nfsread.py <run> [...]                       per-run table only, no verdict

Same binary both arms (fastpaths1010's fpread.py pattern): ON queues with no
--env, so the app's own defaults (step 1 of this lane) reach native code. OFF
queues --env with every a_env entry, which xemu_android.cpp applies after
MainActivity's nativeSetenv calls and so overrides the defaults back to the
pre-lane shipped values. A run's arm is read from its request.json env: OFF
when it holds every a_env entry, ON when it holds none of them.

Pace parsing, windows and selection are raread.py's (docs/lanes/reportasync1010):
a `hakuX-pace` line counts for a start when its print time falls in
[mark+LO, mark+HI]; countdown -2..+1.5s is the default. A start whose route
input failed or hung (raread.bad_starts) is left out. A run's period over a
window is sum(ms) / (60 x lines); an arm's is the MEAN OF ITS RUNS' periods.

Legs:
  V  every run: >= V_min_marks marks, >= V_min_valid_starts valid starts, no
     input failed or hung before `mark gameplay`, each arm >= V_min_cold_lines
     cold pace lines, the run's arm read unambiguously from its env, and:
       ON  logs `[postput] on`, `[lockwake] on` and `submit frames: 3`
       OFF logs none of `[postput]`/`[lockwake]`, and `submit frames: 2`
  K  ON's cold start 1 period <= K_max ms (lockwake1011's own K bound).
  N  ON is not slower than OFF at the cold start: ON - OFF <= N_d_max ms.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reportasync1010'))
import raread  # noqa: E402

LOG_POSTPUT_ON = r'\[postput\] on'
LOG_POSTPUT_ANY = r'\[postput\]'
LOG_LOCKWAKE_ON = r'\[lockwake\] on'
LOG_LOCKWAKE_ANY = r'\[lockwake\]'
LOG_SUBMIT3 = r'submit frames: 3'
LOG_SUBMIT2 = r'submit frames: 2'


def request(d):
    try:
        return json.load(open(os.path.join(d, 'request.json')))
    except (OSError, ValueError):
        return {}


def arm_of(d, off_env):
    env = request(d).get('env') or []
    have = [x in env for x in off_env]
    if all(have):
        return 'OFF'
    if not any(have):
        return 'ON'
    return None


def logs_ok(d, arm):
    out = []
    if arm == 'ON':
        for rx, label in ((LOG_POSTPUT_ON, '[postput] on'), (LOG_LOCKWAKE_ON, '[lockwake] on'),
                           (LOG_SUBMIT3, 'submit frames: 3')):
            seen = raread.has_log(d, rx)
            out.append((seen, f'/{label}/ {"seen" if seen else "NOT seen"} on ON'))
    else:
        for rx, label in ((LOG_POSTPUT_ANY, '[postput]'), (LOG_LOCKWAKE_ANY, '[lockwake]')):
            seen = raread.has_log(d, rx)
            out.append((not seen, f'/{label}/ {"seen" if seen else "not seen"} on OFF'))
        seen = raread.has_log(d, LOG_SUBMIT2)
        out.append((seen, f'/submit frames: 2/ {"seen" if seen else "NOT seen"} on OFF'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--expect')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))

    exp = json.load(open(a.expect)) if a.expect else {}
    e = exp.get('expect', {})
    off_env = exp.get('a_env') or []

    legs = []
    arms = {'ON': {'cold': []}, 'OFF': {'cold': []}}
    print(f"{'run':40s} arm  cold1 (ms)  marks  valid")
    for d in a.dirs:
        name = os.path.basename(d.rstrip('/'))
        marks, pace, _, _ = raread.read(d)
        bad = raread.bad_starts(d)
        good = raread.valid(marks, bad)
        arm = arm_of(d, off_env) if exp else None
        cold = raread.sel(pace, good, lo, hi, 'cold')
        p = raread.period(cold)
        print(f"{name:40s} {arm or '?':3s}  {p if p is None else f'{p:7.2f}'}      "
              f"{len(marks):3d}   {len(good)}/{len(marks)}")
        if arm:
            arms[arm]['cold'] += cold
        if not exp:
            continue
        legs.append(('V', arm is not None, f'{name}: arm {arm} from request.json env {request(d).get("env")}'))
        for ok, what in logs_ok(d, arm) if arm else []:
            legs.append(('V', ok, f'{name}: {what}'))
        legs.append(('V', len(marks) >= e['V_min_marks'], f'{name}: {len(marks)} marks'))
        n_min = e.get('V_min_valid_starts', e['V_min_marks'])
        legs.append(('V', len(good) >= n_min,
                     f'{name}: {len(good)} valid starts >= {n_min}'
                     + ''.join(f'; dropped {k} ({v})' for k, v in bad.items())))
        legs.append(('V', 'gameplay' not in bad,
                     f'{name}: boot inputs went through before `mark gameplay`'
                     + (f' -- NO: {bad["gameplay"]}' if 'gameplay' in bad else '')))

    if not exp:
        return 0

    for arm in ('ON', 'OFF'):
        n = len(arms[arm]['cold'])
        legs.append(('V', n >= e['V_min_cold_lines'], f'{arm}: {n} cold pace lines'))

    c_on, c_off = raread.period(arms['ON']['cold']), raread.period(arms['OFF']['cold'])
    for leg, ok, what in legs:
        print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
    v_ok = all(ok for leg, ok, _ in legs if leg == 'V')
    if not v_ok:
        print('VERDICT: VOID -- a validity check failed')
        return 2
    if c_on is None or c_off is None:
        print('VERDICT: VOID -- an arm has no cold pace lines in the window')
        return 2

    rest = []
    k_ok = c_on <= e['K_max']
    rest.append(k_ok)
    print(f'  K {"PASS" if k_ok else "FAIL"}  ON cold {c_on:.2f} ms <= {e["K_max"]}')
    n_ok = c_on - c_off <= e['N_d_max']
    rest.append(n_ok)
    print(f'  N {"PASS" if n_ok else "FAIL"}  ON - OFF cold {c_on - c_off:+.2f} ms <= {e["N_d_max"]} '
          f'(ON {c_on:.2f}, OFF {c_off:.2f})')
    print(f'VERDICT: {"PASS" if all(rest) else "FAIL"} -- {sum(rest)} of {len(rest)} checks hold')
    return 0 if all(rest) else 1


if __name__ == '__main__':
    sys.exit(main())
