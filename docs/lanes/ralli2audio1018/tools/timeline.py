#!/usr/bin/env python3
"""Per-window timeline of a hakuX threadtime logcat: audio starve windows
against the other once-a-second (or 2 s) instruments.

usage: timeline.py LOGCAT [--from LINE] [--t0 HH:MM:SS] [--only-short]

Each `hakuX-audiocap: starve:` line is the DELTA since the previous line
(apu.c apu_starve_report), so a starve window runs from the previous starve
line to this one. For every window this prints the starve figures and, over
the same span, the worst frame (hakuX-pace max), the shader create time
(shd413 dpc_ms), JIT translation (hakuX-pages "generated A of B calls"),
DVD DMA (ide425d dma_kb), vCPU busy share (rr425w), and the vCPU run-queue
wait (idlehalt rq_us).
"""
import re
import sys

TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d\d\d)\s+\d+\s+(\d+)\s')


def ts(line):
    m = TS.match(line)
    if not m:
        return None, None
    h, mi, s, ms, tid = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0, int(tid)


def kv(line, key, cast=float):
    m = re.search(r'(?:^|[\s(])' + re.escape(key) + r'=(-?[0-9.]+)', line)
    return cast(m.group(1)) if m else None


def main():
    path = sys.argv[1]
    start = 1
    t0 = None
    only_short = '--only-short' in sys.argv
    if '--from' in sys.argv:
        start = int(sys.argv[sys.argv.index('--from') + 1])
    rows = []  # (t, kind, dict)
    with open(path, errors='replace') as f:
        for n, line in enumerate(f, 1):
            if n < start:
                continue
            t, tid = ts(line)
            if t is None:
                continue
            if 'hakuX-audiocap: starve:' in line:
                m = re.search(r'starve: (\d+)/(\d+) callbacks short \((\d+) empty\), '
                              r'(\d+)/(\d+) bytes zero-filled = ([0-9.]+)%', line)
                if m:
                    rows.append((t, 'starve', dict(short=int(m.group(1)),
                                calls=int(m.group(2)), empty=int(m.group(3)),
                                zb=int(m.group(4)), ab=int(m.group(5)),
                                pct=float(m.group(6)))))
            elif 'hakuX-pace:' in line:
                rows.append((t, 'pace', dict(max=kv(line, 'max'), ms=kv(line, 'ms'))))
            elif '[shd413]' in line:
                rows.append((t, 'shd', dict(dpc=kv(line, 'dpc_ms'), dpm=kv(line, 'dpm'),
                                            dsm=kv(line, 'dsm'))))
            elif 'hakuX-pages: slow stores' in line:
                m = re.search(r'generated (\d+) of (\d+) calls', line)
                d = re.search(r'blocks discarded (\d+) of', line)
                rows.append((t, 'jit', dict(gen=int(m.group(1)) if m else 0,
                                            disc=int(d.group(1)) if d else 0)))
            elif '[ide425d]' in line:
                rows.append((t, 'ide', dict(kb=kv(line, 'dma_kb'), gapmax=kv(line, 'gap_us_max'),
                                            win=kv(line, 'win_us'))))
            elif '[rr425w]' in line:
                rows.append((t, 'cpu', dict(idle=kv(line, 'idle_us'), busy=kv(line, 'busy_us'))))
            elif '[idlehalt]' in line:
                rows.append((t, 'rq', dict(rq=kv(line, 'rq_us'), run=kv(line, 'run_us'),
                                           span=kv(line, 'span_us'))))
            elif 'hakuX-perf: gfps=' in line:
                m = re.search(r'gfps=(\d+) G:([0-9.]+)\(([0-9.]+)-([0-9.]+)\)', line)
                ri = re.search(r'Ri:([0-9.]+)', line)
                tq = re.search(r'Tq:(\d+)', line)
                rows.append((t, 'gfps', dict(gfps=int(m.group(1)) if m else None,
                                             gmax=float(m.group(4)) if m else None,
                                             ri=float(ri.group(1)) if ri else None,
                                             tq=int(tq.group(1)) if tq else None)))
            elif '[tlb68]' in line:
                rows.append((t, 'tlb', dict(pf=kv(line, 'pf'), cpu=kv(line, 'cpu'))))
            elif '[pic14]' in line:
                rows.append((t, 'pic', dict(raise_=kv(line, 'raise'))))
    if '--t0' in sys.argv:
        h, mi, s = sys.argv[sys.argv.index('--t0') + 1].split(':')
        t0 = int(h) * 3600 + int(mi) * 60 + float(s)
    else:
        t0 = rows[0][0]

    def span(kind, a, b, field, agg=max):
        vals = [r[2][field] for r in rows if r[1] == kind and a < r[0] <= b + 0.5
                and r[2].get(field) is not None]
        return agg(vals) if vals else None

    prev = None
    print('%7s %7s %6s %9s %8s %7s %7s %6s %6s %7s %6s %5s %6s' % (
        'from', 'to', 'short', 'zerofill', 'pct', 'paceMx', 'dpcMs', 'jitGen',
        'dmaKB', 'busy%', 'rqMs', 'Tq', 'pfK'))
    for t, kind, d in rows:
        if kind != 'starve':
            continue
        if prev is None:
            prev = t
            continue
        if only_short and not d['short']:
            prev = t
            continue
        pm = span('pace', prev, t, 'max')
        dpc = span('shd', prev, t, 'dpc', sum)
        gen = span('jit', prev, t, 'gen', sum)
        kb = span('ide', prev, t, 'kb', sum)
        busy = [r[2] for r in rows if r[1] == 'cpu' and prev < r[0] <= t + 0.5]
        bs = (100.0 * sum(x['busy'] for x in busy) /
              max(1, sum(x['busy'] + x['idle'] for x in busy))) if busy else None
        rq = span('rq', prev, t, 'rq', max)
        tq = span('gfps', prev, t, 'tq', max)
        pf = span('tlb', prev, t, 'pf', sum)
        print('%7.1f %7.1f %3d/%-3d %9d %8.4f %7.1f %7.1f %6s %6s %7s %6s %5s %6s' % (
            prev - t0, t - t0, d['short'], d['calls'], d['zb'], d['pct'],
            pm or 0, dpc or 0, gen, kb,
            '%.1f' % bs if bs is not None else '-',
            '%.1f' % (rq / 1000.0) if rq is not None else '-', tq,
            '%.1f' % (pf / 1000.0) if pf is not None else '-'))
        prev = t


if __name__ == '__main__':
    main()
