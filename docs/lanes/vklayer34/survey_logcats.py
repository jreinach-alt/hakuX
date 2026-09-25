#!/usr/bin/env python3
"""Survey device logcats under dispatch/results: which GPU driver the app
loaded, how many instance layers the Vulkan loader reported, and whether any
validation message (VUID) appears.  lane.vklayer34, #34."""
import collections
import glob
import os
import re
import sys

R = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
last = int(sys.argv[1]) if len(sys.argv) > 1 else 0

dirs = sorted(glob.glob(R + "/*"), key=os.path.getmtime)
if last:
    dirs = dirs[-last:]
seen = collections.Counter()
n_lc = 0
vuid_lines = 0
for d in dirs:
    for lc in glob.glob(d + "/**/*logcat*", recursive=True):
        if os.path.isdir(lc):
            continue
        n_lc += 1
        t = open(lc, errors="replace").read()
        drv = re.findall(r"(Loading custom Vulkan driver: [^\n]*|"
                         r"No custom driver specified|"
                         r"adrenotools failed[^\n]*|GPU driver: [^\n]*)", t)[:1]
        lay = re.findall(r"Available instance layers: (\d+)", t)[:1]
        cfg = re.findall(r"validation_layers config = (\d)", t)[:1]
        vuid_lines += len(re.findall(r"VUID-", t))
        seen[(drv[0] if drv else "-", lay[0] if lay else "-",
              cfg[0] if cfg else "-")] += 1
print(f"result dirs {len(dirs)}  logcat files {n_lc}  VUID lines {vuid_lines}")
print("count  (GPU driver line, instance layers, validation_layers cfg)")
for k, v in seen.most_common():
    print(v, k)
