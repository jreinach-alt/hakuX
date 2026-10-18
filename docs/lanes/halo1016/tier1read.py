#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-tier1.json.

usage: tier1read.py --arm A=<dir> --arm A2=<dir> --arm IF=<dir> --arm T=<dir> --arm FIT=<dir>
                    [--expect PREDICTION.json]

Written before T or FIT ran. A, A2 and IF are halo1016-vcpu.json's arms (judged by vcpuread.py); T and FIT add
HAKUX_TIER1_THRESHOLD=0 (tier-1 promotion off; xemu_android.cpp reads it after the request env is set and logs
`tier1 threshold: 0`). FIT also carries HAKUX_FLDCW_CHAIN=1 and HAKUX_IBC=1. All on d70f782f45 with
HAKUX_S2T_CVT=1, over vcpuread.py's span and accounting.

Why: tb_request_tier1_promotion() marks a hot block CF_INVALID and leaves it in the qht, whose compare masks
CF_INVALID (tb_lookup_cmp), so the block is found on every lookup, tb_gen_code never runs, and the request is
never consumed (cpu-exec.c:710). Meanwhile tb_add_jump refuses a CF_INVALID destination, the jump cache misses
on it (stale) and goes to the qht, and the main loop drops last_tb after running one, so the goto_tb exits of a
chain it starts are never patched (`gi`). Census B: gi 7.9 k a frame, 380 k per 2 s at resume pc 0x19f23;
`promote` lines name 0x19f23 and 0x1ec3d over and over.

Legs:
  V   T and FIT: `mark cinematic`, `[s2tcvt] on`, `tier1 threshold: 0`, >= V_min_windows [rr425] windows;
      FIT `[fldcw1018] chain=1` and `[ibc507] on=1 layout=ok`; T chain=0 and ibc on=0. A and A2: threshold 64.
  N   as vcpuread.py: |A2 - A| / mean <= N_spread_max, base = mean(A, A2); over it the ms legs are void.
  TM  T's gi per frame <= TM_gi_ratio_max x A's.
  TE  T's ms/f <= TE_msf_ratio_max x base.
  XS  FIT's ms/f <= XS_ratio_max x IF's (what tier-1 off adds to both remedies).
  XE  FIT's ms/f <= XE_msf_ratio_max x base.
  XG  FIT's ms/f <= XG_msf_max (30 fps).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vcpuread import VArm, leg, window_msf  # noqa: E402

ROLES = ('A', 'A2', 'IF', 'T', 'FIT')
WANT = {'A': (0, 0, 64), 'A2': (0, 0, 64), 'IF': (1, 1, 64), 'T': (0, 0, 0), 'FIT': (1, 1, 0)}


def threshold(arm_dir):
    for line in open(os.path.join(arm_dir, 'logcat.txt'), errors='replace'):
        m = re.search(r'tier1 threshold: (\d+)', line)
        if m:
            return int(m.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', action='append', default=[])
    ap.add_argument('--expect')
    o = ap.parse_args()
    e = json.load(open(o.expect))['expect'] if o.expect else {}
    dirs = dict(a.split('=', 1) for a in o.arm)
    arms = {r: VArm(dirs[r]) for r in ROLES if r in dirs}
    acc, bad = {}, {}
    for r, arm in arms.items():
        why = []
        if arm.mark is None:
            why.append('no mark cinematic')
        else:
            acc[r] = arm.account()
        if not arm.s2tcvt:
            why.append('no [s2tcvt] on')
        c, i, th = WANT[r]
        if arm.chain != c:
            why.append('[fldcw1018] chain=%s, want %d' % (arm.chain, c))
        if arm.ibc is None or arm.ibc[0] != i or (i and arm.ibc[1] != 'ok'):
            why.append('[ibc507] %s, want on=%d' % (arm.ibc, i))
        got = threshold(dirs[r])
        if got != th:
            why.append('tier1 threshold %s, want %d' % (got, th))
        if r in acc and acc[r]['windows'] < e.get('V_min_windows', 20):
            why.append('%d [rr425] windows' % acc[r]['windows'])
        if why:
            bad[r] = why

    print('### per arm, per guest frame over the span\n')
    print('| arm | dir | ms/f | it | eo | g | gi | x | hc | gap % |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for r in ROLES:
        if r in acc:
            a = acc[r]
            print('| %s | %s | %.1f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.1f |' % (
                r, arms[r].name, a['msf'], a['it'], a['eo'], a['g'], a['gi'], a['x'], a['hc'], a['gap']))
    print('\n### ms/f per 10-s window from mark+100 (not judged)\n')
    print('| arm | ' + ' | '.join('+%d' % a for a in range(100, 220, 10)) + ' |')
    print('|---' * 13 + '|')
    for r in ROLES:
        if r in arms and arms[r].mark is not None:
            print('| %s | ' % r + ' | '.join('%.1f' % v for v in window_msf(arms[r])) + ' |')

    print('\n### verdict\n')
    for r, why in bad.items():
        print('- V: %s VOID  %s' % (r, '; '.join(why)))
    if 'A' in bad or 'A' not in acc:
        print('- every leg VOID: the base arm is void')
        return 2
    base, spread_ok = acc['A']['msf'], True
    if 'A2' in acc and 'A2' not in bad:
        base = (acc['A']['msf'] + acc['A2']['msf']) / 2.0
        spread = abs(acc['A2']['msf'] - acc['A']['msf']) / base
        spread_ok = spread <= e.get('N_spread_max', 0.08)
        leg('N', spread_ok, 'spread %.3f (<= %.2f); base %.1f' % (spread, e.get('N_spread_max', 0.08), base))
    ok = lambda r: r in acc and r not in bad  # noqa: E731
    if ok('T'):
        q = acc['T']['gi'] / acc['A']['gi'] if acc['A']['gi'] else float('nan')
        leg('TM', q <= e.get('TM_gi_ratio_max', 0.2), 'gi T %.0f vs A %.0f per frame: %.3f (<= %.2f)'
            % (acc['T']['gi'], acc['A']['gi'], q, e.get('TM_gi_ratio_max', 0.2)))
    else:
        leg('TM', None, 'T void or absent')

    def ms(name, r, ref, refname, key, dflt):
        if not ok(r) or ref is None:
            return leg(name, None, '%s or %s void or absent' % (r, refname))
        if not spread_ok:
            return leg(name, None, 'drift over the bound (N)')
        q = acc[r]['msf'] / ref
        return leg(name, q <= e.get(key, dflt), '%s %.1f ms/f = %.3f x %s (<= %.2f)'
                   % (r, acc[r]['msf'], q, refname, e.get(key, dflt)))

    ms('TE', 'T', base, 'base', 'TE_msf_ratio_max', 0.96)
    ms('XS', 'FIT', acc['IF']['msf'] if ok('IF') else None, 'IF', 'XS_ratio_max', 0.97)
    ms('XE', 'FIT', base, 'base', 'XE_msf_ratio_max', 0.85)
    if ok('FIT'):
        leg('XG', acc['FIT']['msf'] <= e.get('XG_msf_max', 33.4), 'FIT %.1f ms/f (<= %.1f)'
            % (acc['FIT']['msf'], e.get('XG_msf_max', 33.4)))
    else:
        leg('XG', None, 'FIT void or absent')
    return 0


if __name__ == '__main__':
    sys.exit(main())
