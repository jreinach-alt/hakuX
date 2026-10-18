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

--prod prints a second table: per starve window, the producer-timing line
apu.c prints right after it (`hakuX-audiocap: prod:`, lane ralli2audio1018)
and the producer's deficit, which is wall time minus the audio it pushed
over the level meter's 5 s windows (`hakuX-audio: level L: <s>`) that end
inside the starve window.
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


PROD = re.compile(
    r'prod: blk=(\d+) free=(\d+) late=(\d+)/([0-9.]+)ms qmin=(-?\d+) '
    r'gap=([0-9.]+)ms wall=([0-9.]+)/([0-9.]+)ms cpu=([0-9.]+)/([0-9.]+)ms '
    r'vp=(\d+)/(\d+)us bql=([0-9.]+)ms rq=([0-9.]+)ms wrq=([0-9.]+)/([0-9.]+)ms '
    r'c=([0-9/]+) \| cb=(\d+) gapmax=([0-9.]+)ms lvlmin=(-?\d+) short=(-?\d+)B '
    r'lvl=(-?\d+) age=(-?[0-9.]+)ms prev=(-?[0-9.]+)ms')
PROD_KEYS = ('blk', 'free', 'late', 'late_ms', 'qmin', 'gap', 'wall', 'wallmax',
             'cpu', 'cpumax', 'vp', 'vpmax', 'bql', 'rq', 'wrq', 'wrqmax', 'c',
             'cb', 'cbgap', 'lvlmin', 'short', 'lvl', 'age', 'prev')


def prod_fields(line):
    m = PROD.search(line)
    if not m:
        return {}
    d = {}
    for k, v in zip(PROD_KEYS, m.groups()):
        d[k] = v if k == 'c' else float(v)
    return d


def prod_table(rows, t0):
    """One row per starve window: its prod: line and the producer deficit."""
    levels = [(t, d['s']) for t, k, d in rows if k == 'level']
    print('%7s %7s %6s %4s %5s %6s %6s %6s %6s %6s %7s %6s %6s %6s %6s %6s %6s %6s %s' % (
        'from', 'to', 'short', 'free', 'qmin', 'gapMs', 'wallMx', 'cpuMx',
        'vpMxUs', 'bqlMs', 'rqMs', 'wrqMx', 'cbGap', 'shB', 'shLvl', 'ageMs',
        'prevMs', 'defMs', 'cpus'))
    prev = None
    last_starve = None
    for t, kind, d in rows:
        if kind == 'starve':
            last_starve = (prev, t, d)
            prev = t
            continue
        if kind != 'prod' or not d or last_starve is None or last_starve[0] is None:
            continue
        a, b, s = last_starve
        deficit = 0.0
        for (t1, s1), (t2, s2) in zip(levels, levels[1:]):
            if a < t2 <= b + 0.5:
                deficit += (t2 - t1) - (s2 - s1)
        print('%7.1f %7.1f %3d/%-3d %4d %5d %6.1f %6.1f %6.1f %6d %6.2f %7.1f %6.1f %6.1f %6d %6d %6.1f %6.1f %6.0f %s' % (
            a - t0, b - t0, s['short'], s['calls'], d['free'], d['qmin'], d['gap'],
            d['wallmax'], d['cpumax'], d['vpmax'], d['bql'], d['rq'], d['wrqmax'],
            d['cbgap'], d['short'], d['lvl'], d['age'], d['prev'], deficit * 1000,
            d['c']))


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
            elif 'hakuX-audiocap: prod:' in line:
                rows.append((t, 'prod', prod_fields(line)))
            elif 'hakuX-audio: level L:' in line:
                m = re.search(r'level L: ([0-9.]+) s', line)
                if m:
                    rows.append((t, 'level', dict(s=float(m.group(1)))))
    if '--t0' in sys.argv:
        h, mi, s = sys.argv[sys.argv.index('--t0') + 1].split(':')
        t0 = int(h) * 3600 + int(mi) * 60 + float(s)
    else:
        t0 = rows[0][0]

    if '--prod' in sys.argv:
        prod_table(rows, t0)
        return

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
