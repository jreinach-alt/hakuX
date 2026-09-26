#!/usr/bin/env python3
"""Print the vCPU's raw topo lines, freq and thermal lines around the X3 loss.

usage: eject.py <result id> [first_n_to_skip]
"""
import re
import sys

D = "/home/justin/hakux-work/dispatch/results/"
p = D + sys.argv[1] + "/logcat.txt"
lines = open(p, errors="replace").read().splitlines()
tid = None
for l in lines:
    m = re.search(r"place vcpu.*", l)
    if m:
        print("PLACE:", m.group(0)[:300])
    if re.search(r"offline|isolat|core_ctl|cpu_pause|hotplug", l, re.I):
        print("CPU:", l[:300])
topo = [l for l in lines if "perfarch topo" in l]
skip = int(sys.argv[2]) if len(sys.argv) > 2 else 0
for l in topo[skip:skip + (int(sys.argv[3]) if len(sys.argv) > 3 else 60)]:
    print(l[:400])
