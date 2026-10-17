#!/usr/bin/env python3
"""Judge the HAKUX_S2T_DRAIN arms on GTA III (#433): gta3drive1017-drive.json.

Committed before the arms' data exists. One build, env A/B: A has
HAKUX_S2T_DRAIN=1 (the #474 drain ahead of every surface-to-texture copy),
B has none (no drain ahead of a plain colour copy). Both carry
HAKUX_FRAMETRACE=1 HAKUX_FRAMETRACE_CSV=0 for the fence-wait column.

Per run, over the hakuX-pace windows (60 flips each) that start at or after
the route's `mark gameplay`, minus any --exclude spans (stretches the drive
shots show the car not moving: a crash into a wall, wasted, busted, a
cutscene), it prints:

  turnip       the first Turnip line, or NONE (the run does not count)
  switch       '[s2tdrain] on' / '[s2tdrain] first skip' present
  errors       Vulkan validation, device lost, hakuX-crash, Fatal signal lines
  windows      pace windows scored, and the seconds they cover
  share_t      share of the scored SECONDS in windows at >= 28.5 fps (the
               bar: a slow window lasts longer, so it weighs more)
  share_n      share of the scored windows at >= 28.5 fps
  fps50 fps10  median and 10th percentile of window fps
  p_fence      [hakuX-ft1] pw[5], PFIFO ms/frame in vkWaitForFences, median
  v_lock       [hakuX-ft1] vw[2], vCPU ms/frame waiting for pgraph.lock, median
  prun gpu50   [hakuX-ft1] PFIFO run ms/frame, GPU ms/frame, medians
  shots        each route frame: time, name, and the mean absolute RGB
               difference to the previous `drive` shot (0-255). A low value
               is a hint the car did not move; the frames are read by eye
               and that reading decides --exclude, not this number.

Then the legs of the prediction, each PASS/FAIL/VOID with its numbers.
--onfoot reads gta-3.route arms instead: only V and P4 apply.

Usage:
  drive_judge.py --a <dir> [--a <dir>] --b <dir> [--b <dir>]
                 [--exclude <result id>=HH:MM:SS-HH:MM:SS ...] [--onfoot]
"""
import argparse
import glob
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drive_split import ts, kv, pid_of, over  # noqa: E402

W_PGRAPH_LOCK, W_FENCE = 2, 5  # profile.h wait indices
BAR = 28.5
ERR = re.compile(r'VALIDATION|ValidationLayer|VK_ERROR_DEVICE_LOST|device lost|'
                 r'hakuX-crash|Fatal signal', re.I)


def hms(t):
    return datetime.fromtimestamp(t).strftime('%H:%M:%S')


def day_of(t, clock):
    """HH:MM:SS on the day of logcat time t, as an epoch."""
    d = datetime.fromtimestamp(t)
    h, m, s = (int(x) for x in clock.split(':'))
    return d.replace(hour=h, minute=m, second=s, microsecond=0).timestamp()


def shot_diffs(rdir):
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return [(os.path.basename(f), None) for f in
                sorted(glob.glob(os.path.join(rdir, 'route-frames', '*.png')))]
    out, prev = [], None
    for f in sorted(glob.glob(os.path.join(rdir, 'route-frames', '*.png'))):
        name = os.path.basename(f)
        diff = None
        if name.endswith('-drive.png'):
            im = Image.open(f).convert('RGB')
            if prev is not None and prev.size == im.size:
                diff = sum(ImageStat.Stat(ImageChops.difference(prev, im)).mean) / 3
            prev = im
        out.append((name, diff))
    return out


