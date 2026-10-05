#!/usr/bin/env python3
"""Read a frametrace capture (#433): per-title tables and a timeline.

    ftread.py <result dir> [...] [--all] [--delay 20] [--tsv timeline.tsv]
    ftread.py --pf <host capture dir>          (capture_simpsons_frametrace.sh)

A capture is the frame CSV (`frametrace_*.csv`, in <dir>/pulled/ for a
dispatcher result, in <dir>/ for a host capture) plus the logcat beside it.

THE WINDOW. Only frames inside the gameplay window count: from the route's
`mark gameplay` (run.log's `ROUTE hh:mm:ss mark gameplay`, or logcat's
`hakuX-route: mark gameplay`) plus --delay seconds, to the end of the frames.
No mark, no window: the capture is VOID unless --all is given (and then the
tables say ALL FRAMES, not gameplay). Frame times are mapped to wall clock by
the [hakuX-ft1] lines (rt_ms beside t_ms); without them, by hakuX-pace's
frame counter (f= at each line's logcat stamp; the trace's frame f is the
guest's frame f + 1).

What it prints per capture:
  1. pacemaker shares, all frames and late frames (the rule is profile.h's
     hakux_ft_attribute; the CSV's cls column is the device's verdict)
  2. GPU ms p50/p95 by GPU clock, and ms x MHz (flat if clock-limited)
  3. vCPU time per frame: run, guest work, guest idle, queue, blocked, and
     blocked by reason; lock waits by what the holder did; the PFIFO row
  4. hitches: periods over max(2 x the median of the previous 60 frames,
     50 ms), each with the frame record and its pacemaker
  5. VBLANKs per flip, the inferred interval, and slack to the deadline
"""
import argparse
import bisect
import csv
import glob
import gzip
import json
import os
import re
import statistics

CLS = ['vsync', 'run', 'bgpu', 'block', 'pgraph', 'gpu', 'rsub', 'unattr']
W = ['bql', 'pfl', 'pgl', 'halt', 'idle', 'fence', 'submit', 'rthr', 'dl', 'oth']
H = ['unk', 'run', 'gpu', 'rnd', 'idle', 'wait']
TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def pct(v, p):
    if not v:
        return float('nan')
    v = sorted(v)
    return v[min(len(v) - 1, int(round((len(v) - 1) * p / 100.0)))]


def find_files(d, pf):
    csvs = sorted(glob.glob(os.path.join(d, 'pulled', 'frametrace_*.csv')) +
                  glob.glob(os.path.join(d, 'frametrace_*.csv')) +
                  glob.glob(os.path.join(d, 'frames.csv.gz')))   # archive.py
    logs = [p for p in [os.path.join(d, 'ft-logcat.txt'),
                        os.path.join(d, 'logcat.txt'),
                        os.path.join(d, 'pf', 'logcat.txt'),
                        os.path.join(d, 'ft.log.gz')] if os.path.exists(p)]
    return csvs, logs


