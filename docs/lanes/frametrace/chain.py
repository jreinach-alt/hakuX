#!/usr/bin/env python3
"""Re-read a frametrace capture with the period-late rule, and close the chain.

    chain.py <result dir or captures/<id>> [...] [--delay 20]

Why: profile.h's rule called a frame on time when it saw no more VBLANKs
than the guest asked for. nv2a.c's adaptive VBLANK deferral holds a VBLANK
until the flip, so a 60 Hz guest flipping every 22 ms sees 1 or 2 VBLANKs a
flip and the rule read 70% of Simpsons' frames `vsync`. The rule now also
calls a frame late when P > 1.05 x the deadline (profile.h, session 4);
captures made before that carry the old verdict in their `cls` column.

What it prints, over ftread.py's window:
  0. the port check: this file's copy of hakux_ft_attribute, run with the
     OLD lateness on every frame, must give the device's `cls` on >= 99.5%
     of frames, or nothing below is printed (the port is wrong)
  1. the grid test: share of periods within 1.5 ms of a whole number of
     VBLANK periods (a vsync-locked guest is near 100%; a deferred grid is
     not), and the [vblphase] deferral counts from the logcat
  2. pacemakers under the period-late rule, all frames and late frames
  3. the vCPU's chain per frame (guest work + idle + queue + each wait)
     against P: what fraction of the period each part is, and the residue
  4. per-frame correlations of P with each part (which part moves the pace)
"""
import argparse
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ftread  # noqa: E402

W = ftread.W            # bql pfl pgl halt idle fence submit rthr dl oth
CLS = ftread.CLS


def sub0(a, b):
    return a - b if a > b else 0


def attribute(f, period_late):
    """profile.h's hakux_ft_attribute on one CSV row (us). Returns (cls, late)."""
    D = f['vbp'] * (f['ireq'] or 1)
    gidle = 0 if f['gidle'] is None or f['gidle'] < 0 else f['gidle']
    halt = f['v_halt']
    work = sub0(f['v_run'], sub0(gidle, halt)) + f['v_rq']
    extra = sub0(f['lockw'], f['v_pfl'])
    named = extra + sum(f['v_' + w] for w in W)
    g = max(gidle, halt)
    ch = dict.fromkeys(CLS, 0)
    ch['run'] = work
    ch['block'] = f['vh_run'] + f['vh_wait']
    ch['bgpu'] = f['vh_gpu'] + f['v_fence'] + f['v_dl']
    ch['rsub'] = f['vh_rnd'] + f['v_submit'] + f['v_rthr']
    ch['unattr'] = (f['vh_unk'] + f['vh_idle'] + extra + f['v_oth'] +
                    sub0(f['v_blk'], named))
    if g:
        if f['gpu'] * 10 >= f['P'] * 9:
            ch['gpu'] += g
        else:
            pnamed = sum(f['p_' + w] for w in W if w != 'idle')
            pfence = f['p_fence'] + f['p_dl']
            prend = f['p_submit'] + f['p_rthr']
            punn = sub0(f['p_blk'], f['pidle'] + pnamed)
            pwork = sub0(f['P'], f['pidle'] + pnamed + f['p_rq'] + punn)
            s = [(pfence, 'gpu'), (prend, 'rsub'), (pwork, 'pgraph'), (punn, 'unattr')]
            k = 0
            for i in range(1, 4):
                if s[i][0] > s[k][0]:
                    k = i
            if s[k][0] >= f['pidle'] and s[k][0] > 0:
                ch[s[k][1]] += g
            else:
                ch['unattr'] += g
    best = 'unattr'
    for c in CLS[2:]:           # BLK_GPU .. UNATTR, in the enum's order
        if ch[c] > ch[best]:
            best = c
    if period_late:
        late = (bool(f['ireq']) and f['vb'] > f['ireq']) or (D and f['P'] * 20 > D * 21)
    else:
        late = f['vb'] > f['ireq'] if f['ireq'] else f['P'] * 20 > D * 21
    if not late:
        return 'vsync', False
    if work > D:
        return 'run', True
    return (best if ch[best] else 'unattr'), True


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if not sa or not sb:
        return float('nan')
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def window(d, delay):
    csvs, logs = ftread.find_files(d, [])
    frames = []
    for p in csvs:
        frames += ftread.read_frames(p)
    anchors, pace, mark, _, _ = ftread.read_logs(logs, d)
    how = ftread.wall_of(frames, anchors, pace)
    if mark is None or not how:
        return None, logs
    return [f for f in frames if f['wall'] >= mark + delay], logs


def vblphase(logs, t0):
    n = de = un = 0
    for p in set(logs):
        if p.endswith('.gz'):
            continue
        for line in ftread.opentext(p):
            ts = ftread.TS.match(line)
            if not ts or ftread.secs(*ts.groups()[2:]) < t0:
                continue
            m = re.search(r'vblphase n=(\d+) .* def\(n=(\d+) .* unl=(\d+)', line)
            if m:
                n += int(m.group(1))
                de += int(m.group(2))
                un += int(m.group(3))
    return n, de, un


