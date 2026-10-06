#!/usr/bin/env python3
"""Decompose frame time for a soak's scored window, from the always-on lines.

    decompose.py <result dir> [...] [--bar 28.5] [--tsv out.tsv] [--mark HH:MM:SS]

lane.fps20786 copy of docs/lanes/near30/decompose.py: --mark gives the
gameplay mark for a held run (pathfind) whose run.log has no ROUTE mark line.

Rows are the 2 s telemetry windows printed by the vCPU thread ([rr425w],
[tlb68], [idlehalt]) after `mark gameplay`. Each row gets the guest frame rate
of the same 2 s, read from the hakuX-pace frame counter (f= at each line's
logcat stamp, interpolated), and the renderer idle per frame (Ri, an EMA, from
the hakuX-perf gfps line nearest the row's end).

Per row, for one guest frame of length F = 1000/fps ms:
  guest busy   = F * busy_us / (idle_us + busy_us)      vCPU running guest code
  guest idle   = F - guest busy, split by the interrupt that ended each idle
                 stretch: vblank (0x33, PCRTC pending), pgraph (0x33, PGRAPH
                 pending), timer (0x30), disc (0x3e), other.
  renderer idle (Ri): the render thread waiting for the guest's next command.
So a slow frame with small guest idle and large Ri is the vCPU's (guest code);
small Ri and large guest idle woken by PGRAPH is the renderer's; large idle
woken by vblank or timer with large Ri is pacing (the guest waits on time).
"""
import argparse, json, os, re, statistics, bisect

ap = argparse.ArgumentParser()
ap.add_argument('dirs', nargs='+')
ap.add_argument('--bar', type=float, default=28.5)
ap.add_argument('--tsv')
ap.add_argument('--mark')
args = ap.parse_args()

TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def num(rx, s, d=None):
    m = re.search(rx, s)
    return float(m.group(1)) if m else d


def wake_class(key):
    vec, units = key.split('.')
    vec, units = int(vec, 16), int(units, 16)
    if vec == 0x33:
        if units & 4:
            return 'pgraph'
        if units & 2:
            return 'vblank'
        return 'gpu_other'
    return {0x30: 'timer', 0x3e: 'disc'}.get(vec, 'other')


CLASSES = ['vblank', 'pgraph', 'gpu_other', 'timer', 'disc', 'other']


