#!/usr/bin/env python3
"""The #425 return split from a soak's [rr425] / [rr425pc] lines.

    python3 rr425.py [--from S] [--to S] <result-id | logcat path> [...]

Windows are seconds since the logcat's first line (the aufire412b windows:
AUF mission play is 299-483 on the survey route). For every [rr425] window
whose line falls inside [from, to] it sums the counters, and it takes the
frame rate from the hakuX-perf gfps lines in the same span. It prints:

  - returns per second and per frame by cause, and each cause's share;
  - the checks the counter owes before any number is read:
      d <= x          a return none of the causes booked is a longjmp
      m ~= hm         the loop's miss count agrees with the helper's own
      gs+gi+ga <= g   the goto_tb split does not exceed its parent
  - the loop cost: gapus (sampled loop time, scaled to all dispatches) in ms
    per frame, beside the 37 ms/frame bound from the #412 profile;
  - the top 16 (cause, pc) pairs summed over the span, with guest bytes;
  - from [rr425w]: the guest's idle time and what ended each idle stretch,
    by interrupt vector and the NV2A units pending at the wake, with the
    busy period each wake started, in ms per frame; the check that
    idle + busy comes to the wall clock of the span; and the same keys
    rolled up by source, with each source's share of the busy periods of
    2 ms or more (the wakes that readied a thread).

--selftest runs it on a built-in two-window logcat.
"""
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
KV = re.compile(r'(\w+)=(-?\d+)')
PC = re.compile(r' ([a-z]):([0-9a-f]{8}):([0-9a-f]{6}):(\d+)')
WK = re.compile(r' ([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):(\d+)'
                r':(\d+)/(\d+)/(\d+)/(\d+):(\d+)/(\d+)/(\d+)/(\d+):(\d+)')
# The Xbox kernel maps IRQ n to vector 0x30 + n (HalGetInterruptVector).
IRQ = {0: 'PIT timer', 1: 'USB0', 3: 'NV2A', 4: 'NIC', 5: 'APU', 6: 'ACI',
       9: 'USB1', 11: 'SMBus', 14: 'IDE', 15: 'IDE2'}
UNITS = ['PFIFO', 'PCRTC(vblank)', 'PGRAPH', 'pg.NOTIFY', 'pg.CTXSW',
         'pg.BUFNOTIFY', 'pg.ERROR', 'pg.other']
WF = ['n', 'idle_us', 'busy_us', 'i0', 'i1', 'i2', 'i3',
      'b0', 'b1', 'b2', 'b3', 'nb']
CAUSES = [('e', 'gen_eob plain exit_tb'), ('m', 'lookup_tb_ptr miss'),
          ('r', 'TB_EXIT_REQUESTED'), ('g', 'goto_tb not patched'),
          ('o', 'other NULL exit')]
SUB = [('en', 'e: EOB_NEXT'), ('es', 'e: EOB_INHIBIT_IRQ (STI, MOV SS)'),
       ('eo', 'e: EOB_ONLY (IRET, far jump)'), ('et', 'e: RECHECK_TF'),
       ('ej', 'e: DISAS_JUMP in a shadow'), ('esh', 'e: TB began in a shadow'),
       ('gs', 'g: target spans pages'), ('gi', 'g: CF_INVALID'),
       ('ga', 'g: tb_add_jump called')]


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')


def read(lines, lo, hi):
    t0 = None
    tot = Counter()
    nwin = 0
    pcs = Counter()
    gfps = []
    wake = defaultdict(Counter)
    for line in lines:
        try:
            t = ts(line)
        except ValueError:
            continue
        if t0 is None:
            t0 = t
        s = (t - t0).total_seconds()
        if not lo <= s <= hi:
            continue
        if '[rr425] ' in line:
            kv = {k: int(v) for k, v in KV.findall(line.split('[rr425]', 1)[1])}
            tot.update(kv)
            nwin += 1
        elif '[rr425w] ' in line:
            body = line.split('[rr425w]', 1)[1]
            m0 = WK.search(body)
            kv = {k: int(v) for k, v in KV.findall(body[:m0.start()] if m0 else body)
                  if k in ('idle_us', 'busy_us', 'n', 'nb', 'drop')}
            tot.update({'w_' + k: v for k, v in kv.items()})
            tot['w_lines'] += 1
            for m in WK.findall(body):
                key = (int(m[0], 16), int(m[1], 16))
                wake[key].update(dict(zip(WF, map(int, m[2:]))))
        elif '[rr425pc] ' in line:
            for c, pc, b, n in PC.findall(line):
                pcs[(c, pc, b)] += int(n)
        elif 'hakuX-perf' in line:
            # G:<mean ms per guest frame>; gfps is an integer and too coarse.
            m = re.search(r' G:([\d.]+)', line)
            if m and float(m.group(1)) > 0:
                gfps.append(float(m.group(1)))
    return tot, nwin, pcs, gfps, wake


