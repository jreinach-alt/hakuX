#!/usr/bin/env python3
"""The 38-title Playable screen, ON (app default) vs OFF (pre-lane shipped
env), step 4 of lane.nfsdefault1011 (#433).

    screenread.py <run> [...] --expect docs/testing/predictions/nfsdefault1011-screen.json

Same binary, same env shape as nfsread.py/simpread.py (ON: no --env; OFF:
the three switches forced back to their pre-lane shipped values). Reuses
title_verdict.judge() the same way simpread.py does, instead of re-deriving
booted/crash/gfps from logcat by hand. There is no automated W/V leg here --
the brief's own screen column set is fatal, frames and gfps, read by eye
against each title's own OFF baseline (fastpaths1010's step 3 did the same,
no per-title numeric threshold works across 38 different titles). This
script's job is to surface the three columns in one table per batch, and to
flag the mechanical signals (crash, void, missing gfps) that make a title
worth a closer look -- not to pass/fail a title on its own.

Columns:
  fatal   crash or void from title_verdict.judge() (hang/abort/real exit
          inside the scored window). Not "failed the Playable fps/hitch
          bar" -- a short screen run is not a confirmation run, and is not
          judged against that bar.
  frames  count of captured frame files in the run dir (route `shot`
          captures or --frames-every), for a human to review by eye.
  gfps    g_fps_mean_reported_not_judged, the same raw reported figure
          fpread.py/simpread.py already read, not a judged/gated value.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'testing'))
import title_verdict as tv  # noqa: E402


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


def frame_count(d):
    return len(glob.glob(os.path.join(d, '*.png')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--expect')
    a = ap.parse_args()

    exp = json.load(open(a.expect)) if a.expect else {}
    off_env = exp.get('a_env') or []

    print(f"{'run':40s} arm  fatal  frames  gfps     title")
    rows = []
    for d in a.dirs:
        name = os.path.basename(d.rstrip('/'))
        req = request(d)
        title = req.get('title', '?')
        v = tv.judge(d, write_contact_sheet=False)
        arm = arm_of(d, off_env) if exp else None
        fatal = bool(v.get('crash')) or bool(v.get('void'))
        nframes = frame_count(d)
        gfps = v.get('g_fps_mean_reported_not_judged')
        rows.append((name, arm, fatal, nframes, gfps, title, v))
        print(f"{name:40s} {arm or '?':3s}  "
              f"{'YES' if fatal else 'no':5s}  {nframes:6d}  "
              f"{'   n/a' if gfps is None else f'{gfps:6.2f}'}  {title}")
        if fatal:
            print(f"    fatal detail: booted={v.get('booted')} "
                  f"reached_gameplay={v.get('reached_gameplay')} "
                  f"crash_detail={v.get('crash_detail')} void={v.get('void')}")

    if not exp:
        return 0

    fatal_titles = sorted({t for _, arm, fatal, _, _, t, _ in rows if arm == 'ON' and fatal})
    print()
    if fatal_titles:
        print(f"ON-only fatal in this batch: {fatal_titles}")
    else:
        print("No ON-only fatal in this batch (read frames/gfps by eye against OFF before calling a title pass).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
