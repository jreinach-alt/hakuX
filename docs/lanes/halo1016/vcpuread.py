#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-vcpu.json.

usage: vcpuread.py --arm A=<dir> --arm F=<dir> --arm I=<dir> --arm IF=<dir>
                   [--arm A2=<dir>] [--expect PREDICTION.json]

Written before any arm ran. All arms are perflog soaks of the halo-cinematic
route on one binary with HAKUX_S2T_CVT=1, HAKUX_FRAMETRACE=1 and
HAKUX_PROBE_WAITS=1 (census B's configuration, where the cvt downloads are gone
and the vCPU bounds the heavy shots):
  A   that alone (the base); A2 the same, queued last, for drift
  F   + HAKUX_FLDCW_CHAIN=1 (R2: an FLDCW that keeps the precision bit stays
      in its TB; translate.c gen_fldcw_chain)
  I   + HAKUX_IBC=1 (#507's inline jump-cache probe, parked off by default)
  IF  + both

The span is censusread.py's: [mark+131 s, mark+191 s]. ms per guest frame is
Census.msf (sum of pace ms / sum of guest frames over pace lines in the span).
[rr425] windows count if their line's time t has span0 < t <= span1 + 2; eo
at 0x1ec3a is the sum of the window's [rr425pc] `e:0001ec3a` entries.

Legs (thresholds from the prediction's expect block):
  V   every arm: `mark cinematic`; `[s2tcvt] on`; `[fldcw1018] chain=1` in F
      and IF, `chain=0` in A, A2 and I; `[ibc507] on=1 layout=ok` in I and IF,
      `on=0` in A, A2 and F; >= V_min_windows [rr425] windows in the span;
      Finish sd per frame over the span <= V_sd_max (the cvt route is on). A
      failing arm voids the legs that read it, not the others.
  N   drift: with A2, |A2 - A| / mean(A, A2) <= N_spread_max. The base is
      mean(A, A2) (A alone without A2). Over the bound, the ms legs are void.
  FL  the precision bit rarely flips: A's [fldcw1018] flips / n (whole run)
      <= FL_flip_share_max.
  FM  F's mechanism: F's eo at 0x1ec3a over the span <= FM_eo_ratio_max x A's
      (per guest frame).
  FE  F's effect: F's ms/f <= FE_msf_ratio_max x base.
  IM  I's mechanism: I's helper_lookup_tb_ptr calls (hc) per guest frame <=
      IM_hc_ratio_max x A's.
  IE  I's effect: I's ms/f <= IE_msf_ratio_max x base.
  BE  both: IF's ms/f <= BE_msf_ratio_max x base.
  G   the bar: IF's ms/f over the span <= G_msf_max (30 fps).

Printed whatever the verdict: per-arm table (ms/f, Finish sd/f, dispatched,
eo 0x1ec3a, g, gi, x, hc per guest frame, loop gap share, fldcw flips/n) and
per-window ms/f across [mark+100, mark+220].
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from censusread import Census, SPAN  # noqa: E402
from cineread import ts  # noqa: E402

ROLES = ('A', 'F', 'I', 'IF', 'A2')
WANT = {'A': (0, 0), 'A2': (0, 0), 'F': (1, 0), 'I': (0, 1), 'IF': (1, 1)}
PCE = re.compile(r'(\w):([0-9a-f]+):([0-9a-f]+):(\d+)')
FLD = re.compile(r'\[fldcw1018\] n=(\d+) flips=(\d+)')


class VArm(Census):
    def read_log(self, path):
        super().read_log(path)
        self.rr = []        # (t, {field: n}, eo_1ec3a)
        self.chain = None
        self.ibc = None
        self.fld = []       # (t, n, flips)
        pcs = {}
        for line in open(path, errors='replace'):
            if '[fldcw1018] chain=' in line and self.chain is None:
                self.chain = int(re.search(r'chain=(\d)', line).group(1))
            elif '[ibc507] on=' in line and self.ibc is None:
                m = re.search(r'on=(\d) layout=(\w+)', line)
                self.ibc = (int(m.group(1)), m.group(2))
            elif '[fldcw1018] n=' in line:
                m = FLD.search(line)
                self.fld.append((ts(line), int(m.group(1)), int(m.group(2))))
            elif '[rr425pc] ' in line:
                w = re.search(r'w=(\d+)', line).group(1)
                pcs[w] = sum(int(n) for c, pc, b, n in PCE.findall(line)
                             if c == 'e' and int(pc, 16) == 0x1ec3a)
            elif '[rr425] ' in line:
                kv = {k: int(v) for k, v in
                      re.findall(r'(\w+)=(\d+)', line.split('[rr425]', 1)[1])}
                self.rr.append((ts(line), kv))
        # a window's pc line follows its counter line
        self.rr = [(t, kv, pcs.get(str(kv.get('w')), 0)) for t, kv in self.rr]

    def account(self):
        s0, s1 = self.span(*SPAN)
        frames = (self.frame_at(s1 + 2.0) or 0) - (self.frame_at(s0) or 0)
        win = [r for r in self.rr if r[0] and s0 < r[0] <= s1 + 2.0]
        tot = {}
        for _, kv, eo in win:
            for k in ('it', 'eo', 'g', 'gi', 'gs', 'x', 'hc', 'gapus', 'dt'):
                tot[k] = tot.get(k, 0) + kv.get(k, 0)
            tot['eo1ec3a'] = tot.get('eo1ec3a', 0) + eo
        bl = self.blocks_in(s0, s1)
        sd = (sum(b['sd'] for b in bl) / (60.0 * len(bl))) if bl else float('nan')
        f = max(frames, 1)
        n = self.fld[-1][1] if self.fld else 0
        fl = self.fld[-1][2] if self.fld else 0
        return {
            'msf': self.msf(s0, s1), 'sd': sd, 'windows': len(win), 'frames': frames,
            'it': tot.get('it', 0) / f, 'eo': tot.get('eo', 0) / f,
            'eo1ec3a': tot.get('eo1ec3a', 0) / f, 'g': tot.get('g', 0) / f,
            'gi': tot.get('gi', 0) / f, 'x': tot.get('x', 0) / f,
            'hc': tot.get('hc', 0) / f,
            'gap': 100.0 * tot.get('gapus', 0) / (tot.get('dt', 0) * 1000.0)
                   if tot.get('dt') else float('nan'),
            'flipshare': fl / n if n else float('nan'), 'fldn': n,
        }


def leg(name, ok, text):
    if ok is None:
        print('- %s: VOID  %s' % (name, text))
    else:
        print('- %s: %s  %s' % (name, 'HIT' if ok else 'MISS', text))
    return ok


def window_msf(arm, lo=100, hi=220, step=10):
    out = []
    for a in range(lo, hi, step):
        out.append(arm.msf(arm.mark + a, arm.mark + a + step - 2.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', action='append', default=[])
    ap.add_argument('--expect')
    o = ap.parse_args()
    e = json.load(open(o.expect))['expect'] if o.expect else {}
    dirs = dict(a.split('=', 1) for a in o.arm)
    arms = {r: VArm(dirs[r]) for r in ROLES if r in dirs}
    bad = {}
    acc = {}
    for r, arm in arms.items():
        why = []
        if arm.mark is None:
            why.append('no mark cinematic')
        else:
            acc[r] = arm.account()
        if not arm.s2tcvt:
            why.append('no [s2tcvt] on')
        c, i = WANT[r]
        if arm.chain != c:
            why.append('[fldcw1018] chain=%s, want %d' % (arm.chain, c))
        if arm.ibc is None or arm.ibc[0] != i or (i and arm.ibc[1] != 'ok'):
            why.append('[ibc507] %s, want on=%d%s' % (arm.ibc, i, ' layout=ok' if i else ''))
        if r in acc:
            if acc[r]['windows'] < e.get('V_min_windows', 20):
                why.append('%d [rr425] windows in the span' % acc[r]['windows'])
            if not acc[r]['sd'] <= e.get('V_sd_max', 5.0):
                why.append('Finish sd %.2f/f over the span' % acc[r]['sd'])
        if why:
            bad[r] = why

    print('### per arm, over [mark+%.0f, mark+%.0f], per guest frame\n' % SPAN)
    print('| arm | dir | ms/f | sd/f | it | eo | eo 0x1ec3a | g | gi | x | hc | gap % | fldcw flips/n (n) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in ROLES:
        if r in acc:
            a = acc[r]
            print('| %s | %s | %.1f | %.2f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.1f | %.4f (%d) |' % (
                r, arms[r].name, a['msf'], a['sd'], a['it'], a['eo'], a['eo1ec3a'], a['g'],
                a['gi'], a['x'], a['hc'], a['gap'], a['flipshare'], a['fldn']))
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
    base = acc['A']['msf']
    spread_ok = True
    if 'A2' in acc and 'A2' not in bad:
        a, a2 = acc['A']['msf'], acc['A2']['msf']
        base = (a + a2) / 2.0
        spread = abs(a2 - a) / base
        spread_ok = spread <= e.get('N_spread_max', 0.08)
        leg('N', spread_ok, 'A %.1f, A2 %.1f ms/f: spread %.3f (<= %.2f); base %.1f'
            % (a, a2, spread, e.get('N_spread_max', 0.08), base))
    else:
        print('- N: no valid A2; base is A alone, %.1f ms/f' % base)
    A = acc['A']
    leg('FL', A['flipshare'] <= e.get('FL_flip_share_max', 0.05) if A['fldn'] else None,
        'A flips/n %.4f over %d FLDCW (<= %.2f)' % (A['flipshare'], A['fldn'],
                                                    e.get('FL_flip_share_max', 0.05)))

    def ms_leg(name, r, key, dflt):
        if r not in acc or r in bad:
            return leg(name, None, '%s void or absent' % r)
        if not spread_ok:
            return leg(name, None, 'drift over the bound (N)')
        q = acc[r]['msf'] / base
        return leg(name, q <= e.get(key, dflt), '%s %.1f ms/f = %.3f x base (<= %.2f)'
                   % (r, acc[r]['msf'], q, e.get(key, dflt)))

    if 'F' in acc and 'F' not in bad:
        q = acc['F']['eo1ec3a'] / A['eo1ec3a'] if A['eo1ec3a'] else float('nan')
        leg('FM', q <= e.get('FM_eo_ratio_max', 0.1), 'eo at 0x1ec3a F %.0f vs A %.0f per frame: %.3f (<= %.2f)'
            % (acc['F']['eo1ec3a'], A['eo1ec3a'], q, e.get('FM_eo_ratio_max', 0.1)))
    else:
        leg('FM', None, 'F void or absent')
    ms_leg('FE', 'F', 'FE_msf_ratio_max', 0.93)
    if 'I' in acc and 'I' not in bad:
        q = acc['I']['hc'] / A['hc'] if A['hc'] else float('nan')
        leg('IM', q <= e.get('IM_hc_ratio_max', 0.3), 'hc I %.0f vs A %.0f per frame: %.3f (<= %.2f)'
            % (acc['I']['hc'], A['hc'], q, e.get('IM_hc_ratio_max', 0.3)))
    else:
        leg('IM', None, 'I void or absent')
    ms_leg('IE', 'I', 'IE_msf_ratio_max', 0.93)
    ms_leg('BE', 'IF', 'BE_msf_ratio_max', 0.87)
    if 'IF' in acc and 'IF' not in bad:
        leg('G', acc['IF']['msf'] <= e.get('G_msf_max', 33.4), 'IF %.1f ms/f (<= %.1f)'
            % (acc['IF']['msf'], e.get('G_msf_max', 33.4)))
    else:
        leg('G', None, 'IF void or absent')
    return 0


if __name__ == '__main__':
    sys.exit(main())
