#!/usr/bin/env python3
"""The Playable-title screen for HAKUX_VTX_HAZARD (#433), ON vs OFF.

    scrread.py <run dir> [...]

One binary, env-only A/B: ON queues --env HAKUX_VTX_HAZARD=1, OFF queues no
env. The brief's columns, as fastpaths1010 read them:
  fatal     crash or void from title_verdict.judge().
  on-line   the value in logcat's "HAKUX_VTX_HAZARD=<v>" line (printed at the
            first vertex bind in both arms): 1 ON, 0 OFF, '-' if absent.
  finishes  the last "vtx_hazard: N finishes" count (ON only). 0 means the
            switch never acted: the ON run rendered as OFF does, and any
            difference from OFF is the run, not the fix.
  hdd       golden_status/state/loaded from result.json's hdd block, and '!'
            when hdd.after carries errors.
  gfps      g_fps_mean_reported_not_judged (reported, not judged).
  frames    route-frames/ plus frames/ stills, for reading by eye.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'testing'))
import title_verdict as tv  # noqa: E402

ON_RE = re.compile(r'HAKUX_VTX_HAZARD=(\d+) \(finish before')
FIN_RE = re.compile(r'vtx_hazard: (\d+) finishes')


def jload(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return {}


def lines(d):
    on, fin = None, 0
    try:
        with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
            for ln in f:
                m = ON_RE.search(ln)
                if m:
                    on = m.group(1)
                m = FIN_RE.search(ln)
                if m:
                    fin = int(m.group(1))
    except OSError:
        pass
    return on, fin


def main():
    dirs = sys.argv[1:]
    bad = [d for d in dirs if not os.path.isfile(os.path.join(d, 'request.json'))]
    if bad:
        sys.exit('not a run directory (no request.json): %s' % ', '.join(bad))
    print('%-44s %-3s %-5s %-4s %8s %-26s %6s %6s  %s' % (
        'run', 'arm', 'fatal', 'on', 'finishes', 'hdd', 'gfps', 'frames', 'title'))
    for d in dirs:
        req = jload(os.path.join(d, 'request.json'))
        res = jload(os.path.join(d, 'result.json'))
        arm = 'ON' if 'HAKUX_VTX_HAZARD=1' in (req.get('env') or []) else 'OFF'
        v = tv.judge(d, write_contact_sheet=False)
        fatal = bool(v.get('crash')) or bool(v.get('void'))
        on, fin = lines(d)
        h = res.get('hdd') or {}
        herr = (h.get('after') or {}).get('errors')
        hdd = '%s/%s/%s%s' % (h.get('golden_status'), h.get('state'), h.get('loaded'),
                              '!' if herr else '')
        n = (len(glob.glob(os.path.join(d, 'route-frames', '*.png'))) +
             len(glob.glob(os.path.join(d, 'frames', '*.png'))))
        g = v.get('g_fps_mean_reported_not_judged')
        print('%-44s %-3s %-5s %-4s %8d %-26s %6s %6d  %s' % (
            os.path.basename(d.rstrip('/'))[-44:], arm, 'YES' if fatal else 'no',
            on or '-', fin, hdd[:26], 'n/a' if g is None else '%.2f' % g, n,
            req.get('title', '?')))
        if fatal:
            print('    fatal: booted=%s gameplay=%s crash=%s void=%s' % (
                v.get('booted'), v.get('reached_gameplay'), v.get('crash_detail'),
                v.get('void')))
        if herr:
            print('    hdd errors: %s' % herr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
