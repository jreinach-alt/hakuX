#!/usr/bin/env python3
"""Split each 60-flip hakuX-pace window of a plain-build logcat into vCPU,
PFIFO-thread CPU, PFIFO parked time and the remainder, from the always-on
lines ([rr425w], [rdc], fifoskew, hakuX-perf). No frametrace needed.

Each 2 s instrument line covers [t - dt, t]; it is weighted into a pace
window [t_k - ms, t_k] by its overlap. Usage:

    winsplit.py LOGCAT [--from HH:MM:SS] [--to HH:MM:SS] [--csv OUT]
"""
import argparse
import csv
import re
import sys
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


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--from', dest='t_from')
    ap.add_argument('--to', dest='t_to')
    ap.add_argument('--csv')
    a = ap.parse_args()

    pace, perf, rrw, rdc, fsk = [], [], [], [], []
    with open(a.log, errors='replace') as f:
        for line in f:
            t = ts(line)
            if t is None:
                continue
            if 'hakuX-pace' in line and ' f=' in line:
                pace.append((t, kv(line.split('):', 1)[1])))
            elif 'hakuX-perf' in line and 'gfps=' in line:
                m = re.search(r'gfps=(\d+) G:([\d.]+).*Df:(\d+).*Vpf:([\d.]+) '
                              r'Ri:([\d.]+) Tq:(\d+)', line)
                if m:
                    perf.append((t, dict(gfps=int(m.group(1)),
                                         G=float(m.group(2)),
                                         Df=int(m.group(3)),
                                         Vpf=float(m.group(4)),
                                         Ri=float(m.group(5)),
                                         Tq=int(m.group(6)))))
            elif '[rr425w]' in line:
                body = line.split('[rr425w]', 1)[1]
                head = kv(body)
                keys = {}
                for m in re.finditer(r' ([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):(\d+):', body):
                    keys[m.group(1) + '.' + m.group(2)] = (
                        int(m.group(3)), int(m.group(4)), int(m.group(5)))
                idle = head.get('idle_us', 0)
                busy = head.get('busy_us', 0)
                rrw.append((t, (idle + busy) / 1e6, idle, busy, keys))
            elif '[rdc]' in line:
                m = re.search(r'dt=(\d+) tid=(\d+) tcpu=([\d.]+)', line)
                if m:
                    rdc.append((t, int(m.group(1)) / 1e3, int(m.group(2)),
                                float(m.group(3))))
            elif 'fifoskew win=' in line:
                m = re.search(r'win=(\d+)ms kicks=(\d+) behind=(\d+).*'
                              r'backlog\(mean=(\d+) max=(\d+)\) '
                              r'drain\(n=(\d+) mean=(\d+) p50=(\d+)', line)
                if m:
                    fsk.append((t, int(m.group(1)) / 1e3, int(m.group(2)),
                                int(m.group(3)), int(m.group(4)),
                                int(m.group(6)), int(m.group(7)) / 1e6,
                                int(m.group(8)) / 1e6))

    def hhmmss(s):
        if not s:
            return None
        d = datetime.fromtimestamp(pace[0][0]).strftime('%Y-%m-%d ')
        return datetime.strptime(d + s, '%Y-%m-%d %H:%M:%S').timestamp()

    t_from, t_to = hhmmss(a.t_from), hhmmss(a.t_to)
    rows = []
    for t, p in pace:
        if t_from and t < t_from or t_to and t > t_to:
            continue
        ms = p.get('ms', 0) / 1e3
        if ms <= 0:
            continue
        w0, w1 = t - ms, t
        period = ms * 1e3 / 60
        idle = busy = cov = 0.0
        nv_busy = tmr_idle = 0.0
        for (tt, dt, i_us, b_us, keys) in rrw:
            o = overlap(w0, w1, tt - dt, tt)
            if o <= 0 or dt <= 0:
                continue
            fr = o / dt
            idle += i_us * fr
            busy += b_us * fr
            cov += o
            for k, (n, ki, kb) in keys.items():
                if k.startswith('33.'):
                    nv_busy += kb * fr
                if k == '30.00':
                    tmr_idle += ki * fr
        tc = tcov = 0.0
        tids = set()
        for (tt, dt, tid, tcpu) in rdc:
            o = overlap(w0, w1, tt - dt, tt)
            if o <= 0 or dt <= 0:
                continue
            tids.add(tid)
            tc += tcpu * o / dt
            tcov += o
        dr = drc = bl = 0.0
        p50 = []
        for (tt, dt, kicks, behind, blm, dn, dmean, dp50) in fsk:
            o = overlap(w0, w1, tt - dt, tt)
            if o <= 0:
                continue
            dr += dmean * o
            bl += blm * o
            drc += o
            p50.append(dp50)
        pf = min(perf, key=lambda x: abs(x[0] - t)) if perf else (t, {})
        pf = pf[1] if abs(pf[0] - t) < 0.5 else {}
        vsh = (busy / (idle + busy)) if idle + busy else float('nan')
        row = dict(
            t=datetime.fromtimestamp(t).strftime('%H:%M:%S'),
            gfps=pf.get('gfps'), period=period,
            v2=int(p.get('v2', 0)), v3=int(p.get('v3', 0)), v4=int(p.get('v4', 0)),
            vcpu_ms=vsh * period, vcpu_sh=vsh,
            nv_busy_ms=(nv_busy / (idle + busy)) * period if idle + busy else float('nan'),
            pfifo_ms=(tc / (tcov * 1e3)) * period if tcov else float('nan'),
            ri=pf.get('Ri'), df=pf.get('Df'), tq=pf.get('Tq'),
            drain_ms=dr / drc if drc else float('nan'),
            backlog_kb=bl / drc / 1024 if drc else float('nan'),
            tids=','.join(str(x) for x in sorted(tids)),
        )
        row['rest_ms'] = period - row['pfifo_ms'] - (row['ri'] or 0)
        rows.append(row)

    cols = ['t', 'gfps', 'period', 'v2', 'v3', 'v4', 'vcpu_ms', 'vcpu_sh',
            'nv_busy_ms', 'pfifo_ms', 'ri', 'rest_ms', 'df', 'tq', 'drain_ms',
            'backlog_kb', 'tids']
    print(' '.join('%9s' % c[:9] for c in cols))
    for r in rows:
        out = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                out.append('%9.2f' % v if c == 'vcpu_sh' else '%9.1f' % v)
            else:
                out.append('%9s' % ('-' if v is None else v))
        print(' '.join(out))
    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


if __name__ == '__main__':
    sys.exit(main())
