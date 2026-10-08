#!/usr/bin/env python3
"""Print a few [rdc] and [tlb68] lines from mid-run of a soak's logcat."""
import sys

d = sys.argv[1] + '/logcat.txt'
rdc = [l for l in open(d, errors='replace') if '[rdc]' in l]
tlb = [l for l in open(d, errors='replace') if '[tlb68]' in l]
for l in rdc[100:104] + tlb[150:152]:
    print(l.rstrip()[60:460])