def report(d, a):
    name = os.path.basename(os.path.normpath(d))
    win, logs = window(d, a.delay)
    print('## %s\n' % name)
    if not win:
        print('VOID: no gameplay window\n')
        return
    n = len(win)

    # 0. the port check
    agree = sum(1 for f in win if attribute(f, False)[0] == f['cls'])
    print('port check: %d of %d frames (%.2f%%) match the device cls under the old rule'
          % (agree, n, 100.0 * agree / n))
    if agree < 0.995 * n:
        print('PORT WRONG: stop\n')
        return

    # 1. the grid
    vbp = sorted(f['vbp'] for f in win)[n // 2]
    on = 0
    for f in win:
        k = max(1, round(f['P'] / vbp))
        if abs(f['P'] - k * vbp) <= 1500:
            on += 1
    full = os.path.join(a.results, name, 'logcat.txt')     # an archived capture keeps only ft lines
    vn, vde, vun = vblphase(logs + ([full] if os.path.exists(full) else []), win[0]['wall'])
    print('\n### 1. Is the guest on the VBLANK grid?\n')
    print('VBLANK period (median vbp) %.2f ms; periods within 1.5 ms of k x vbp: %.1f%%'
          % (vbp / 1000.0, 100.0 * on / n))
    if vn:
        print('[vblphase] in the window: %d VBLANKs, %d deferred (%.0f%%), %d in unlock mode (%.0f%%)'
              % (vn, vde, 100.0 * vde / vn, vun, 100.0 * vun / vn))

    # 2. pacemakers, period-late
    cl = [attribute(f, True) for f in win]
    late = [c for c, l in cl if l]
    print('\n### 2. Pacemaker with the period-late rule\n')
    rows = []
    for c in CLS:
        na = sum(1 for x, _ in cl if x == c)
        nl = sum(1 for x in late if x == c)
        nold = sum(1 for f in win if f['cls'] == c)
        if na or nold:
            rows.append([c, '%.1f%%' % (100.0 * nold / n), '%.1f%%' % (100.0 * na / n),
                         '%.1f%%' % (100.0 * nl / len(late)) if late else '-'])
    print(ftread.table(rows, ['class', 'all (device, old rule)', 'all (period-late)',
                              'late (period-late)']))
    print('\nlate: %d of %d (%.1f%%) against %.1f%% under the old rule'
          % (len(late), n, 100.0 * len(late) / n,
             100.0 * sum(1 for f in win if f['late']) / n))
    # delivery against the deadline. The CSV's slack is blind where the
    # deferral holds the VBLANK to the flip (present and flip coincide), so
    # read lateness as P - D directly.
    over = [(f['P'] - f['vbp'] * (f['ireq'] or 1)) for f in win]
    print('P - D, ms: p5 %s p50 %s p95 %s p99 %s; deadline D = %s ms (ireq %d)'
          % (ftread.ms(ftread.pct(over, 5)), ftread.ms(ftread.pct(over, 50)),
             ftread.ms(ftread.pct(over, 95)), ftread.ms(ftread.pct(over, 99)),
             ftread.ms(vbp * (win[-1]['ireq'] or 1)), win[-1]['ireq'] or 1))

    # 3. the vCPU's chain
    parts = {
        'guest on-CPU (work + idle loop)': lambda f: f['v_run'],
        'run queue': lambda f: f['v_rq'],
        'DMA_PUT pfifo.lock (lockw)': lambda f: f['lockw'],
        'BQL': lambda f: f['v_bql'],
        'pgraph.lock': lambda f: f['v_pgl'],
        'halt': lambda f: f['v_halt'],
        'other named waits': lambda f: sum(f['v_' + w] for w in ('idle', 'fence', 'submit', 'rthr', 'dl', 'oth')),
        'blocked, no named wait': lambda f: sub0(f['v_blk'], f['lockw'] + sum(f['v_' + w] for w in W) - f['v_pfl']),
    }
    P = [f['P'] for f in win]
    mP = sum(P) / n
    print('\n### 3. The vCPU chain, ms per frame (mean), against P = %.2f\n' % (mP / 1000.0))
    rows = []
    tot = 0
    for k, fn in parts.items():
        v = [fn(f) for f in win]
        m = sum(v) / n
        tot += m
        rows.append([k, '%.2f' % (m / 1000.0), '%.1f%%' % (100.0 * m / mP),
                     '%.2f' % corr(P, v) if m > 0 else '-'])
    rows.append(['sum', '%.2f' % (tot / 1000.0), '%.1f%%' % (100.0 * tot / mP), ''])
    print(ftread.table(rows, ['part', 'ms/frame', 'of P', 'corr with P']))

    pf = {
        'PFIFO on-CPU': lambda f: f['p_run'],
        'PFIFO idle (waiting for work)': lambda f: f['pidle'],
        'PFIFO blocked, no hooked wait': lambda f: sub0(f['p_blk'], f['pidle'] + sum(f['p_' + w] for w in W if w != 'idle')),
        'GPU execution (main CBs, timestamps)': lambda f: f['gpu'],
    }
    rows = []
    lw = [f['lockw'] for f in win]
    for k, fn in pf.items():
        v = [fn(f) for f in win]
        m = sum(v) / n
        rows.append([k, '%.2f' % (m / 1000.0), '%.2f' % corr(P, v), '%.2f' % corr(lw, v)])
    print()
    print(ftread.table(rows, ['other side', 'ms/frame', 'corr with P', 'corr with lockw']))
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--delay', type=int, default=20)
    ap.add_argument('--results', default=os.path.expanduser('~/hakux-work/dispatch/results'),
                    help='where the full logcat of an archived capture is found')
    a = ap.parse_args()
    for d in a.dirs:
        report(d, a)


if __name__ == '__main__':
    main()
