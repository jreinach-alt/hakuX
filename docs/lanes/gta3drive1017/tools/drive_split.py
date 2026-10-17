#!/usr/bin/env python3
"""Where the PFIFO thread's blocked time goes while GTA III drives (#433).

Question: in the driving windows under 28.5 fps, which wait fills the
~28 ms per flip the owner's capture shows as PFIFO blocked (section 3)?
Committed before the pilot's data arrives; reads one dispatch result dir.

Per 60-flip `hakuX-pace` window after the logcat's `mark gameplay`:

  always on (any build)
    fps          60 / (pace ms / 1000)
    Ri, Tq       hakuX-perf gfps line: PFIFO park ms/flip (EWMA), dirty queries
    pf_cpu       [rdc] tcpu / f        PFIFO thread CPU ms per flip
    pf_blk       period - Ri - pf_cpu  neither parked nor on a CPU
    drain50      fifoskew drain p50 ms (submission waiting on the PFIFO thread;
                 51.25 is the overflow bin; the mean is not used: lost-track
                 outliers of tens of seconds dominate it). '-' when the FIFO
                 never drained in the window (n=0).
  perflog build (NV2A_PERF_LOG) only
    fin, fin_*   hakuX-stall Finish per 60 frames, by cause (vtx sc sd buf fb
                 pres flip flu stl)
    ph_draw, ph_fin, ph_sub, ph_fen, ph_idle   hakuX-phase ms per frame
    gpu, gpu_r, gpu_x                          hakuX-phase GPU ms per frame
    lw           hakuX-cpu Lw (lock wait)
    txdl         hakuX-stall txr dl count / txdl[...] reasons
  HAKUX_FRAMETRACE=1 only (hakuX-lane [hakuX-ft1], ~20 frames a line)
    prun, pblk, pidle   PFIFO thread run / blocked / idle ms per frame
    fw1          the top fence/submit wait site, ms per frame / count
    gpu50        GPU ms per frame, median
  cblat         fin and mdraw ms per flip (cblat split, always on)
  hz            HAKUX_VTX_HAZARD finishes per flip (always on: vk/vertex.c prints
                the running total on I/hakuX at most every 10 s, only after a
                finish; linear between lines, so 10 s resolution)

Bands by fps (>=28.5, 26-28.5, <26), medians, on stderr. The Turnip check
(the brief: no run counts without it) is printed first.

Usage: drive_split.py <result dir> [--all]   (--all: include pre-mark windows)
"""
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime

TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d)\s')
KV = re.compile(r'(\w+)=(-?[\d.]+)')


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S.%f').timestamp()


def kv(s):
    return {k: float(v) for k, v in KV.findall(s)}


def pid_of(line):
    m = re.search(r'\(\s*(\d+)\):', line)
    return m.group(1) if m else None


def nearest(lst, t, tol):
    best = None
    for e in lst:
        if abs(e[0] - t) <= tol and (best is None or abs(e[0] - t) < abs(best[0] - t)):
            best = e
    return best[1] if best else {}


def interp(series, t):
    """A running total at time t, linear between its (time, total) points."""
    if not series or t <= series[0][0]:
        return series[0][1] if series else None
    for (t0, n0), (t1, n1) in zip(series, series[1:]):
        if t0 <= t <= t1:
            return n0 + (n1 - n0) * (t - t0) / (t1 - t0) if t1 > t0 else n1
    return None  # past the last line: unknown, not flat


def over(lst, w0, w1):
    """Mean of the dicts whose own time falls inside (w0, w1]."""
    sel = [d for (t, d) in lst if w0 < t <= w1]
    if not sel:
        return {}
    keys = set().union(*sel)
    out = {}
    for k in keys:
        vals = [d[k] for d in sel if isinstance(d.get(k), (int, float))]
        if vals:
            out[k] = sum(vals) / len(vals)
    return out


