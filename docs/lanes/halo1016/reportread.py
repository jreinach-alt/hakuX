#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-reports.json.

usage: reportread.py --arm RT=<dir> --arm RC=<dir> [--arm A=<vcpu A dir>] [--expect PREDICTION.json]

Written before RT or RC ran. Both arms run the same binary with HAKUX_S2T_CVT=1 and HAKUX_REPORT_TRACE=1
(reports.c: one record per GET_REPORT, summed per 2 s in `[rtrace] w` lines); RC adds HAKUX_REPORT_CATCHUP=1.
A, if given, is halo1016-vcpu.json's arm A (same code with both switches off) and only prices the trace.

Why: the plateau's two hottest TB entries are one loop. 0x63482 calls D3D's 0x1810f0 (three arguments,
`ret 0xc`) while it returns 0x88760828, which 0x1810f0 does at 0x18111b when the 16-byte record's last word is
still -1: a visibility-test result poll. So the "vCPU bound" of the heavy shots is the guest spinning on an
occlusion report. A report is written only at a finish (pgraph_vk_finish's tail). At a caught-up FIFO the
STALLED finish runs only with a command buffer open and a draw since the last one
(pgraph_vk_process_pending_reports), so a GET_REPORT the guest kicks after that finish waits for the next finish
of any kind, while the guest spins. HAKUX_REPORT_CATCHUP=1 writes such a report at the catch-up.

All values over [mark+131, mark+191] (vcpuread.py's span), per guest frame where so labelled. The trace's
histogram edges are 0.25 0.5 1 2 4 8 16.7 33.3 66.7 ms: q2e is GET_REPORT queued (the PFIFO ran the method) to
the finish handing it to the write, q2w to the write.

Legs:
  V   RT and RC: `mark cinematic`, `[s2tcvt] on`, >= V_min_windows [rr425] windows, >= V_min_rtrace `[rtrace] w`
      windows with mode=sync, and `[rcatch1018] off` (RT) / `on` (RC). A failure voids that arm's legs.
  Q   RT: the spin's share of [tpc787] sampled TB time (entry pcs 0x63482, 0x63492, 0x1810f0, 0x18111b)
      >= Q_spin_share_min. The poll is the heavy shots' bound.
  HS  RT: share of reports with q2e >= 2 ms >= HS_share_min. Reports wait in the queue for a finish.
  HG  RT: (share with q2w >= 2 ms) - (share with q2e >= 2 ms) >= HG_share_min. They wait on the GPU after
      the handoff.
  HB  RT: share with q2w < 1 ms >= HB_share_min. The report lands fast once the PFIFO reaches it; the spin
      is upstream (the PFIFO's backlog or the guest's kick).
  RM  RC: share with q2e >= 2 ms <= RM_share_max, and >= 1 `[rcatch1018] w` catch-up finish per frame.
  RS  RC's spin share <= RS_ratio_max x RT's.
  RE  RC's ms/f <= RE_msf_ratio_max x RT's.
  RG  RC's ms/f <= RG_msf_max (30 fps).
  TR  (A given) RT's ms/f <= TR_ratio_max x A's: the trace's cost.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cineread import ts  # noqa: E402
from vcpuread import VArm, leg, window_msf  # noqa: E402

SPAN = (131.0, 191.0)
SPIN = {'00063482', '00063492', '001810f0', '0018111b'}
TPE = re.compile(r' ([0-9a-f]{8}):([0-9a-f]{6}):(\d+):(\d+)')
NB = 10


def hist(s):
    v = [int(x) for x in s.split(',')]
    return v + [0] * (NB - len(v))


def read_trace(d, mark):
    """Sum the [rtrace] w windows, [rcatch1018] lines and [tpc787] samples inside the span."""
    t = {'windows': 0, 'modes': set(), 'n': 0, 'e': [0] * NB, 'f': [0] * NB, 'w': [0] * NB,
         'armed': 0, 'late': 0, 'flipb4w': 0, 'noflip': 0, 'reuseb4w': 0, 'catch': None,
         'open': 0, 'closed': 0, 'tpc_us': 0, 'spin_us': 0}
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for line in f:
            m = re.search(r'\[rcatch1018\] (on|off) ', line)
            if m:
                t['catch'] = m.group(1)
                continue
            if '[rtrace] w ' not in line and '[rcatch1018] w ' not in line and '[tpc787]' not in line:
                continue
            s = ts(line)
            if s is None or mark is None or not (SPAN[0] < s - mark <= SPAN[1]):
                continue
            if '[rtrace] w ' in line:
                t['windows'] += 1
                t['modes'].add(re.search(r'mode=(\w+)', line).group(1))
                t['n'] += int(re.search(r' n=(\d+)', line).group(1))
                for k in ('e', 'f', 'w'):
                    h = hist(re.search(r' %s=([\d,]+)' % k, line).group(1))
                    t[k] = [a + b for a, b in zip(t[k], h)]
                for k in ('armed', 'late', 'flipb4w', 'noflip', 'reuseb4w'):
                    t[k] += int(re.search(r' %s=(\d+)' % k, line).group(1))
            elif '[rcatch1018] w ' in line:
                t['open'] += int(re.search(r'open=(\d+)', line).group(1))
                t['closed'] += int(re.search(r'closed=(\d+)', line).group(1))
            else:
                for pc, b, us, n in TPE.findall(line):
                    t['tpc_us'] += int(us)
                    if pc in SPIN:
                        t['spin_us'] += int(us)
    n = max(t['n'], 1)
    t['e2'] = sum(t['e'][3:]) / n        # q2e >= 2 ms
    t['w2'] = sum(t['w'][3:]) / n        # q2w >= 2 ms
    t['w1'] = sum(t['w'][:2 + 1]) / n    # q2w < 1 ms: buckets <0.25, <0.5, <1
    t['spin'] = t['spin_us'] / t['tpc_us'] if t['tpc_us'] else float('nan')
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', action='append', default=[])
    ap.add_argument('--expect')
    o = ap.parse_args()
    e = json.load(open(o.expect))['expect'] if o.expect else {}
    dirs = dict(a.split('=', 1) for a in o.arm)
    arms = {r: VArm(dirs[r]) for r in ('RT', 'RC', 'A') if r in dirs}
    acc, tr, bad = {}, {}, {}
    for r, arm in arms.items():
        why = []
        if arm.mark is None:
            why.append('no mark cinematic')
        else:
            acc[r] = arm.account()
            tr[r] = read_trace(dirs[r], arm.mark)
        if not arm.s2tcvt:
            why.append('no [s2tcvt] on')
        if r in acc and acc[r]['windows'] < e.get('V_min_windows', 20):
            why.append('%d [rr425] windows' % acc[r]['windows'])
        if r in ('RT', 'RC') and r in tr:
            if tr[r]['windows'] < e.get('V_min_rtrace', 20) or tr[r]['modes'] != {'sync'}:
                why.append('%d [rtrace] w windows, modes %s' % (tr[r]['windows'], sorted(tr[r]['modes'])))
            want = 'on' if r == 'RC' else 'off'
            if tr[r]['catch'] != want:
                why.append('[rcatch1018] %s, want %s' % (tr[r]['catch'], want))
        if why:
            bad[r] = why

    print('### per arm over [mark+131, mark+191]\n')
    print('| arm | dir | ms/f | frames | reports/f | armed | q2e >= 2 ms | q2w >= 2 ms | q2w < 1 ms | late | '
          'flip before write | spin share of TB time | catch-up finishes/f (open, closed) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in ('RT', 'RC', 'A'):
        if r not in acc:
            continue
        a, t = acc[r], tr[r]
        fr = max(a['frames'], 1)
        print('| %s | %s | %.1f | %d | %.2f | %.2f | %.3f | %.3f | %.3f | %d | %d | %.3f | %.2f (%.2f, %.2f) |' % (
            r, arms[r].name, a['msf'], a['frames'], t['n'] / fr, t['armed'] / max(t['n'], 1), t['e2'], t['w2'],
            t['w1'], t['late'], t['flipb4w'], t['spin'], (t['open'] + t['closed']) / fr, t['open'] / fr,
            t['closed'] / fr))
    print('\n### histograms (counts over the span; edges 0.25 0.5 1 2 4 8 16.7 33.3 66.7 ms)\n')
    for r in ('RT', 'RC'):
        if r in tr:
            for k in ('e', 'f', 'w'):
                print('- %s q2%s: %s' % (r, k, ','.join(str(x) for x in tr[r][k])))
    print('\n### ms/f per 10-s window from mark+100 (not judged)\n')
    print('| arm | ' + ' | '.join('+%d' % x for x in range(100, 220, 10)) + ' |')
    print('|---' * 13 + '|')
    for r in ('RT', 'RC', 'A'):
        if r in arms and arms[r].mark is not None:
            print('| %s | ' % r + ' | '.join('%.1f' % v for v in window_msf(arms[r])) + ' |')

    print('\n### verdict\n')
    for r, why in bad.items():
        print('- V: %s VOID  %s' % (r, '; '.join(why)))
    ok = lambda r: r in acc and r not in bad  # noqa: E731
    if ok('RT'):
        t = tr['RT']
        leg('Q', t['spin'] >= e.get('Q_spin_share_min', 0.25), 'RT spin share %.3f (>= %.2f)'
            % (t['spin'], e.get('Q_spin_share_min', 0.25)))
        leg('HS', t['e2'] >= e.get('HS_share_min', 0.3), 'RT q2e >= 2 ms: %.3f of %d reports (>= %.2f)'
            % (t['e2'], t['n'], e.get('HS_share_min', 0.3)))
        leg('HG', t['w2'] - t['e2'] >= e.get('HG_share_min', 0.3), 'RT q2w >= 2 ms %.3f - q2e >= 2 ms %.3f = %.3f '
            '(>= %.2f)' % (t['w2'], t['e2'], t['w2'] - t['e2'], e.get('HG_share_min', 0.3)))
        leg('HB', t['w1'] >= e.get('HB_share_min', 0.7), 'RT q2w < 1 ms: %.3f (>= %.2f)'
            % (t['w1'], e.get('HB_share_min', 0.7)))
    else:
        for k in ('Q', 'HS', 'HG', 'HB'):
            leg(k, None, 'RT void or absent')
    if ok('RC'):
        t, fr = tr['RC'], max(acc['RC']['frames'], 1)
        cf = (t['open'] + t['closed']) / fr
        leg('RM', t['e2'] <= e.get('RM_share_max', 0.1) and cf >= 1.0,
            'RC q2e >= 2 ms: %.3f (<= %.2f); catch-up finishes %.2f/f (>= 1)' % (t['e2'], e.get('RM_share_max', 0.1), cf))
    else:
        leg('RM', None, 'RC void or absent')
    if ok('RC') and ok('RT'):
        q = tr['RC']['spin'] / tr['RT']['spin'] if tr['RT']['spin'] else float('nan')
        leg('RS', q <= e.get('RS_ratio_max', 0.5), 'spin share RC %.3f vs RT %.3f: %.3f (<= %.2f)'
            % (tr['RC']['spin'], tr['RT']['spin'], q, e.get('RS_ratio_max', 0.5)))
        q = acc['RC']['msf'] / acc['RT']['msf']
        leg('RE', q <= e.get('RE_msf_ratio_max', 0.9), 'RC %.1f ms/f = %.3f x RT %.1f (<= %.2f)'
            % (acc['RC']['msf'], q, acc['RT']['msf'], e.get('RE_msf_ratio_max', 0.9)))
    else:
        leg('RS', None, 'RC or RT void or absent')
        leg('RE', None, 'RC or RT void or absent')
    if ok('RC'):
        leg('RG', acc['RC']['msf'] <= e.get('RG_msf_max', 33.4), 'RC %.1f ms/f (<= %.1f)'
            % (acc['RC']['msf'], e.get('RG_msf_max', 33.4)))
    else:
        leg('RG', None, 'RC void or absent')
    if ok('RT') and ok('A'):
        q = acc['RT']['msf'] / acc['A']['msf']
        leg('TR', q <= e.get('TR_ratio_max', 1.05), 'RT %.1f ms/f = %.3f x A %.1f (<= %.2f)'
            % (acc['RT']['msf'], q, acc['A']['msf'], e.get('TR_ratio_max', 1.05)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
