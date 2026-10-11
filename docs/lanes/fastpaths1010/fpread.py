#!/usr/bin/env python3
"""NFS Most Wanted race start, app default (fastpaths ON) vs HAKUX_*=0 (OFF) (#433, lane.fastpaths1010).

    fpread.py <run> [...] --expect docs/testing/predictions/fastpaths1010-nfs.json
    fpread.py <run> [...]                       per-run table only, no verdict

Both arms are the same binary (this lane's step-1 commit, which sets all six
switches ON by default from the app's "Fast renderer paths" setting). ON
queues with no --env at all, so the app's own default reaches native code;
OFF queues --env with each of the prediction's a_env entries (all six
switches set to "0"), which xemu_android.cpp applies after MainActivity's
own nativeSetenv calls and so overrides the default back off. A run's arm is
read from its request.json env: OFF when it holds every a_env entry, ON when
it holds none of them.

Pace parsing, windows and selection are raread.py's (docs/lanes/reportasync1010,
also used by ppread.py/texread.py): a `hakuX-pace` line counts for a start
when its print time falls in [mark+LO, mark+HI]; countdown -2..+1.5s is the
default (warm = go2..go12). A start whose route input failed or hung
(raread.bad_starts) is left out. A run's period over a window is sum(ms) /
(60 x lines); an arm's is the MEAN OF ITS RUNS' periods, so each run weighs
the same whatever its line count.

Legs:
  V  every run: >= V_min_marks marks, >= V_min_valid_starts valid starts, no
     input failed or hung before `mark gameplay`, each arm >= V_min_warm_lines
     warm pace lines, the run's arm read unambiguously from its env, and all
     four switch on-lines (LOGS_ON) present on every ON run and absent on
     every OFF run. Three of the six switches (HAKUX_UNI_BULK/UBERCACHE/
     FOGCACHE) share one combined log line, so this is four lines for six
     vars, not six.
  W  ON's warm countdown period <= W_on_max ms.
  D  OFF's warm countdown period - ON's >= D_min ms (OFF must be the slower
     arm by at least this much).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reportasync1010'))
import raread  # noqa: E402

LOGS_ON = [
    r'\[reportasync\] on',
    r'\[texscan\] on',
    r'\[drawrec1010\] drawrec=1 vtx=1 shc=1',
    r'\[perdraw433\] bulk=1 ubercache=1 fogcache=1',
]


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


def judge(dirs, exp, lo, hi):
    e = exp['expect']
    off_env = exp.get('a_env') or []
    legs = []
    arms = {'ON': {'warm': []}, 'OFF': {'warm': []}}
    for d in dirs:
        marks, pace, _, _ = raread.read(d)
        bad = raread.bad_starts(d)
        good = raread.valid(marks, bad)
        arm = arm_of(d, off_env)
        name = os.path.basename(d.rstrip('/'))
        for rx in LOGS_ON:
            seen = raread.has_log(d, rx)
            want = (arm == 'ON')
            legs.append(('V', arm is not None and seen == want,
                         f'{name}: arm {arm}, /{rx}/ {"seen" if seen else "not seen"}'))
        legs.append(('V', len(marks) >= e['V_min_marks'], f'{name}: {len(marks)} marks'))
        n_min = e.get('V_min_valid_starts', e['V_min_marks'])
        legs.append(('V', len(good) >= n_min,
                     f'{name}: {len(good)} valid starts >= {n_min}'
                     + ''.join(f'; dropped {k} ({v})' for k, v in bad.items())))
        if arm:
            arms[arm]['warm'] += raread.sel(pace, good, lo, hi, 'warm')
    for arm in ('ON', 'OFF'):
        n = len(arms[arm]['warm'])
        legs.append(('V', n >= e['V_min_warm_lines'], f'{arm}: {n} warm pace lines'))
    w_on = raread.period(arms['ON']['warm'])
    w_off = raread.period(arms['OFF']['warm'])
    if w_on is None or w_off is None:
        for leg, ok, what in legs:
            print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
        print('VERDICT: VOID -- an arm has no warm pace lines in the window')
        return 2
    legs.append(('W', w_on <= e['W_on_max'], f'ON warm {w_on:.2f} ms <= {e["W_on_max"]}'))
    legs.append(('D', w_off - w_on >= e['D_min'],
                 f'OFF - ON warm {w_off - w_on:+.2f} ms >= {e["D_min"]} (OFF {w_off:.2f}, ON {w_on:.2f})'))
    for leg, ok, what in legs:
        print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
    v_ok = all(ok for leg, ok, _ in legs if leg == 'V')
    rest = [ok for leg, ok, _ in legs if leg != 'V']
    if not v_ok:
        print('VERDICT: VOID -- a validity check failed')
        return 2
    print(f'VERDICT: {"PASS" if all(rest) else "FAIL"} -- {sum(rest)} of {len(rest)} checks hold')
    return 0 if all(rest) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--expect')
    ap.add_argument('--window', default='-2,1.5')
    args = ap.parse_args()
    lo, hi = (float(x) for x in args.window.split(','))
    if args.expect:
        exp = json.load(open(args.expect))
        sys.exit(judge(args.dirs, exp, lo, hi))
    for d in args.dirs:
        marks, pace, _, _ = raread.read(d)
        bad = raread.bad_starts(d)
        good = raread.valid(marks, bad)
        warm = raread.sel(pace, good, lo, hi, 'warm')
        print(os.path.basename(d.rstrip('/')), raread.period(warm))


if __name__ == '__main__':
    main()