def main():
    rdir = sys.argv[1]
    include_all = '--all' in sys.argv
    log = os.path.join(rdir, 'logcat.txt')
    lines = open(log, errors='replace').read().splitlines()

    # The emulator's pid: the one that prints hakuX-pace.
    pids = Counter(pid_of(l) for l in lines if 'hakuX-pace' in l)
    pid = pids.most_common(1)[0][0] if pids else None
    turnip = [l for l in lines if 'GPU: PurpleVK' in l or 'Loading custom Vulkan driver' in l
              or ('[gpl569]' in l and 'mode=' in l)]
    print('turnip check: %s' % (turnip[0].strip() if turnip else 'NONE FOUND -- run does not count'))
    for l in turnip[1:3]:
        print('              %s' % l.strip())

    mark = None
    pace, perf, rdc, fsk, cbl = [], [], [], [], []
    stall, phase, cpu, ft1, txr = [], [], [], [], []
    hz = []
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
        elif 'hakuX-perf' in l and 'gfps=' in l:
            m = re.search(r'Ri:([\d.]+) Tq:(\d+)', l)
            if m:
                perf.append((t, {'Ri': float(m.group(1)), 'Tq': int(m.group(2))}))
        elif '[rdc]' in l:
            m = re.search(r'f=(\d+) dt=(\d+) tid=(\d+) tcpu=([\d.]+)', l)
            if m:
                rdc.append((t, {'f': int(m.group(1)), 'dt': int(m.group(2)),
                                'tcpu': float(m.group(4))}))
        elif 'vtx_hazard: ' in l:
            m = re.search(r'vtx_hazard: (\d+) finishes', l)
            if m:
                hz.append((t, int(m.group(1))))
        elif 'fifoskew win=' in l:
            m = re.search(r'drain\(n=(\d+) mean=(\d+) p50=(\d+)', l)
            b = re.search(r'backlog\(mean=(\d+)', l)
            if m:
                d = {'backlog_kb': int(b.group(1)) / 1024 if b else 0}
                if int(m.group(1)):  # n=0: the FIFO never drained; no drain time, not 0
                    d['drain'] = int(m.group(2)) / 1e6
                    d['drain50'] = int(m.group(3)) / 1e6
                fsk.append((t, d))
        elif 'cblat win=' in l:
            m = re.search(r'flips=(\d+)', l)
            s = re.search(r'split\(([^)]*)\)', l)
            if m and s and int(m.group(1)):
                d = kv(s.group(1))
                n = int(m.group(1))
                cbl.append((t, {'cb_fin': d.get('fin', 0) / n, 'cb_mdraw': d.get('mdraw', 0) / n}))
        elif 'hakuX-stall' in l and 'Finish:' in l:
            m = re.search(r'Finish:(\d+)\(([^)]*)\)', l)
            if m:
                d = {'fin': int(m.group(1))}
                for k, v in re.findall(r'([a-zA-Z]+)(\d+)', m.group(2)):
                    d['fin_' + k] = int(v)
                stall.append((t, d))
        elif 'hakuX-stall' in l and 'txr[' in l:
            m = re.search(r'dl(\d+)/', l)
            x = re.search(r'txdl\[([^\]]*)\]', l)
            d = {'txdl_n': int(m.group(1)) if m else 0,
                 'txdl_why': ' '.join(w for w in (x.group(1).split() if x else [])
                                      if not w.endswith('0') or re.search(r'[1-9]', w))}
            txr.append((t, d))
        elif 'hakuX-phase' in l:
            d = {}
            for k in ('Draw', 'Fin', 'Idle', 'Tot', 'GPU'):
                m = re.search(r'\b' + k + r':([\d.]+)', l)
                if m:
                    d['ph_' + k.lower()] = float(m.group(1))
            m = re.search(r'Fin:[\d.]+\(Sub:([\d.]+) Fen:([\d.]+)\)', l)
            if m:
                d['ph_sub'], d['ph_fen'] = float(m.group(1)), float(m.group(2))
            m = re.search(r'GPU:[\d.]+\(R:([\d.]+) X:([\d.]+)', l)
            if m:
                d['gpu_r'], d['gpu_x'] = float(m.group(1)), float(m.group(2))
            phase.append((t, d))
        elif 'hakuX-cpu' in l and 'Lw:' in l:
            m = re.search(r'Lw:([\d.]+)', l)
            cpu.append((t, {'lw': float(m.group(1))}))
        elif '[hakuX-ft1]' in l:
            d = kv(l.split('[hakuX-ft1]', 1)[1])
            m = re.search(r'fw=([^,\s]+)', l)
            ft = {k: d[k] for k in ('prun', 'pblk', 'pidle', 'gpu50', 'p50', 'lw') if k in d}
            if m:
                fm = re.match(r'(.*):([\d.]+)/([\d.]+)$', m.group(1))
                if fm:
                    ft['fw1_ms'] = float(fm.group(2))
                    ft['fw1_site'] = fm.group(1)
            ft1.append((t, ft))

    print('pid %s, mark gameplay %s, pace windows %d, perflog lines %d, ft1 lines %d, '
          'vtx_hazard lines %d'
          % (pid, datetime.fromtimestamp(mark).strftime('%H:%M:%S') if mark else 'NONE',
             len(pace), len(phase), len(ft1), len(hz)))

    cols = ['t', 'fps', 'Ri', 'Tq', 'pf_cpu', 'pf_blk', 'hz', 'drain50', 'backlog_kb', 'cb_fin',
            'cb_mdraw', 'fin', 'fin_sd', 'fin_vtx', 'fin_flip', 'fin_stl', 'fin_sc', 'fin_buf',
            'fin_fb', 'ph_draw', 'ph_fin', 'ph_sub', 'ph_fen', 'ph_idle', 'ph_gpu', 'gpu_r',
            'gpu_x', 'lw', 'prun', 'pblk', 'pidle', 'gpu50', 'fw1_ms', 'fw1_site', 'txdl_n',
            'txdl_why']
    print('\t'.join(cols))
    rows = []
    prev_f = None
    for t, p in pace:
        f = p.get('f')
        ms = p.get('ms', 0)
        nf = (f - prev_f) if prev_f is not None and f is not None else 60
        prev_f = f
        if ms <= 0 or nf <= 0:
            continue
        if mark and not include_all and t - ms / 1e3 < mark:
            continue
        period = ms / nf
        r = {'t': datetime.fromtimestamp(t).strftime('%H:%M:%S'), 'fps': 1000.0 / period}
        r.update(nearest(perf, t, 0.5))
        rd = nearest(rdc, t, 1.5)
        if rd.get('f'):
            r['pf_cpu'] = rd['tcpu'] / rd['f']
            r['pf_blk'] = rd['dt'] / rd['f'] - r.get('Ri', 0) - r['pf_cpu']
        w0 = t - ms / 1e3
        h0, h1 = interp(hz, w0), interp(hz, t)
        if h0 is not None and h1 is not None:
            r['hz'] = (h1 - h0) / nf
        for src in (fsk, cbl, ft1):
            r.update(over(src, w0, t))
        for src in (stall, phase, cpu, txr):
            r.update(nearest(src, t, 0.5))
        # ft1's non-numeric site: the most recent inside the window
        sites = [d.get('fw1_site') for (tt, d) in ft1 if w0 < tt <= t and d.get('fw1_site')]
        if sites:
            r['fw1_site'] = Counter(sites).most_common(1)[0][0]
        rows.append(r)

        def fmt(c):
            v = r.get(c)
            if v is None:
                return '-'
            if isinstance(v, float):
                return '%.1f' % v
            return str(v)
        print('\t'.join(fmt(c) for c in cols))

    bands = [('>=28.5', lambda x: x >= 28.5), ('26-28.5', lambda x: 26 <= x < 28.5),
             ('<26', lambda x: x < 26)]
    num = [c for c in cols if c not in ('t', 'fw1_site', 'txdl_why')]
    n_bar = sum(1 for r in rows if r['fps'] >= 28.5)
    sys.stderr.write('windows %d, at >=28.5: %d (%.1f%%)\n'
                     % (len(rows), n_bar, 100.0 * n_bar / len(rows) if rows else 0))
    sys.stderr.write('band\tn\t' + '\t'.join(num) + '\n')
    for name, pred in bands:
        sel = [r for r in rows if pred(r['fps'])]
        meds = []
        for k in num:
            vals = [r[k] for r in sel if isinstance(r.get(k), (int, float))]
            meds.append('%.1f' % statistics.median(vals) if vals else '-')
        sys.stderr.write('%s\t%d\t%s\n' % (name, len(sel), '\t'.join(meds)))


if __name__ == '__main__':
    main()
