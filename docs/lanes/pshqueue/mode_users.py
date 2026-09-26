#!/usr/bin/env python3
"""Which nxdk_pgraph_tests sources name each mode or surface format the lane's
hunks gate on. A hunk can move only captures whose test sets its gate, so
this list bounds what the must_not_move legs have to cover."""
import os, re, sys

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1
                          else '~/nxdk_pgraph_tests/src')
PATS = [('DOT_ZW', re.compile(r'DOT_ZW')),
        ('BRDF', re.compile(r'BRDF')),
        ('B8/G8B8 surface', re.compile(r'SCF_B8|SCF_G8B8|COLOR_LE_B8|COLOR_LE_G8B8'))]
for dp, _, fs in os.walk(ROOT):
    for f in sorted(fs):
        if not f.endswith(('.cpp', '.h')):
            continue
        p = os.path.join(dp, f)
        lines = open(p, errors='ignore').read().splitlines()
        for tag, rx in PATS:
            hits = [i + 1 for i, l in enumerate(lines)
                    if rx.search(l) and not l.lstrip().startswith('//')]
            if hits:
                print('%-16s %s lines %s' % (tag, os.path.relpath(p, ROOT), hits[:8]))