def label(vec, units):
    irq = vec - 0x30
    s = 'v%02x' % vec + (' irq%d %s' % (irq, IRQ.get(irq, '?'))
                         if 0 <= irq < 16 else ' (not a PIC irq)')
    u = [UNITS[i] for i in range(8) if units >> i & 1]
    return s + (' [' + ' '.join(u) + ']' if u else '')


def source(vec, units):
    """One source per wake key. A pending PGRAPH ERROR decides the source
    whatever the vector: it is raised only by NV097_NO_OPERATION with a
    non-zero parameter, the push buffer's software callback (pgraph.c)."""
    if units & 0x40:
        return 'PGRAPH ERROR (push-buffer callback)'
    if units & 0xb8:
        return 'PGRAPH other (NOTIFY, CTXSW, BUFNOTIFY)'
    if units & 0x01:
        return 'PFIFO'
    if vec == 0x33:
        return 'NV2A vblank' if units & 0x02 else 'NV2A, nothing pending'
    irq = vec - 0x30
    return IRQ.get(irq, 'v%02x' % vec) if 0 <= irq < 16 else 'v%02x' % vec


def by_source(wake):
    src = defaultdict(Counter)
    for key, w in wake.items():
        src[source(*key)].update(w)
    return src


def report_source(wake, frames):
    """Which interrupt starts the guest's work. A busy period of 2 ms or more
    is a thread that was readied; an ISR that returns to idle is under 0.2 ms.
    The 1 kHz PIT ends most idle stretches without readying anything, so idle
    time by key does not name what the guest waited for; the source of the
    long busy periods does."""
    src = by_source(wake)
    busy = sum(w['busy_us'] for w in src.values())
    long_n = sum(w['b3'] for w in src.values())
    per = (lambda n: '%.2f' % (n / frames)) if frames else (lambda n: 'n/a')
    print('   %-40s %8s %9s %9s %7s %9s %7s' % (
        'wake source', 'taken/f', 'wakes/f', 'busy ms/f', 'share', '>=2ms /f',
        'share'))
    for name, w in sorted(src.items(), key=lambda kv: -kv[1]['busy_us']):
        print('   %-40s %8s %9s %9s %6.1f%% %9s %6.1f%%' % (
            name, per(w['n'] + w['nb']), per(w['n']), per(w['busy_us'] / 1000),
            100.0 * w['busy_us'] / busy if busy else 0, per(w['b3']),
            100.0 * w['b3'] / long_n if long_n else 0))
    idle = sum(w['idle_us'] for w in src.values())
    print('   busy periods >= 2 ms: %s per frame; idle per such period %.1f ms'
          ' (derived: all idle / their count)' % (
              per(long_n), idle / 1000 / long_n if long_n else 0))
    return src


def report_wake(tot, wake, secs, frames):
    if not tot['w_lines']:
        print('   [rr425w]: none in the span (a build without the wake counter)')
        return True
    idle, busy = tot['w_idle_us'], tot['w_busy_us']
    wall = secs * 1e6
    per = (lambda us: '%.2f' % (us / 1000 / frames)) if frames else (lambda us: 'n/a')
    print('   idle: %.1f%% of wall, %s ms/frame; busy %.1f%%, %s ms/frame;'
          ' wakes %.0f/s' % (100 * idle / wall, per(idle), 100 * busy / wall,
                             per(busy), tot['w_n'] / secs))
    # Every microsecond of the vCPU thread is in an idle stretch or in the
    # busy period after a wake; stretches are booked whole in the window they
    # end in, so over many windows the two sum to the wall clock.
    good = abs(idle + busy - wall) <= 0.05 * wall and not tot['w_drop']
    print('     %-16s %s  idle+busy=%.1f s wall=%.1f s drop=%d' % (
        'idle+busy~wall', 'ok' if good else 'FAIL', (idle + busy) / 1e6,
        secs, tot['w_drop']))
    print('   %-44s %8s %8s %9s %8s %9s  %-15s %-15s %7s' % (
        'wake key (vector, NV2A units pending)', 'wakes/s', '/frame',
        'idle ms/f', 'mean us', 'busy ms/f', 'idle <.1/<1/<4/>=4ms',
        'busy <20u/<.2/<2/>=2ms', 'nb/s'))
    for key, w in sorted(wake.items(), key=lambda kv: -(kv[1]['idle_us'] + kv[1]['busy_us'])):
        print('   %-44s %8.0f %8s %9s %8.0f %9s  %-15s %-15s %7.0f' % (
            label(*key), w['n'] / secs,
            '%.2f' % (w['n'] / frames) if frames else 'n/a',
            per(w['idle_us']), w['idle_us'] / w['n'] if w['n'] else 0,
            per(w['busy_us']),
            '/'.join(str(w['i%d' % i]) for i in range(4)),
            '/'.join(str(w['b%d' % i]) for i in range(4)), w['nb'] / secs))
    report_source(wake, frames)
    return good


