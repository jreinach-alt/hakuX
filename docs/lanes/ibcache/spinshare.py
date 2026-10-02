#!/usr/bin/env python3
"""The vCPU's samples inside a guest pc range, e.g. a title's frame-limiter spin (#507, lane.ibcache).

    spinshare.py <capture_gta.sh session dir> [--lo 0x273678] [--hi 0x273698]
                 [--data rec-on.data]

GTA SA's frame limiter (default.xbe 0x273678; vcpuplan NOTES section 4) waits
for the second vblank in a loop with no stores: 0x273686 / 0x27368e load a
word, compare, and loop. At the 30 fps cap every vCPU cycle a change saves
lands in that loop, so its share of the vCPU thread is the headroom the frame
had. Below the cap the loop exits at once and its share is near zero.

Uses gta482/tbmap.py to map the vCPU thread's JIT samples to TBs. Offline.
"""
import argparse
import bisect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gta482"))
import tbmap  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--lo", default="0x273678")
    ap.add_argument("--hi", default="0x273698")
    ap.add_argument("--data", default="rec-on.data")
    a = ap.parse_args()
    lo, hi = int(a.lo, 16), int(a.hi, 16)
    tbs, _ = tbmap.load_headers(a.dir)
    starts = [t[0] for t in tbs]
    tid, ips, nsamp = tbmap.jit_samples(os.path.join(a.dir, a.data), None)
    mapped = inside = 0
    pcs = {}
    for ip in ips:
        i = bisect.bisect_right(starts, ip) - 1
        if i >= 0 and ip < tbs[i][0] + tbs[i][1]:
            mapped += 1
            pc = tbs[i][2] & 0xffffffff
            if lo <= pc < hi:
                inside += 1
                pcs[pc] = pcs.get(pc, 0) + 1
    print("%s: tid %s, %d samples, %d JIT, %d mapped to a TB"
          % (os.path.basename(os.path.normpath(a.dir)), tid, nsamp, len(ips),
             mapped))
    print("  TBs starting in [%#x, %#x): %d samples, %.2f%% of the thread, "
          "%.2f%% of mapped JIT"
          % (lo, hi, inside, 100.0 * inside / max(1, nsamp),
             100.0 * inside / max(1, mapped)))
    for pc, n in sorted(pcs.items(), key=lambda x: -x[1]):
        print("    %08x %6d" % (pc, n))


if __name__ == "__main__":
    main()
