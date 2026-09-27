#!/usr/bin/env python3
"""Mean of the 30 s gfps medians and p7 over the first 240 s of each run's
gameplay window: before the thermal state that ejected B2's and B3's vCPU."""
import os
import re
import subprocess

RUNS = [("A1", "1790454357-vcpuprime428-3938872"), ("B1", "1790454370-vcpuprime428-3939641"),
        ("A2", "1790454370-vcpuprime428-3939708"), ("B2", "1790454371-vcpuprime428-3939754"),
        ("A3", "1790454371-vcpuprime428-3939794"), ("B3", "1790454372-vcpuprime428-3939872")]
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vcpu_judge.py")
for name, rid in RUNS:
    out = subprocess.run(["python3", J, "--one", rid], env=dict(os.environ, TIMELINE="1"),
                         capture_output=True, text=True).stdout
    g, p, x = [], [], []
    for m in re.finditer(r"t\+\s*(\d+)s gfps med (\S+)\s+vcpu X3 (\S+)%.*?p7 (\S+)", out):
        if m.group(2) != "None" and int(m.group(1)) < 240:
            g.append(float(m.group(2)))
            x.append(float(m.group(3)))
            p.append(float(m.group(4)))
    print("%s %s first 240 s: gfps-med mean %.1f  vCPU X3 %.0f%%  p7 mean %.0f  (n=%d)"
          % (name, rid, sum(g) / len(g), sum(x) / len(x), sum(p) / len(p), len(g)))
