#!/usr/bin/env python3
"""Summarise probe v2's guest-buffer tint lines from a soak logcat.

usage: guest_tint.py <logcat.txt>

Each `[fmv303] f=N tex0 tint mb=M lit=L of=O` line counts tinted 16x16
macroblocks in the guest ARGB FMV buffer. Frames with lit < 100 (black or
fading) are excluded, the same floor green_cells.py applies on screen.
"""
import re
import sys

PAT = re.compile(r'f=(\d+) tex0 tint mb=(\d+) lit=(\d+) of=(\d+) px=([\d.]+) rgb=')

rows = []
for line in open(sys.argv[1], errors='replace'):
    m = PAT.search(line)
    if m:
        f, mb, lit, of = map(int, m.groups()[:4])
        rows.append((f, mb, lit, of))

lit_rows = [(f, mb / lit) for f, mb, lit, of in rows if lit >= 100]
fr = [x for _, x in lit_rows]
print(f'tint lines {len(rows)}, lit>=100 {len(fr)}')
if fr:
    print(f'>0.1 {sum(x > 0.1 for x in fr)}  ==0 {sum(x == 0 for x in fr)}  '
          f'>0.9 {sum(x > 0.9 for x in fr)}  mean {sum(fr) / len(fr):.2f}')
    # on/off switching: transitions between clean (0) and tinted (>0.1)
    state = [0 if x == 0 else (1 if x > 0.1 else None) for x in fr]
    s = [x for x in state if x is not None]
    print('clean<->tinted transitions', sum(a != b for a, b in zip(s, s[1:])))
