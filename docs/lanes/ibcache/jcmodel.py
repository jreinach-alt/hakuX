#!/usr/bin/env python3
"""Jump-cache collision model at several cache sizes, from one capture_gta.sh session (#507, lane.ibcache).

    jcmodel.py <session dir> [--tid T]

Sizes the next lever after the inline probe: a larger TB_JMP_CACHE_BITS. The
jump cache is direct-mapped, so two hot TBs whose pcs hash to one slot evict
each other and every eviction is a helper call and a QHT lookup.

The model. Each live TB (no CF_INVALID) with at least one vCPU JIT sample is a
key, weighted by its samples (tbmap.py's mapping). For each slot of the
softmmu hash (tb-hash.h, TARGET_PAGE_BITS 12, TB_JMP_PAGE_BITS = BITS/2) the
independent-reference model gives a miss rate for key i of 1 - w_i/W_slot:
the chance that the slot's last visitor was someone else. Reported as the
sample-weighted share of misses.

What it cannot see. Samples are time spent in a TB, not how often the TB is
reached through the jump cache (a chained direct jump never looks). So the
absolute share is a proxy. The ratio between sizes is the reading. The 12-bit
row is checked against the measured `[jc425]` pc-collision share (R1 6.4% of
helper lookups, R1b 7.3% of R1's lookups): a model far from those is not
trusted at any size.
"""
import argparse
import bisect
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gta482"))
import tbmap  # noqa: E402

CF_INVALID = 0x00004000


def slot(pc, bits):
    pb = bits // 2
    sh = 12 - pb
    t = pc ^ (pc >> sh)
    page_mask = (1 << bits) - (1 << pb)
    return ((t >> sh) & page_mask) | (t & ((1 << pb) - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--tid")
    a = ap.parse_args()
    tbs, _ = tbmap.load_headers(a.dir)
    starts = [t[0] for t in tbs]
    tid, ips, total = tbmap.jit_samples(os.path.join(a.dir, "rec-on.data"), a.tid)
    w = collections.Counter()
    for ip in ips:
        i = bisect.bisect_right(starts, ip) - 1
        if i >= 0 and ip < tbs[i][0] + tbs[i][1]:
            t = tbs[i]
            w[(t[2], t[3], t[4] & ~0xff000000)] += 1
    live = {}
    for t in tbs:
        if t[4] & CF_INVALID:
            continue
        k = (t[2], t[3], t[4] & ~0xff000000)
        if w[k]:
            live[k] = w[k]
    tot = sum(live.values())
    print(f"tid {tid}: {total} samples, {len(ips)} JIT, {tot} in {len(live)} live keyed TBs")
    print(f"{'bits':>4} {'slots':>6} {'KB/vCPU':>7} {'shared slots':>12} {'miss share':>10} {'vs 12':>6}")
    base = None
    for bits in (12, 13, 14, 15, 16):
        per = collections.defaultdict(list)
        for k, v in live.items():
            per[slot(k[0], bits)].append(v)
        miss = sum(v * (1 - v / sum(vs)) for vs in per.values() for v in vs)
        shared = sum(1 for vs in per.values() if len(vs) > 1)
        m = miss / tot
        base = base or m
        print(f"{bits:>4} {1 << bits:>6} {(16 << bits) // 1024:>7} {shared:>12} {m:>9.1%} {m / base:>6.2f}")


if __name__ == "__main__":
    main()
