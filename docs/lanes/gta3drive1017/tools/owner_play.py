#!/usr/bin/env python3
"""Per-window table of the owner's GTA III play (10-17, pid 21488, Turnip).

Question: in the windows where the frame rate drops, which thread's time
grows, and on what? Joins, per 60-flip window (the gfps/pace/rdc cadence):

  hakuX-pace   f, ms          -> fps = 60000 / ms over that window
  gfps         Ri, Tq         -> PFIFO park ms per flip (EWMA), dirty queries
  [rdc]        tcpu, vtx, tex -> PFIFO thread CPU ms (tid printed every line),
                                 TLB walks per site: calls/us/pages/hits
  [shd413]     dpn, dfb_ms    -> pipelines created / fallback ms in the window
  hakuX-pages  slow stores, inval ev
and, from the full logcat snapshot (2 s wall windows, the nearest one at or
before the window's end):
  [rr425w]     idle_us, busy_us, the 33.44 (NV2A interrupt) key's busy
  [idlehalt]   run_us, rq_us  -> vCPU thread on-CPU and runnable-waiting
  [ide425d]    dma, dma_kb    -> DVD reads (streaming)

Derived per flip: pfifo_cpu = tcpu/f, pfifo_blk = frame - Ri - pfifo_cpu
(time the PFIFO thread is neither parked nor on a CPU: blocked inside a
method), vcpu_off = (2000 ms - run - rq)/frames-in-2s.

Usage: owner_play.py <tag-filtered capture> <full snapshot> [--pid N]
Writes the TSV to stdout and a band summary to stderr.
"""
import re
import statistics
import sys
from datetime import datetime

TS = re.compile(r'^(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d\d\d) ')


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.strptime('2026-' + m.group(1) + ' ' + m.group(2),
                             '%Y-%m-%d %H:%M:%S.%f').timestamp()


def kv(s):
    return dict(re.findall(r'(\w+)=([^\s]+)', s))


def site(v):
    a = [float(x) for x in v.split('/')]
    return a