def read_run(d):
    runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    if args.mark:
        mk = re.match(r'(\d+):(\d+):([\d.]+)', args.mark)
    if not mk:
        return None, 'no mark'
    mark = secs(*mk.groups())
    th = re.search(r'THERMAL: .*', runlog)
    pace, gf, rows, rdc = [], [], [], []
    tlb = {}
    ih = {}
    lk, ph, be = [], [], []
    rw = []
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        m = TS.match(line)
        if not m:
            continue
        t = secs(*m.groups()) - mark
        if 'hakuX-pace' in line:
            pace.append((t, num(r' f=(\d+)', line), num(r' ms=([\d.]+)', line),
                         num(r' v3=(\d+)', line, 0) + num(r' v4=(\d+)', line, 0),
                         num(r' max=([\d.]+)', line)))
        elif 'gfps=' in line:
            gf.append((t, num(r'Ri:([\d.]+)', line), num(r' D:([\d.]+)', line),
                       num(r' G:([\d.]+)', line)))
        elif '[rdc]' in line:
            dt, tc = num(r' dt=(\d+)', line), num(r' tcpu=([\d.]+)', line)
            if dt and tc is not None:
                rdc.append((t, tc / dt))
        elif '[idlehalt]' in line:
            sp = num(r'span_us=(\d+)', line)
            if sp:
                ih[num(r' w=(\d+)', line)] = (num(r'run_us=(\d+)', line) / sp,
                                               num(r'rq_us=(\d+)', line) / sp)
        elif '[rwait526] mode' in line:
            # rthr, rwait: the render thread's CPU and its deferred-wait time,
            # each as % of the line's span (thr_cpu_ms is "-" when unread).
            s_ = num(r' s=([\d.]+)', line)
            tc = num(r'thr_cpu_ms=([\d.]+)', line)
            wm = num(r'deferred calls=\d+ waits=\d+ spun=\d+ blocked=\d+ wakes=\d+ wait_ms=([\d.]+)', line)
            if s_ and tc is not None and wm is not None:
                rw.append((t, tc / (10 * s_), wm / (10 * s_)))
        elif '[lock474]' in line:
            dt = num(r'dt_ms=(\d+)', line)
            if dt:
                lk.append((t, (num(r'rd_wait_ms=([\d.]+)', line) + num(r'wr_wait_ms=([\d.]+)', line)) / dt))
        elif 'hakuX-phase' in line:
            ph.append((t, {k: num(r'\b' + k + r':([\d.]+)', line) for k in ('GPU', 'Draw', 'Fin', 'Idle', 'Tot', 'Surf', 'Tex')}))
        elif 'xemu-work' in line:
            be.append((t, num(r'BE:(\d+)', line)))
        elif '[tlb68]' in line:
            tlb[num(r' w=(\d+)', line)] = num(r' cpu=(\d+)', line) / num(r' dt=(\d+)', line)
        elif '[rr425w]' in line and t > 0:
            idle, busy = num(r'idle_us=(\d+)', line), num(r'busy_us=(\d+)', line)
            if not idle and not busy:
                continue
            r = {'t': t, 'w': num(r' w=(\d+)', line), 'idle': idle, 'busy': busy}
            for c in CLASSES:
                r[c] = 0.0
            for k, n, iu, bu in re.findall(r' ([0-9a-f]{2}\.[0-9a-f]{2}):(\d+):(\d+):(\d+):', line):
                r[wake_class(k)] += float(iu)
            rows.append(r)
    end = re.search(r'(\d+):(\d+):([\d.]+).*soak end', runlog)
    pt = [p[0] for p in pace]
    pf = [p[1] for p in pace]

    def frames_at(t):
        i = bisect.bisect_left(pt, t)
        if i == 0 or i >= len(pt):
            return None
        t0, t1, f0, f1 = pt[i - 1], pt[i], pf[i - 1], pf[i]
        if t1 - t0 > 10:        # a hang or a load: no frame rate inside it
            return None
        return f0 + (f1 - f0) * (t - t0) / (t1 - t0)

    gt = [g[0] for g in gf]
    rt = [x[0] for x in rdc]
    out = []
    for r in rows:
        a, b = frames_at(r['t'] - 2.0), frames_at(r['t'])
        if a is None or b is None or b <= a:
            continue
        fps = (b - a) / 2.0
        span = r['idle'] + r['busy']
        F = 1000.0 / fps
        r['fps'] = fps
        r['F'] = F
        r['gbusy'] = F * r['busy'] / span
        r['gidle'] = F - r['gbusy']
        for c in CLASSES:
            r[c + '_ms'] = F * r[c] / span
        i = bisect.bisect_right(gt, r['t']) - 1
        r['Ri'] = gf[i][1] if i >= 0 and r['t'] - gt[i] < 3 else None
        j = bisect.bisect_right(rt, r['t']) - 1
        r['rdc'] = rdc[j][1] if j >= 0 and r['t'] - rt[j] < 4 else None
        # fps20786: render thread on-CPU ms per guest frame, and the rest of
        # its non-idle time (F - Ri - rcpu): blocked, not waiting for the guest
        if r['rdc'] is not None:
            r['rcpu'] = F * r['rdc']
            if r['Ri'] is not None:
                r['rblk'] = F - r['Ri'] - r['rcpu']
        r['vcpu'] = tlb.get(r['w'])
        x = ih.get(r['w'])
        if x:
            r['v_run'] = F * x[0]
            r['v_rq'] = F * x[1]
            r['v_blk'] = F * (1 - x[0] - x[1])
        for src, key, fn in ((lk, 'lockw', lambda v: F * v),):
            j = bisect.bisect_right([y[0] for y in src], r['t']) - 1
            if j >= 0 and r['t'] - src[j][0] < 4:
                r[key] = fn(src[j][1])
        pts = [y for y in ph if r['t'] - 2 < y[0] <= r['t']]
        if pts:
            for k in ('GPU', 'Draw', 'Fin', 'Idle', 'Tot'):
                r['ph_' + k] = med([y[1][k] for y in pts])
        bs = [y[1] for y in be if r['t'] - 2 < y[0] <= r['t']]
        if bs:
            r['BE'] = med(bs)
        k = bisect.bisect_left([y[0] for y in rw], r['t'])
        if k < len(rw) and rw[k][0] - r['t'] < 10:
            r['rthr'] = rw[k][1]
            r['rwait'] = rw[k][2]
        out.append(r)
    return {'rows': out, 'thermal': th.group(0) if th else '', 'pace': pace}, None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else float('nan')


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float('nan')


COLS = ['n', 'fps', 'F', 'gbusy', 'gidle', 'vblank_ms', 'pgraph_ms', 'timer_ms',
        'disc_ms', 'other_ms', 'Ri', 'rcpu', 'rblk', 'v_run', 'v_rq', 'v_blk', 'vcpu', 'rthr', 'rwait', 'lockw', 'ph_GPU', 'ph_Draw', 'ph_Fin', 'ph_Idle', 'ph_Tot', 'BE']
tsv = open(args.tsv, 'w') if args.tsv else None
if tsv:
    tsv.write('run\tt\t' + '\t'.join(COLS[1:]) + '\n')
for d in args.dirs:
    name = os.path.basename(d.rstrip('/'))
    info, err = read_run(d)
    if err:
        print('==', name, 'VOID', err)
        continue
    rows = info['rows']
    print('== %s  rows=%d (2 s each)' % (name, len(rows)))
    print('   ' + info['thermal'][:300])
    ok = [r for r in rows if r['fps'] >= args.bar]
    lo = [r for r in rows if r['fps'] < args.bar]
    print('   at/above bar %d s, below %d s -> share %.2f' % (
        2 * len(ok), 2 * len(lo), len(ok) / max(1, len(rows))))
    print('   %-10s ' % 'group' + ' '.join('%8s' % c for c in COLS))
    groups = [('all', rows), ('>=bar', ok), ('<bar', lo),
              ('<bar p10', [r for r in lo if r['fps'] <= pct([x['fps'] for x in lo], 0.25)])]
    for g, rs in groups:
        if not rs:
            continue
        vals = [len(rs)] + [med([r.get(c) for r in rs]) for c in COLS[1:]]
        print('   %-10s ' % g + ' '.join('%8.2f' % v if isinstance(v, float) else '%8d' % v
                                           for v in vals))
    if tsv:
        for r in rows:
            tsv.write('%s\t%.1f\t' % (name, r['t']) + '\t'.join(
                '' if r.get(c) is None else '%.3f' % r[c] for c in COLS[1:]) + '\n')