def opentext(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', errors='replace')
    return open(path, errors='replace')


def read_frames(path):
    rows = []
    for r in csv.DictReader(opentext(path)):
        f = {}
        for k, v in r.items():
            if k == 'cls':
                f[k] = v
            elif v == '' or v is None:
                f[k] = None
            else:
                try:
                    f[k] = int(v)
                except ValueError:
                    f[k] = v
        rows.append(f)
    return rows


def read_logs(logs, d):
    """Clock anchors, the gameplay mark, summaries, hitch blocks."""
    anchors = []            # (trace t_ms, wall secs-of-day) from [hakuX-ft1]
    pace = []               # (wall, guest frame count)
    mark = None
    marks = []
    summ, hitch = [], []
    for p in logs:
        for line in opentext(p):
            m = TS.match(line)
            if not m:
                continue
            wall = secs(*m.groups()[2:])
            if '[hakuX-ft1] n=' in line:
                rt = re.search(r' rt_ms=(\d+)', line)
                tm = re.search(r' t_ms=([\d.]+)', line)
                if tm:
                    anchors.append((float(tm.group(1)), wall))
                summ.append((wall, line.split('[hakuX-ft1] ', 1)[1].strip()))
            elif '[hakuX-ft] ' in line:
                hitch.append((wall, line.split('[hakuX-ft] ', 1)[1].strip()))
            elif 'hakuX-pace' in line:
                fm = re.search(r' f=(\d+)', line)
                if fm:
                    pace.append((wall, int(fm.group(1))))
            elif 'mark gameplay' in line and 'hakuX-route' in line:
                marks.append(wall)
    if marks:
        mark = marks[0]
    for rl in (os.path.join(d, 'run.log'), os.path.join(d, 'meta.md')):
        if os.path.exists(rl):
            mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', open(rl, errors='replace').read())
            if mk:
                mark = secs(*mk.groups())
                break
    return anchors, pace, mark, summ, hitch


def wall_of(frames, anchors, pace):
    """Wall clock (secs of day) per frame; method name."""
    if anchors:
        # trace ms -> wall: median offset over the anchors
        off = statistics.median(w - t / 1000.0 for t, w in anchors)
        for f in frames:
            f['wall'] = f['t_ns'] / 1e9 + off
        return 'ft1 anchors (%d)' % len(anchors)
    if pace:
        # hakuX-pace prints at the flip of guest frame f (= trace frame f - 1),
        # so each line gives one (trace t, wall) pair; take the median offset.
        by_f = {f['f']: f['t_ns'] for f in frames}
        offs = [w - by_f[g - 1] / 1e9 for w, g in pace if (g - 1) in by_f]
        if offs:
            off = statistics.median(offs)
            for f in frames:
                f['wall'] = f['t_ns'] / 1e9 + off
            return 'hakuX-pace frame counter (%d lines)' % len(offs)
    return None


def table(rows, head):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for r in rows:
        out.append('| ' + ' | '.join(str(x) for x in r) + ' |')
    return '\n'.join(out)


def ms(v):
    return '%.2f' % (v / 1000.0) if v == v else '-'


def mean(v):
    return sum(v) / len(v) if v else float('nan')


def report(d, a):
    csvs, logs = find_files(d, a.pf)
    name = os.path.basename(os.path.normpath(d))
    print('## %s\n' % name)
    if not csvs:
        print('VOID: no frametrace_*.csv\n')
        return None
    frames = []
    for p in csvs:
        frames += read_frames(p)
    anchors, pace, mark, summ, hitch = read_logs(logs, d)
    how = wall_of(frames, anchors, pace)
    title = ''
    rq = os.path.join(d, 'request.json')
    if os.path.exists(rq):
        j = json.load(open(rq))
        title = '%s, %s, ref %s, env %s' % (j.get('title'), j.get('device'),
                                          j.get('ref'), j.get('env'))
    print('capture: %s; %d frames in %s; clock: %s' %
          (title or d, len(frames), ', '.join(os.path.basename(c) for c in csvs), how))
    if mark is not None and how:
        t0 = mark + a.delay
        win = [f for f in frames if f['wall'] >= t0]
        print('window: mark gameplay %s + %d s -> %d frames (%.0f s)' %
              (fmt_t(mark), a.delay, len(win),
               (win[-1]['wall'] - win[0]['wall']) if win else 0))
    elif a.all:
        win = frames[1:]
        print('window: ALL FRAMES (--all; no gameplay mark) -> %d frames' % len(win))
    else:
        print('VOID: no `mark gameplay` (pass --all to read every frame, not as gameplay)\n')
        return None
    if len(win) < 30:
        print('VOID: %d frames in the window\n' % len(win))
        return None
    n = len(win)
    late = [f for f in win if f['late']]
    have = win[-1]['have']
    print('rows with schedstat: %s; guest idle hooked (G1): %s; VBLANK hooked (G6): %s\n' %
          ('/'.join(r for i, r in enumerate(['v', 'p', 'r', 'm']) if have & (1 << i)),
           'yes' if have & 16 else 'NO', 'yes' if have & 32 else 'no'))

    # 1. pacemakers
    rows = []
    for c in CLS:
        na = sum(1 for f in win if f['cls'] == c)
        nl = sum(1 for f in late if f['cls'] == c)
        if na or nl:
            rows.append([c, na, '%.1f%%' % (100.0 * na / n), nl,
                         '%.1f%%' % (100.0 * nl / len(late)) if late else '-'])
    print('### 1. Pacemaker (late = more VBLANKs than the guest asked for)\n')
    print(table(rows, ['class', 'frames', 'share', 'late frames', 'share of late']))
    P = [f['P'] for f in win]
    print('\nframes %d, late %d (%.1f%%); period p50 %s p95 %s p99 %s max %s ms; '
          'fps %.1f\n' % (n, len(late), 100.0 * len(late) / n, ms(pct(P, 50)),
                          ms(pct(P, 95)), ms(pct(P, 99)), ms(max(P)),
                          1e6 * n / sum(P)))

    # 2. GPU ms against the clock
    print('### 2. GPU execution against the GPU clock\n')
    by = {}
    for f in win:
        by.setdefault(f['mhz'], []).append(f['gpu'])
    rows = []
    for mhz in sorted(by):
        g = by[mhz]
        rows.append([mhz or '(unread)', len(g), ms(pct(g, 50)), ms(pct(g, 95)),
                     '%.0f' % (pct(g, 50) / 1000.0 * mhz) if mhz else '-'])
    print(table(rows, ['MHz', 'frames', 'GPU ms p50', 'GPU ms p95', 'p50 ms x MHz']))
    ks = [k for k in by if k]
    if len(ks) >= 2:
        lo, hi = min(ks), max(ks)
        glo, ghi = pct(by[lo], 50), pct(by[hi], 50)
        if glo > 0 and ghi > 0 and len(by[lo]) >= 30 and len(by[hi]) >= 30:
            import math
            e = math.log(glo / ghi) / math.log(hi / lo)
            print('\nelasticity of GPU ms to clock, %d -> %d MHz: %.2f '
                  '(1 = clock-limited, 0 = flat)' % (lo, hi, e))
    gall = [f['gpu'] for f in win]
    print('\nGPU busy share of the frame: p50 %.0f%%; frames with GPU >= 90%% of P: %d\n' %
          (100.0 * pct([f['gpu'] / max(1, f['P']) for f in win], 50),
           sum(1 for f in win if f['gpu'] * 10 >= f['P'] * 9)))

    # 3. vCPU and PFIFO time per frame
    print('### 3. Where the time went, ms per frame (mean; late frames in brackets)\n')

    def m(key, fr):
        v = [f[key] for f in fr if f.get(key) is not None and f[key] >= 0]
        return mean(v)

    def both(key):
        return '%s (%s)' % (ms(m(key, win)), ms(m(key, late)) if late else '-')

    rows = [['vCPU on-CPU', both('v_run')], ['vCPU run queue', both('v_rq')],
            ['vCPU blocked', both('v_blk')],
            ['guest idle (G1)', both('gidle') if have & 16 else 'not hooked']]
    for w in W:
        if any(f.get('v_' + w) for f in win):
            rows.append(['vCPU wait: ' + w, both('v_' + w)])
    rows.append(['DMA_PUT pfifo.lock wait (lock_wait_ns)', both('lockw')])
    for h in H:
        if any(f.get('vh_' + h) for f in win):
            rows.append(['vCPU lock waits, holder doing ' + h, both('vh_' + h)])
    for k, nm in [('vho_v', 'vCPU'), ('vho_p', 'PFIFO'), ('vho_r', 'render'),
                  ('vho_m', 'main loop'), ('vho_none', 'unknown')]:
        if any(f.get(k) for f in win):
            rows.append(['vCPU lock waits, held by ' + nm, both(k)])
    if any(f.get('nw_v') for f in win):
        rows.append(['vCPU waits per frame (count)',
                     '%.1f (%.1f)' % (m('nw_v', win), m('nw_v', late) if late else 0)])
    rows += [['PFIFO on-CPU', both('p_run')], ['PFIFO run queue', both('p_rq')],
             ['PFIFO blocked', both('p_blk')], ['PFIFO idle (waiting for work)', both('pidle')]]
    for w in W:
        if any(f.get('p_' + w) for f in win):
            rows.append(['PFIFO wait: ' + w, both('p_' + w)])
    if have & 4:
        rows += [['render on-CPU', both('r_run')], ['render blocked', both('r_blk')]]
    if have & 64:       # G9: the vCPU in MMIO dispatch (waits inside included)
        rows += [['vCPU in MMIO dispatch (G9)', both('mmio')],
                 ['MMIO accesses per frame', '%.0f' % m('nmmio', win)]]
    rows += [['main loop on-CPU', both('m_run')], ['GPU execution', both('gpu')],
             ['charged critical path (crit)', both('crit')],
             ['instrument (ins, us)', '%.1f' % m('ins', win)]]
    print(table(rows, ['', 'ms/frame']))
    print()

    # 4. hitches
    print('### 4. Hitches (period > max(2 x median of the previous 60 frames, 50 ms))\n')
    rows = []
    for i, f in enumerate(win):
        prev = [g['P'] for g in win[max(0, i - 60):i]]
        med = pct(prev, 50) if len(prev) >= 10 else 0
        thr = max(2 * med, 50000)
        if f['P'] > thr:
            rows.append([f['f'], fmt_t(f['wall']), ms(f['P']), f['vb'], f['cls'],
                         ms(f['v_run']), ms(f['v_blk']), ms(f['lockw']),
                         ms(f['p_run']), ms(f['p_blk']), ms(f['pidle']), ms(f['gpu']),
                         f['mhz']])
    if rows:
        print(table(rows, ['f', 'wall', 'P ms', 'vb', 'pacemaker', 'v run', 'v blk',
                           'lockw', 'p run', 'p blk', 'p idle', 'gpu', 'MHz']))
    else:
        print('none')
    hb = [h for h in hitch if h[1].startswith('B ')]
    print('\nhitch blocks on the log ([hakuX-ft] B lines): %d\n' % len(hb))

    # 5. deadline and delivery
    print('### 5. The guest\'s deadline against delivery\n')
    vb = {}
    for f in win:
        vb[min(f['vb'], 5)] = vb.get(min(f['vb'], 5), 0) + 1
    ireq = statistics.mode([f['ireq'] for f in win])
    print(table([[k if k < 5 else '5+', vb[k], '%.1f%%' % (100.0 * vb[k] / n)]
                 for k in sorted(vb)], ['VBLANKs per flip', 'frames', 'share']))
    sl = [f['slack'] for f in win if f.get('slack') is not None]
    print('\nguest interval inferred: %d VBLANK(s) (deadline %.1f ms)' %
          (ireq, ireq * statistics.median(f['vbp'] for f in win) / 1000.0))
    if sl:
        print('slack to the deadline, ms: p50 %s, p5 %s, min %s; frames with slack < 0: %d'
              % (ms(pct(sl, 50)), ms(pct(sl, 5)), ms(min(sl)), sum(1 for s in sl if s < 0)))
    print()
    if a.tsv:
        with open(a.tsv, 'w') as o:
            o.write('wall\tf\tP\tvb\tcls\tv_run\tv_blk\tlockw\tp_run\tp_blk\tpidle\tgpu\tmhz\n')
            for f in win:
                o.write('%.3f\t%d\t%d\t%d\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n' % (
                    f['wall'], f['f'], f['P'], f['vb'], f['cls'], f['v_run'], f['v_blk'],
                    f['lockw'], f['p_run'], f['p_blk'], f['pidle'], f['gpu'], f['mhz']))
    return win


def fmt_t(s):
    s = s % 86400
    return '%02d:%02d:%06.3f' % (s // 3600, (s % 3600) // 60, s % 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='*')
    ap.add_argument('--pf', action='append', default=[])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--delay', type=int, default=20)
    ap.add_argument('--tsv')
    a = ap.parse_args()
    for d in a.dirs + a.pf:
        report(d, a)


if __name__ == '__main__':
    main()
