#!/usr/bin/env python3
"""Locate every TexFmt_R6G5B5 capture on this host (golden, console, runs)."""
import os
import sys

bases = sys.argv[1:] or ['/home/justin/goldens', '/home/justin/hakuX/hardware',
                         '/home/justin/hakux-work']
for base in bases:
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'wt')]
        if root.endswith('2026-09-19-calib'):
            print('CALIBDIR', root)
        for f in files:
            if 'TexFmt_R6G5B5' in f and f.endswith('.png'):
                print(os.path.join(root, f))