def read_run(rdir, excludes):
    lines = open(os.path.join(rdir, 'logcat.txt'), errors='replace').read().splitlines()
    pids = Counter(pid_of(l) for l in lines if 'hakuX-pace' in l)
    pid = pids.most_common(1)[0][0] if pids else None
    turnip = next((l.strip() for l in lines if 'GPU: PurpleVK' in l
                   or 'Loading custom Vulkan driver' in l
                   or ('[gpl569]' in l and 'mode=3' in l)), None)
    run = {'id': os.path.basename(rdir.rstrip('/')), 'turnip': turnip,
           'on': any('[s2tdrain] on' in l for l in lines),
           'skip': any('[s2tdrain] first skip' in l for l in lines),
           'errors': [l.strip() for l in lines if ERR.search(l)]}
    mark = None
    pace, ft1 = [], []
    for l in lines:
        t = ts(l)
        if t is None:
            continue
        if 'hakuX-route' in l and 'mark gameplay' in l and mark is None:
            mark = t
        if pid and '(' + pid + ')' not in l and '( ' + pid + ')' not in l:
            continue
        if 'hakuX-pace' in l and ' f=' in l:
            pace.append((t, kv(l.split('hakuX-pace', 1)[1])))
        elif '[hakuX-ft1]' in l and ' pw=' in l:
            body = l.split('[hakuX-ft1]', 1)[1]
            d = {k: v for k, v in kv(body).items() if k in ('prun', 'gpu50')}
            pw = re.search(r' pw=([\d.,]+)', body)
            vw = re.search(r' vw=([\d.,]+)', body)
            if pw:
                d['p_fence'] = float(pw.group(1).split(',')[W_FENCE])
            if vw:
                d['v_lock'] = float(vw.group(1).split(',')[W_PGRAPH_LOCK])
            ft1.append((t, d))
    run['mark'] = mark
    spans = []
    for e in excludes.get(run['id'], []):
        a, b = e.split('-')
        if pace:
            spans.append((day_of(pace[0][0], a), day_of(pace[0][0], b)))
    rows, prev_f = [], None
    for t, p in pace:
        f, ms = p.get('f'), p.get('ms', 0)
        nf = (f - prev_f) if prev_f is not None and f is not None else 60
        prev_f = f
        if ms <= 0 or nf <= 0:
            continue
        w0 = t - ms / 1e3
        if mark is None or w0 < mark:
            continue
        if any(w0 < s1 and t > s0 for s0, s1 in spans):
            continue
        r = {'t': t, 'dur': ms / 1e3, 'fps': 1000.0 * nf / ms}
        r.update(over(ft1, w0 - 0.5, t + 0.5))
        rows.append(r)
    run['rows'] = rows
    run['ft1_n'] = sum(1 for (t, _) in ft1 if mark and t >= mark)
    secs = sum(r['dur'] for r in rows)
    run['secs'] = secs
    run['share_t'] = sum(r['dur'] for r in rows if r['fps'] >= BAR) / secs if secs else None
    run['share_n'] = sum(1 for r in rows if r['fps'] >= BAR) / len(rows) if rows else None
    fps = sorted(r['fps'] for r in rows)
    run['fps50'] = statistics.median(fps) if fps else None
    run['fps10'] = fps[len(fps) // 10] if fps else None
    for k in ('p_fence', 'v_lock', 'prun', 'gpu50'):
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        run[k] = statistics.median(vals) if vals else None
    run['shots'] = shot_diffs(rdir)
    return run


def f1(v, fmt='%.1f'):
    return '-' if v is None else fmt % v


def show(arm, run):
    print('== %s %s' % (arm, run['id']))
    print('   turnip   %s' % (run['turnip'] or 'NONE -- does not count'))
    print('   switch   on=%s first_skip=%s' % (run['on'], run['skip']))
    print('   errors   %d%s' % (len(run['errors']),
                               ''.join('\n            ' + e for e in run['errors'][:5])))
    print('   mark     %s   windows %d (%.0f s)   ft1 lines after mark %d'
          % (hms(run['mark']) if run['mark'] else 'NONE', len(run['rows']), run['secs'],
             run['ft1_n']))
    print('   share_t %s  share_n %s  fps50 %s  fps10 %s'
          % (f1(run['share_t'], '%.3f'), f1(run['share_n'], '%.3f'), f1(run['fps50']),
             f1(run['fps10'])))
    print('   p_fence %s  v_lock %s  prun %s  gpu50 %s  (ms/frame, medians)'
          % (f1(run['p_fence']), f1(run['v_lock']), f1(run['prun']), f1(run['gpu50'])))
    for name, diff in run['shots']:
        print('   shot  %-28s %s' % (name, '' if diff is None else 'diff %.1f' % diff))


def verdict(name, ok, why):
    print('%-28s %s  %s' % (name, ok, why))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', action='append', default=[])
    ap.add_argument('--b', action='append', default=[])
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--onfoot', action='store_true')
    o = ap.parse_args()
    excludes = {}
    for e in o.exclude:
        rid, span = e.split('=', 1)
        excludes.setdefault(rid, []).append(span)
    A = [read_run(d, excludes) for d in o.a]
    B = [read_run(d, excludes) for d in o.b]
    for r in A:
        show('A', r)
    for r in B:
        show('B', r)
    print()

    # V: validity, per run
    void = []
    for arm, runs in (('A', A), ('B', B)):
        for r in runs:
            why = []
            if not r['turnip']:
                why.append('no Turnip line')
            if len(r['rows']) < 60:
                why.append('%d scored windows < 60' % len(r['rows']))
            if r['ft1_n'] < 60:
                why.append('%d ft1 lines after the mark < 60' % r['ft1_n'])
            if arm == 'A' and r['skip']:
                why.append('A printed first skip: the env did not reach it')
            if arm == 'B' and r['on']:
                why.append('B printed [s2tdrain] on: the env leaked into B')
            if arm == 'B' and not o.onfoot and not r['skip']:
                why.append('B never skipped a drain: the switch did not act')
            if why:
                void.append(r['id'])
            verdict('V %s %s' % (arm, r['id'][-6:]), 'VOID' if why else 'PASS',
                    '; '.join(why) or 'Turnip, switch as set, %d windows' % len(r['rows']))
    print('V (hand)                     the drive shots of every run, minutes apart, show the car '
          'moving through the city; stationary stretches go in --exclude')
    A = [r for r in A if r['id'] not in void]
    B = [r for r in B if r['id'] not in void]
    if not A or not B:
        print('NOT SCORED: an arm has no valid run')
        return

    def med(runs, k):
        vals = [r[k] for r in runs if r[k] is not None]
        return statistics.median(vals) if vals else None

    if o.onfoot:
        a50, b50 = med(A, 'fps50'), med(B, 'fps50')
        ash, bsh = med(A, 'share_t'), med(B, 'share_t')
        ok = b50 >= a50 - 0.5 and bsh >= ash - 0.05
        verdict('P4 on foot not regressed', 'PASS' if ok else 'FAIL',
                'fps50 B %.1f vs A %.1f (floor A-0.5); share_t B %.3f vs A %.3f (floor A-0.05)'
                % (b50, a50, bsh, ash))
        return

    a_fence = med(A, 'p_fence')
    a_share = max(r['share_t'] for r in A)
    p0 = a_fence is not None and a_fence >= 4.0 and a_share <= 0.80
    verdict('P0 premise (A)', 'PASS' if p0 else 'FAIL',
            'A p_fence %s ms/frame (floor 4.0), A best share_t %.3f (ceiling 0.80)%s'
            % (f1(a_fence), a_share, '' if p0 else ' -- the scene did not reproduce the dips; '
               'P2/P3 are not scored'))
    b_fence = med(B, 'p_fence')
    p1 = (b_fence is not None and a_fence is not None and b_fence <= 3.0
          and b_fence <= 0.4 * a_fence)
    verdict('P1 the fence wait falls', 'PASS' if p1 else 'FAIL',
            'B p_fence %s vs A %s ms/frame (ceiling 3.0 and 0.4 x A)' % (f1(b_fence), f1(a_fence)))
    if not p0:
        return
    b_min = min(r['share_t'] for r in B)
    p2 = b_min >= 0.90
    verdict('P2 the bar (every B run)', 'PASS' if p2 else 'FAIL',
            'B share_t %s (floor 0.90)' % ', '.join('%.3f' % r['share_t'] for r in B))
    a_max50 = max(r['fps50'] for r in A)
    b_min50 = min(r['fps50'] for r in B)
    p3 = b_min > a_share and b_min50 > a_max50
    verdict('P3 outside the spread', 'PASS' if p3 else 'FAIL',
            'B worst share_t %.3f > A best %.3f; B worst fps50 %.1f > A best %.1f'
            % (b_min, a_share, b_min50, a_max50))
    b_err = sum(len(r['errors']) for r in B)
    a_err = sum(len(r['errors']) for r in A)
    verdict('F no new errors (logcat)', 'PASS' if b_err <= a_err else 'FAIL',
            'B %d vs A %d error lines; the frames are read by eye for stale, torn or black '
            'textures in B only' % (b_err, a_err))
    if p1 and not p2:
        best = max(r['share_t'] for r in B)
        verdict('X the wait moved', 'FIRES' if best < 0.75 else 'no',
                'B best share_t %.3f (fires under 0.75 with P1 passing); B v_lock %s, '
                'prun %s, gpu50 %s' % (best, f1(med(B, 'v_lock')), f1(med(B, 'prun')),
                                       f1(med(B, 'gpu50'))))


if __name__ == '__main__':
    main()
