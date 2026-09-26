#!/usr/bin/env python3
"""Judge the #303 tier1 on/off A/B from soak logcats.

usage: tier1_judge.py --on LOGCAT [--on LOGCAT ...] --off LOGCAT [--off LOGCAT ...]

Each logcat is one Thor soak of Spikeout with HAKUX_FMV303_PROBE=1. The
tint meter is guest_tint.py's: `[fmv303] f=N tex0 tint mb=M lit=L` lines,
frames with lit < 100 excluded, per-frame ratio mb/lit.

M0, per run: the logcat's `tier1 threshold: N` line reads 64 (ON) or 0
(OFF), and the run has >= 100 lit frames. A run failing M0 is VOID and
does not count; an arm with fewer than two valid runs gives no verdict.

Verdict, from the pooled per-arm means (all lit frames of the arm's valid
runs):
  NOT_TIER1  |OFF - ON| <= 0.2 and OFF >= 0.1   (JIT tier not the cause)
  TIER1      OFF < 0.1 and ON >= 0.3            (tier1 is the cause)
  NONE       anything else (needs more runs)
"""
import argparse
import re

TINT = re.compile(r'f=(\d+) tex0 tint mb=(\d+) lit=(\d+) of=(\d+) px=([\d.]+) rgb=')
TIER = re.compile(r'tier1 threshold: (-?\d+)')


def read(path):
    tiers, fr = [], []
    for line in open(path, errors='replace'):
        m = TIER.search(line)
        if m:
            tiers.append(int(m.group(1)))
        m = TINT.search(line)
        if m:
            mb, lit = int(m.group(2)), int(m.group(3))
            if lit >= 100:
                fr.append(mb / lit)
    return tiers, fr


def arm(name, paths, want):
    pooled, valid = [], 0
    for p in paths:
        tiers, fr = read(p)
        ok_tier = bool(tiers) and all(t == want for t in tiers)
        ok = ok_tier and len(fr) >= 100
        mean = sum(fr) / len(fr) if fr else float('nan')
        print(f'{name} {p}\n    tier1 {tiers} lit>=100 {len(fr)} '
              f'>0.1 {sum(x > 0.1 for x in fr)} ==0 {sum(x == 0 for x in fr)} '
              f'mean {mean:.2f} {"OK" if ok else "VOID"}')
        if ok:
            valid += 1
            pooled += fr
    mean = sum(pooled) / len(pooled) if pooled else None
    return valid, mean


ap = argparse.ArgumentParser()
ap.add_argument('--on', action='append', default=[])
ap.add_argument('--off', action='append', default=[])
a = ap.parse_args()
von, mon = arm('ON ', a.on, 64)
voff, moff = arm('OFF', a.off, 0)
print(f'ON  valid runs {von} pooled mean {mon}')
print(f'OFF valid runs {voff} pooled mean {moff}')
if von < 2 or voff < 2:
    print('VERDICT NONE (fewer than two valid runs in an arm)')
elif moff < 0.1 and mon >= 0.3:
    print('VERDICT TIER1')
elif abs(moff - mon) <= 0.2 and moff >= 0.1:
    print('VERDICT NOT_TIER1')
else:
    print('VERDICT NONE')
