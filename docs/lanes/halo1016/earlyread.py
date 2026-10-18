#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-early.json.

usage: earlyread.py --arm B=<dir> --arm E=<dir> [--arm EIF=<dir>] [--arm S=<dir>] [--arm EV=<dir>]
                    [--arm BV=<dir>] [--arm RT=<reports RT dir>] [--expect PREDICTION.json]

Written before any of these arms ran. One binary (08fd920b5c). Every arm runs with HAKUX_S2T_CVT=1 and
HAKUX_REPORT_TRACE=1, on the app's default report path: "Fast renderer paths" sets HAKUX_REPORT_ASYNC=1, so
`[rtrace] w` lines say mode=async (halo1016-reports.json assumed sync and voided both its arms on that).
  B    the base.
  E    + HAKUX_REPORT_EARLY=1: an armed GET_REPORT whose offset has a count is answered when it is queued,
       with the count the last GET_REPORT at that offset was written with.
  EIF  E + HAKUX_FLDCW_CHAIN=1 + HAKUX_IBC=1 (the vCPU arms' IF).
  S    B + HAKUX_REPORT_SUBMIT=2000: finish at an armed GET_REPORT 2 ms or more after the last finish.
  EV, BV  E and B with --frames-every, for the pictures; not timed, V only.
RT (halo1016-reports.json's, 7da5534b6b) is printed beside B, not judged.

Why: the RT arm traced 544 armed GET_REPORTs a frame over the span. Every one waited >= 2 ms to be handed to
the reader (q2e median 8-16.7 ms) and >= 2 ms to be written (q2w mostly 16.7-33.3 ms): each waits for the
frame's last finish and then for the GPU to run that whole command buffer, while the guest spins on it in
0x63482 -> D3D 0x1810f0 (29% of sampled TB time). The vCPU remedies removed 9 ms/f of work and the spin took
it back. E removes the wait; S shortens it.

All values over [mark+131, mark+191] (vcpuread.py's span), per guest frame where so labelled.

Legs:
  V    every arm: `mark cinematic`, `[s2tcvt] on`, >= V_min_windows [rr425] windows, >= V_min_rtrace
       `[rtrace] w` windows all mode=async, `[rearly1018] early=` 1 in E, EIF, EV and 0 elsewhere,
       `submit_us=` 2000 in S and 0 elsewhere; EIF: `[fldcw1018] chain=1` and `[ibc507] on=1 layout=ok`.
       A failure voids the legs that read that arm.
  EA   E: early / (early + cold) over the span's `[rearly1018] w` windows >= EA_share_min.
  EP   E: the spin's share of [tpc787] sampled TB time <= EP_spin_max.
  EM   E ms/f <= EM_ratio_max x B's.
  EG   E ms/f <= G_msf_max (30 fps).
  XM   EIF ms/f <= XM_ratio_max x E's: with the poll gone, the vCPU savings become frame time.
  XG   EIF ms/f <= G_msf_max.
  SQ   S: share of reports with q2w >= 16.7 ms <= SQ_ratio_max x B's.
  SM   S ms/f <= SM_ratio_max x B's.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cineread import ts  # noqa: E402
from reportread import SPAN, read_trace  # noqa: E402
from vcpuread import VArm, leg, window_msf  # noqa: E402

ORDER = ('B', 'E', 'EIF', 'S', 'EV', 'BV', 'RT')
EARLY = {'E', 'EIF', 'EV'}


def read_early(d, mark):
    """The `[rearly1018]` settings line and the span's window counts."""
    t = {'early_on': None, 'submit_us': None, 'early': 0, 'cold': 0, 'unarmed': 0, 'submit': 0, 'windows': 0}
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for line in f:
            if '[rearly1018]' not in line:
                continue
            m = re.search(r'\[rearly1018\] early=(\d+) submit_us=(\d+)', line)
            if m:
                t['early_on'], t['submit_us'] = int(m.group(1)), int(m.group(2))
                continue
            if '[rearly1018] w ' not in line:
                continue
            s = ts(line)
            if s is None or mark is None or not (SPAN[0] < s - mark <= SPAN[1]):
                continue
            t['windows'] += 1
            for k in ('early', 'cold', 'unarmed', 'submit'):
                t[k] += int(re.search(r' %s=(\d+)' % k, line).group(1))
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', action='append', default=[])
    ap.add_argument('--expect')
    o = ap.parse_args()
    e = json.load(open(o.expect))['expect'] if o.expect else {}
    dirs = dict(a.split('=', 1) for a in o.arm)
    arms = {r: VArm(dirs[r]) for r in ORDER if r in dirs}
    acc, tr, er, bad = {}, {}, {}, {}
    for r, arm in arms.items():
        why = []
        if arm.mark is None:
            why.append('no mark cinematic')
        else:
            acc[r] = arm.account()
            tr[r] = read_trace(dirs[r], arm.mark)
            er[r] = read_early(dirs[r], arm.mark)
        if r == 'RT':
            continue
        if not arm.s2tcvt:
            why.append('no [s2tcvt] on')
        if r in acc and acc[r]['windows'] < e.get('V_min_windows', 20):
            why.append('%d [rr425] windows' % acc[r]['windows'])
        if r in tr:
            if tr[r]['windows'] < e.get('V_min_rtrace', 20) or tr[r]['modes'] != {'async'}:
                why.append('%d [rtrace] w windows, modes %s' % (tr[r]['windows'], sorted(tr[r]['modes'])))
            want_e, want_s = int(r in EARLY), 2000 if r == 'S' else 0
            if er[r]['early_on'] != want_e or er[r]['submit_us'] != want_s:
                why.append('[rearly1018] early=%s submit_us=%s, want %d %d'
                           % (er[r]['early_on'], er[r]['submit_us'], want_e, want_s))
        if r == 'EIF':
            if arm.chain != 1:
                why.append('[fldcw1018] chain=%s, want 1' % arm.chain)
            if arm.ibc != (1, 'ok'):
                why.append('[ibc507] %s, want on=1 layout=ok' % (arm.ibc,))
        if why:
            bad[r] = why

    def w16(r):
        t = tr[r]
        return sum(t['w'][7:]) / max(t['n'], 1)

    print('### per arm over [mark+%d, mark+%d]\n' % SPAN)
    print('| arm | dir | ms/f | frames | reports/f | early share | cold/f | submits/f | q2w >= 16.7 ms | '
          'spin share of TB time |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for r in ORDER:
        if r not in acc:
            continue
        a, t, x = acc[r], tr[r], er[r]
        fr = max(a['frames'], 1)
        ec = x['early'] + x['cold']
        print('| %s | %s | %.1f | %d | %.2f | %s | %.2f | %.2f | %.3f | %.3f |' % (
            r, arms[r].name, a['msf'], a['frames'], t['n'] / fr,
            '%.3f' % (x['early'] / ec) if ec else '-', x['cold'] / fr, x['submit'] / fr, w16(r), t['spin']))
    print('\n### histograms (counts over the span; edges 0.25 0.5 1 2 4 8 16.7 33.3 66.7 ms)\n')
    for r in ORDER:
        if r in tr:
            for k in ('e', 'w'):
                print('- %s q2%s: %s' % (r, k, ','.join(str(v) for v in tr[r][k])))
    print('\n### ms/f per 10-s window from mark+100 (not judged)\n')
    print('| arm | ' + ' | '.join('+%d' % v for v in range(100, 220, 10)) + ' |')
    print('|---' * 13 + '|')
    for r in ORDER:
        if r in arms and arms[r].mark is not None:
            print('| %s | ' % r + ' | '.join('%.1f' % v for v in window_msf(arms[r])) + ' |')

    print('\n### verdict\n')
    for r, why in bad.items():
        print('- V: %s VOID  %s' % (r, '; '.join(why)))
    ok = lambda r: r in acc and r not in bad and r != 'RT'  # noqa: E731
    g = e.get('G_msf_max', 33.4)
    if ok('E'):
        x = er['E']
        ec = x['early'] + x['cold']
        share = x['early'] / ec if ec else 0.0
        leg('EA', share >= e.get('EA_share_min', 0.9), 'E early %d of %d armed (%.3f, >= %.2f)'
            % (x['early'], ec, share, e.get('EA_share_min', 0.9)))
        leg('EP', tr['E']['spin'] <= e.get('EP_spin_max', 0.05), 'E spin share %.3f (<= %.2f)'
            % (tr['E']['spin'], e.get('EP_spin_max', 0.05)))
        leg('EG', acc['E']['msf'] <= g, 'E %.1f ms/f (<= %.1f)' % (acc['E']['msf'], g))
    else:
        for k in ('EA', 'EP', 'EG'):
            leg(k, None, 'E void or absent')
    if ok('E') and ok('B'):
        q = acc['E']['msf'] / acc['B']['msf']
        leg('EM', q <= e.get('EM_ratio_max', 0.85), 'E %.1f ms/f = %.3f x B %.1f (<= %.2f)'
            % (acc['E']['msf'], q, acc['B']['msf'], e.get('EM_ratio_max', 0.85)))
    else:
        leg('EM', None, 'E or B void or absent')
    if ok('EIF') and ok('E'):
        q = acc['EIF']['msf'] / acc['E']['msf']
        leg('XM', q <= e.get('XM_ratio_max', 0.95), 'EIF %.1f ms/f = %.3f x E %.1f (<= %.2f)'
            % (acc['EIF']['msf'], q, acc['E']['msf'], e.get('XM_ratio_max', 0.95)))
    else:
        leg('XM', None, 'EIF or E void or absent')
    if ok('EIF'):
        leg('XG', acc['EIF']['msf'] <= g, 'EIF %.1f ms/f (<= %.1f)' % (acc['EIF']['msf'], g))
    else:
        leg('XG', None, 'EIF void or absent')
    if ok('S') and ok('B'):
        sb, ss = w16('B'), w16('S')
        q = ss / sb if sb else float('nan')
        leg('SQ', q <= e.get('SQ_ratio_max', 0.5), 'q2w >= 16.7 ms: S %.3f vs B %.3f = %.3f (<= %.2f)'
            % (ss, sb, q, e.get('SQ_ratio_max', 0.5)))
        q = acc['S']['msf'] / acc['B']['msf']
        leg('SM', q <= e.get('SM_ratio_max', 0.9), 'S %.1f ms/f = %.3f x B %.1f (<= %.2f)'
            % (acc['S']['msf'], q, acc['B']['msf'], e.get('SM_ratio_max', 0.9)))
    else:
        leg('SQ', None, 'S or B void or absent')
        leg('SM', None, 'S or B void or absent')
    return 0


if __name__ == '__main__':
    sys.exit(main())
