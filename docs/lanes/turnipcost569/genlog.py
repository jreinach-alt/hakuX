#!/usr/bin/env python3
"""Side-by-side SPIR-V size and glslang time of gen logs.

    genlog.py <a.gen.log> <b.gen.log> ...
"""
import re
import sys

RE = re.compile(r"^(\w+)\s+(\S+)\s+glsl\s+(\d+) B\s+spv\s+(\d+) B\s+glslang\s+([\d.]+) ms")
runs = []
for p in sys.argv[1:]:
    d = {}
    for line in open(p):
        m = RE.match(line)
        if m:
            d[f"{m[1]}_{m[2]}"] = (int(m[4]), float(m[5]))
    runs.append(d)
print("| shader | " + " | ".join(f"spv B / glslang ms ({p.split('/')[-1]})" for p in sys.argv[1:]) + " |")
print("|---|" + "---|" * len(runs))
for k in runs[0]:
    print(f"| {k} | " + " | ".join(
        f"{r[k][0]} / {r[k][1]:.1f}" if k in r else "-" for r in runs) + " |")
print("| total | " + " | ".join(
    f"{sum(v[0] for v in r.values())} / {sum(v[1] for v in r.values()):.0f}" for r in runs) + " |")