def main():
    cap, snap = sys.argv[1], sys.argv[2]
    pid = sys.argv[sys.argv.index('--pid') + 1] if '--pid' in sys.argv else '21488'
    rows = []          # one per gfps line
    cur = {}
    rdc_pending = None
    for line in open(cap, errors='replace'):
        if '(' + pid + ')' not in line:
            continue
        t = ts(line)
        if 'hakuX-perf' in line and ' gfps=' in line:
            m = re.search(r'gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\).*?S:([\d.]+).*?Df:(\d+).*?Vpf:([\d.]+) Ri:([\d.]+) Tq:(\d+)', line)
            cur = {'t': t, 'clock': line[6:18], 'gfps': int(m.group(1)),
                   'G': float(m.group(2)), 'Gmax': float(m.group(4)),
                   'S': float(m.group(5)), 'Df': int(m.group(6)),
                   'Vpf': float(m.group(7)), 'Ri': float(m.group(8)),
                   'Tq': int(m.group(9))}
            rows.append(cur)
        elif 'hakuX-pace' in line and cur:
            d = kv(line)
            cur['f'] = int(d['f'])
            cur['ms'] = float(d['ms'])
            cur['max'] = float(d['max'])
        elif '[shd413]' in line and cur:
            d = kv(line)
            cur['dpn'] = int(d['dpn'])
            cur['dfb_ms'] = float(d['dfb_ms'])
        elif '[rdc]' in line and cur:
            d = kv(line)
            cur['rdc_dt'] = float(d['dt'])
            cur['rdc_f'] = int(d['f'])
            cur['tcpu'] = float(d['tcpu']) if d['tcpu'] != '-' else None
            cur['vtx'] = site(d['vtx'])
            cur['tex'] = site(d['tex'])
        elif 'hakuX-pages' in line and 'slow stores' in line and cur:
            m = re.search(r'slow stores (\d+) \((\d+) reached', line)
            cur['slow'] = int(m.group(1))
            cur['inv'] = int(m.group(2))
    # 2 s wall-window lines from the full snapshot
    w = {'rr': [], 'ih': [], 'ide': []}
    for line in open(snap, errors='replace'):
        if '(' + pid + ')' not in line:
            continue
        t = ts(line)
        if '[rr425w]' in line:
            d = kv(line)
            m = re.search(r' 33\.44:(\d+):(\d+):(\d+):', line)
            w['rr'].append((t, float(d['idle_us']) / 1e3, float(d['busy_us']) / 1e3,
                            float(m.group(3)) / 1e3 if m else 0.0,
                            int(m.group(1)) if m else 0))
        elif '[idlehalt]' in line:
            d = kv(line)
            w['ih'].append((t, float(d['span_us']) / 1e3, float(d['run_us']) / 1e3,
                            float(d['rq_us']) / 1e3))
        elif '[ide425d]' in line:
            d = kv(line)
            w['ide'].append((t, int(d['dma']), int(d['dma_kb'])))

    def near(lst, t):
        best = None
        for e in lst:
            if e[0] <= t + 1.0:
                best = e
        return best

    cols = ['clock', 'fps', 'Gmax', 'Ri', 'Tq', 'pf_cpu', 'pf_blk', 'tex_c',
            'tex_us', 'tex_pg', 'vtx_c', 'vtx_us', 'vtx_pg', 'vtx_pg_c',
            'dpn', 'dfb_ms', 'slow', 'inv', 'g_idle', 'g_busy', 'g_b33',
            'g_n33', 'v_run', 'v_rq', 'v_off', 'dvd', 'dvd_kb']
    print('\t'.join(cols))
    prev_f = None
    out = []
    for r in rows:
        if 'ms' not in r:
            continue
        nf = r['f'] - prev_f if prev_f is not None else 60
        prev_f = r['f']
        if nf <= 0:
            continue
        frame = r['ms'] / nf
        fps = 1000.0 / frame
        o = {'clock': r['clock'], 'fps': fps, 'Gmax': r['Gmax'], 'Ri': r['Ri'],
             'Tq': r['Tq']}
        if r.get('tcpu') is not None and r.get('rdc_f'):
            o['pf_cpu'] = r['tcpu'] / r['rdc_f']
            o['pf_blk'] = (r['rdc_dt'] / r['rdc_f']) - r['Ri'] - o['pf_cpu']
            o['tex_c'], o['tex_us'], o['tex_pg'] = (x / r['rdc_f'] for x in r['tex'][:3])
            o['vtx_c'], o['vtx_us'], o['vtx_pg'] = (x / r['rdc_f'] for x in r['vtx'][:3])
            o['vtx_pg_c'] = r['vtx'][2] / r['vtx'][0] if r['vtx'][0] else 0
        o['dpn'] = r.get('dpn')
        o['dfb_ms'] = r.get('dfb_ms')
        o['slow'] = r.get('slow')
        o['inv'] = r.get('inv')
        rr = near(w['rr'], r['t'])
        if rr:
            fr2 = 2000.0 / frame
            o['g_idle'] = rr[1] / fr2
            o['g_busy'] = rr[2] / fr2
            o['g_b33'] = rr[3] / fr2
            o['g_n33'] = rr[4]
        ih = near(w['ih'], r['t'])
        if ih:
            fr2 = ih[1] / frame
            o['v_run'] = ih[2] / fr2
            o['v_rq'] = ih[3] / fr2
            o['v_off'] = (ih[1] - ih[2] - ih[3]) / fr2
        ide = near(w['ide'], r['t'])
        if ide:
            o['dvd'] = ide[1]
            o['dvd_kb'] = ide[2]
        out.append(o)

        def f(c):
            v = o.get(c)
            if v is None:
                return '-'
            if isinstance(v, float):
                return '%.1f' % v
            return str(v)
        print('\t'.join(f(c) for c in cols))

    # Gameplay only: from the first Tq >= 100 reading (the load at 14:37:40).
    start = next(i for i, o in enumerate(out) if o['Tq'] >= 100)
    game = [o for o in out[start:] if o['Tq'] >= 100]
    bands = [('>=28.5', lambda x: x >= 28.5), ('26-28.5', lambda x: 26 <= x < 28.5),
             ('<26', lambda x: x < 26)]
    sys.stderr.write('gameplay windows (Tq>=100 from %s): %d\n'
                     % (out[start]['clock'], len(game)))
    keys = [c for c in cols if c not in ('clock',)]
    sys.stderr.write('band\tn\t' + '\t'.join(keys) + '\n')
    for name, pred in bands:
        sel = [o for o in game if pred(o['fps'])]
        meds = []
        for k in keys:
            vals = [o[k] for o in sel if o.get(k) is not None]
            meds.append('%.1f' % statistics.median(vals) if vals else '-')
        sys.stderr.write('%s\t%d\t%s\n' % (name, len(sel), '\t'.join(meds)))


if __name__ == '__main__':
    main()