def report(name, tot, nwin, pcs, gfps, wake=None, bound_ms=37.0):
    print('== %s: %d [rr425] windows, %.1f s' % (name, nwin, tot['dt'] / 1000))
    if not nwin:
        print('   VOID: no [rr425] line in the span')
        return False
    secs = tot['dt'] / 1000
    fps = 1000.0 / mean(gfps) if gfps else None
    frames = fps * secs if fps else None
    print('   fps (1000 / mean G) %s over %d perf lines' %
          ('%.2f' % fps if fps else 'n/a', len(gfps)))
    ret = sum(tot[c] for c, _ in CAUSES)
    print('   %-34s %12s %10s %10s %7s' % ('cause', 'count', '/s', '/frame', 'share'))
    for c, label in CAUSES + SUB + [('it', 'dispatches (it)'), ('x', 'longjmps'),
                                    ('hc', 'lookup_tb_ptr calls'),
                                    ('hm', 'lookup_tb_ptr misses'),
                                    ('ip', 'irq pending at dispatch'),
                                    ('iq', 'irq taken'), ('xr', 'exit_request')]:
        n = tot[c]
        print('   %-34s %12d %10.0f %10s %6.1f%%' % (
            '%s  %s' % (c, label), n, n / secs,
            '%.0f' % (n / frames) if frames else 'n/a',
            100.0 * n / ret if ret else 0))
    ok = True
    print('   checks:')
    chk = [('d <= x', tot['d'] <= tot['x'], 'd=%d x=%d' % (tot['d'], tot['x'])),
           ('m ~= hm', abs(tot['m'] - tot['hm']) <= max(2 * nwin, tot['hm'] // 100),
            'm=%d hm=%d' % (tot['m'], tot['hm'])),
           ('gs+gi+ga <= g', tot['gs'] + tot['gi'] + tot['ga'] <= tot['g'],
            'sum=%d g=%d' % (tot['gs'] + tot['gi'] + tot['ga'], tot['g'])),
           ('pcdrop == 0', tot['pcdrop'] == 0, 'pcdrop=%d' % tot['pcdrop'])]
    for label, good, detail in chk:
        print('     %-16s %s  %s' % (label, 'ok' if good else 'FAIL', detail))
        ok &= good
    # The 1-in-64 timer charges its own get_clock() cost to the sample and
    # scales it by 64: on the Nova's idle loop (~35 ns a dispatch) the timed
    # total came to 4x the wall clock. Say so rather than print it as a cost.
    timed_ok = tot['gapus'] + tot['tbus'] <= 1.05 * tot['dt'] * 1000
    print('     %-16s %s  timed=%.0f s wall=%.0f s' % (
        'timed <= wall', 'ok' if timed_ok else 'INVALID (timing only)',
        (tot['gapus'] + tot['tbus']) / 1e6, secs))
    if frames:
        loop_ms = tot['gapus'] / 1000 / frames
        tb_ms = tot['tbus'] / 1000 / frames
        print('   loop time %.1f ms/frame (sampled gap), TB time %.1f ms/frame;'
              ' profile bound %.1f ms/frame; per return %.2f us' % (
                  loop_ms, tb_ms, bound_ms,
                  tot['gapus'] / ret if ret else 0))
    print('   top (cause, pc, guest bytes at pc): count, share of returns')
    for (c, pc, b), n in pcs.most_common(16):
        print('     %s %s %s %10d %6.2f%%' % (c, pc, b, n, 100.0 * n / ret if ret else 0))
    ok &= report_wake(tot, wake or {}, secs, frames)
    return ok


SELFTEST = """\
09-27 03:00:00.000  1  2 W hakuX   : start
09-27 03:00:02.000  1  2 W hakuX   : [rr425] w=0 dt=2000 it=100 e=60 en=10 es=20 eo=30 et=0 ej=0 esh=5 m=10 o=5 r=5 g=19 gs=4 gi=0 ga=15 x=2 d=1 hc=500 hm=10 ip=7 iq=6 xr=1 gapus=40000 tbus=60000 sn=2 tbn=2 pcdrop=0
09-27 03:00:02.000  1  2 W hakuX   : [rr425pc] w=0 e:80010000:fbc3cc:40 m:80020000:8bff55:10
09-27 03:00:02.500 I/hakuX-perf(1): gfps=20 G:50.0(3.3-340.2) D:16.7
09-27 03:00:04.000  1  2 W hakuX   : [rr425] w=1 dt=2000 it=100 e=60 en=10 es=20 eo=30 et=0 ej=0 esh=5 m=10 o=5 r=5 g=20 gs=4 gi=0 ga=16 x=0 d=0 hc=500 hm=10 ip=7 iq=6 xr=1 gapus=40000 tbus=60000 sn=2 tbn=2 pcdrop=0
09-27 03:00:04.000  1  2 W hakuX   : [rr425pc] w=1 e:80010000:fbc3cc:20 e:80030000:cf0000:20
09-27 03:00:04.000  1  2 W hakuX   : [rr425w] w=1 idlepc=8001b02e idle_us=3000000 busy_us=1000000 n=1100 nb=10 drop=0 30.00:1000:2000000:200000:900/100/0/0:1000/0/0/0:0 33.02:100:1000000:800000:0/0/100/0:0/0/0/100:10
"""


def selftest():
    tot, nwin, pcs, gfps, wake = read(SELFTEST.splitlines(), 0, 1e9)
    assert nwin == 2 and tot['it'] == 200 and tot['e'] == 120, tot
    assert pcs[('e', '80010000', 'fbc3cc')] == 60, pcs
    assert gfps == [50.0]
    assert tot['w_idle_us'] == 3000000 and tot['w_n'] == 1100, tot
    assert wake[(0x33, 0x02)]['n'] == 100 and wake[(0x33, 0x02)]['b3'] == 100, wake
    assert wake[(0x30, 0)]['nb'] == 0 and wake[(0x33, 2)]['nb'] == 10
    # A pending ERROR names the source under any vector; vblank needs the
    # NV2A vector; a timer tick with vblank pending is still the timer's.
    assert source(0x30, 0x44) == source(0x33, 0x46) \
        == 'PGRAPH ERROR (push-buffer callback)'
    assert source(0x33, 0x02) == 'NV2A vblank' and source(0x30, 0x02) == 'PIT timer'
    assert source(0x33, 0x0c).startswith('PGRAPH other') and source(0x33, 1) == 'PFIFO'
    src = by_source(wake)
    assert src['NV2A vblank']['b3'] == 100 and src['PIT timer']['b3'] == 0, src
    ok = report('selftest', tot, nwin, pcs, gfps, wake)
    assert ok
    short = Counter(tot)
    short['w_busy_us'] = 0          # idle + busy falls 25% short of wall
    assert not report('selftest-short', short, nwin, pcs, gfps, wake)
    # 4 s at 20 fps = 80 frames; e = 120 returns -> 1.5 per frame
    bad = Counter(tot)
    bad['d'] = 5
    assert not report('selftest-bad', bad, nwin, pcs, gfps)
    print('selftest ok')


def main(argv):
    lo, hi = 0.0, 1e9
    args = list(argv)
    if args == ['--selftest']:
        return selftest()
    while args and args[0].startswith('--'):
        k, v = args.pop(0), float(args.pop(0))
        if k == '--from':
            lo = v
        elif k == '--to':
            hi = v
    for run in args:
        path = run if os.path.exists(run) else R + run
        if os.path.isdir(path):
            path = os.path.join(path, 'logcat.txt')
        lines = open(path, errors='replace').read().splitlines()
        report(run, *read(lines, lo, hi))


if __name__ == '__main__':
    main(sys.argv[1:])
