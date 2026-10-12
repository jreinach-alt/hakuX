#!/usr/bin/env python3
"""The Simpsons Hit & Run free roam fps A/B, ON (app default) vs OFF (pre-lane
shipped env), step 3 of lane.nfsdefault1011 (#433).

    simpread.py <run> [...] --expect docs/testing/predictions/nfsdefault1011-simpsons.json

Same binary, same env shape as nfsread.py (ON: no --env; OFF: the three
switches forced back to their pre-lane shipped values). Reuses
title_verdict.judge() for the scored window (`mark gameplay` .. `soak end`)
and hitch_report.position_change()'s moving-player check instead of
re-deriving fps/motion from logcat by hand -- this is the same machinery
pathfind's own Simpsons hold used (docs/lanes/pathfind/runs/
screen-simpsons-hit-run/hold/verdict.json's g_fps_mean_reported_not_judged
and position.first_last). Simpsons has no targets.toml entry, so judge()
runs against the bare defaults (playable_fps=30 etc); that is fine here,
this reader never calls its own fps/share bars, only the raw gfps figure.

Legs:
  B  basic validity, every run: booted, reached_gameplay, no crash, not
     void, and the run's arm read unambiguously from request.json's env.
  V  the player is moving in free roam: hitch_report.position_fail finds
     no "still" failure on the run's position_change() reading (first/last
     frame differ, most consecutive samples differ).
  W  ON's mean fps (mean of each run's g_fps_mean_reported_not_judged
     across the arm's runs) is at least OFF's mean minus W_d_max.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'testing'))
import title_verdict as tv  # noqa: E402
import hitch_report  # noqa: E402


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--expect')
    a = ap.parse_args()

    exp = json.load(open(a.expect)) if a.expect else {}
    e = exp.get('expect', {})
    off_env = exp.get('a_env') or []

    legs = []
    arms = {'ON': [], 'OFF': []}
    print(f"{'run':40s} arm  gfps    first_last  still_frac  booted  gameplay  crash  void")
    for d in a.dirs:
        name = os.path.basename(d.rstrip('/'))
        v = tv.judge(d, write_contact_sheet=False)
        arm = arm_of(d, off_env) if exp else None
        gfps = v.get('g_fps_mean_reported_not_judged')
        pos = v.get('position') or {}
        print(f"{name:40s} {arm or '?':3s}  "
              f"{'   n/a' if gfps is None else f'{gfps:6.2f}'}  "
              f"{pos.get('first_last')}      {pos.get('still_frac')}      "
              f"{v.get('booted')}  {v.get('reached_gameplay')}  {v.get('crash')}  {v.get('void')}")
        if arm and gfps is not None:
            arms[arm].append(gfps)
        if not exp:
            continue
        legs.append(('B', arm is not None, f'{name}: arm {arm} from request.json env {request(d).get("env")}'))
        legs.append(('B', bool(v.get('booted')), f'{name}: booted'))
        legs.append(('B', v.get('reached_gameplay') is True, f'{name}: reached_gameplay'))
        legs.append(('B', not v.get('crash'), f'{name}: no crash ({v.get("crash_detail")})'))
        legs.append(('B', not v.get('void'), f'{name}: not void ({v.get("void")})'))
        pfail, pwhy = hitch_report.position_fail(pos)
        legs.append(('V', not pfail, f'{name}: moving in free roam' + (f' -- NO: {pwhy}' if pfail else '')))

    if not exp:
        return 0

    for leg, ok, what in legs:
        print(f'  {leg} {"PASS" if ok else "FAIL"}  {what}')
    ok_so_far = all(ok for leg, ok, _ in legs if leg in ('B', 'V'))
    if not ok_so_far:
        print('VERDICT: VOID -- a basic-validity or moving-player check failed')
        return 2
    if not arms['ON'] or not arms['OFF']:
        print('VERDICT: VOID -- an arm has no gfps reading')
        return 2

    on_fps = sum(arms['ON']) / len(arms['ON'])
    off_fps = sum(arms['OFF']) / len(arms['OFF'])
    d_max = e.get('W_d_max', 1.0)
    w_ok = on_fps >= off_fps - d_max
    print(f'  W {"PASS" if w_ok else "FAIL"}  ON mean fps {on_fps:.2f} >= OFF mean fps {off_fps:.2f} - {d_max}')
    print(f'VERDICT: {"PASS" if w_ok else "FAIL"}')
    return 0 if w_ok else 1


if __name__ == '__main__':
    sys.exit(main())
