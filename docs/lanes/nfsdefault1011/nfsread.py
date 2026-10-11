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
     cold pace lines, the run's arm read unambiguously from its env, every
     start's `sN-g11.png` frame shows the race HUD (hud_bad_starts, below),
     and:
       ON  logs `[postput] on`, `[lockwake] on` and `submit frames: 3`
       OFF logs none of `[postput]`/`[lockwake]`, and draw.c's own
           `[coldstart1010] submit_frames=2 (HAKUX_SUBMIT_FRAMES; pref 3)`
           (xemu_android.cpp's `submit frames: %d` logs the pref fed into
           xemu_set_submit_frames, not the value draw.c runs with once the
           env var overrides it, so it stays "3" on OFF too -- not useful
           as OFF's proof)
  K  ON's cold start 1 period <= K_max ms (lockwake1011's own K bound).
  N  ON is not slower than OFF at the cold start: ON - OFF <= N_d_max ms.

raread.bad_starts only drops a start when run.log shows a failed or hung
route input; it has no way to see the route reach the wrong screen when
every input it sent still "succeeded" (lane.local, 2026-10-11: the open-loop
first-run route desynced on both of batch 2's runs -- 87617 lost two HATX
taps and landed on an autosave dialog then, later, the name-entry keyboard;
87778 never left the keyboard at all -- yet marks=12, valid=12/12, no
run.log failures, because every pad.sh input it tried did return). The two
runs are not evidence either way: hud_bad_starts below reads each start's
`sN-g11.png` route-frames screenshot and drops it when the race HUD's
speedometer dial is not where the race always puts it, which is visible even
when the frame is otherwise a plausible-looking 3D scene (attract-mode demo
footage, 87617's starts 1 and 12). This is scoped to this reader, not
raread.py: it is a property of NFS MW's screens and this lane's open-loop
route, not of the pace/mark protocol every other lane's reader shares.
nfsroute1011 is building a screen-gated version of this route; once it lands
this check should still hold as a second opinion, but the route should stop
producing frames that need it caught after the fact.
"""
import argparse
import glob
import json
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reportasync1010'))
import raread  # noqa: E402

# The speedometer dial (bottom-right HUD) is a near-black disc ringed in
# orange, present in every known-good sN-g11.png and absent from both a
# dialog/menu frame (all-black background, high fraction) and attract-mode
# demo footage of the same track (no HUD at all, near-zero fraction).
# Measured across the two pilot runs' 24 frames: black_frac in [0.056,
# 0.526]; measured on the two desynced batch-2 runs: 0.017-0.805, including
# values the pilot runs never produced on any of their 24 starts.
HUD_BOX = (0.68, 0.60, 0.95, 0.95)
HUD_LO, HUD_HI = 0.05, 0.55
GO = re.compile(r'^go(\d+)$')

LOG_POSTPUT_ON = r'\[postput\] on'
LOG_POSTPUT_ANY = r'\[postput\]'
LOG_LOCKWAKE_ON = r'\[lockwake\] on'
LOG_LOCKWAKE_ANY = r'\[lockwake\]'
LOG_SUBMIT3 = r'submit frames: 3'
# xemu_android.cpp's "submit frames: %d" always logs the *pref* passed into
# xemu_set_submit_frames, not the value draw.c runs with once HAKUX_SUBMIT_FRAMES
# overrides it (confirmed on OFF1: pref logs 3, draw.c's own line below logs the
# actual 2). draw.c's "[coldstart1010] submit_frames=N (HAKUX_SUBMIT_FRAMES;
# pref M)" line is the one that reflects what the engine actually ran with.
LOG_SUBMIT2 = r'\[coldstart1010\] submit_frames=2 \(HAKUX_SUBMIT_FRAMES'


def mark_num(name):
    if name == 'gameplay':
        return 1
    m = GO.match(name)
    return int(m.group(1)) if m else None


def hud_frac(path):
    """Fraction of near-black pixels in the speedometer dial's HUD box."""
    im = Image.open(path).convert('RGB')
    w, h = im.size
    x0, y0, x1, y1 = HUD_BOX
    spd = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    px = spd.load()
    sw, sh = spd.size
    n = black = 0
    for y in range(0, sh, 2):
        for x in range(0, sw, 2):
            r, g, b = px[x, y]
            if r < 35 and g < 35 and b < 35:
                black += 1
            n += 1
    return black / n if n else None


def hud_bad_starts(d, marks):
    """{mark name: reason}, a start whose sN-g11.png frame does not show the
    race HUD's speedometer dial (the route reached the wrong screen even
    though its inputs all reported success -- see module docstring)."""
    bad = {}
    for _, name in marks:
        n = mark_num(name)
        if n is None:
            continue
        hits = sorted(glob.glob(os.path.join(d, 'route-frames', f'*-s{n}-g11.png')))
        if not hits:
            continue
        frac = hud_frac(hits[0])
        if frac is not None and not (HUD_LO <= frac <= HUD_HI):
            bad[name] = (f'no speedometer HUD in {os.path.basename(hits[0])} '
                         f'(black frac {frac:.3f} outside [{HUD_LO}, {HUD_HI}])')
    return bad


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
        for k, v in hud_bad_starts(d, marks).items():
            bad[k] = f'{bad[k]}; {v}' if k in bad else v
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
