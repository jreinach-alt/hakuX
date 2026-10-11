#!/usr/bin/env python3
"""Run abread.py over matched windows and print the summary lines
(lane.gpunonrender, scope (D)).

    segread.py <request-id> HH:MM:SS HH:MM:SS [<request-id> from until ...]
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEEP = ("window", "gfps", "xemu-gpu Tot", "command buffers", "out  ", "in  ")
a = sys.argv[1:]
for i in range(0, len(a), 3):
    rid, lo, hi = a[i], a[i + 1], a[i + 2]
    r = subprocess.run([sys.executable, os.path.join(HERE, "abread.py"), rid,
                        "--from", lo, "--until", hi],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if any(k in line for k in KEEP):
            print(line)
    print()
