#!/usr/bin/env python3
"""Syntax-check worktree sources with the nightly tree's arm64 Release compile commands (-fsyntax-only).

usage: synck.py <repo-relative path>...
The command is the nightly tree's for the same path, with the source swapped for this worktree's copy, so a
quoted include resolves here first and the -I paths (and generated headers) are the nightly tree's. A check
of syntax and of the declarations this file uses, not a build: say so wherever it is cited.
"""
import glob
import json
import os
import shlex
import subprocess
import sys

WT = '/home/justin/hakux-work/wt/halo1016'
dbs = sorted(glob.glob('/home/justin/hakux-work/nightly-wt/android/app/.cxx/Release/*/arm64-v8a/compile_commands.json'),
             key=os.path.getmtime)
db = json.load(open(dbs[-1]))
print('db', dbs[-1])
rc = 0
for rel in sys.argv[1:]:
    ent = [e for e in db if e['file'].endswith('/' + rel)]
    if not ent:
        print(rel, ': no entry')
        rc = 1
        continue
    e = ent[0]
    args = e['arguments'] if 'arguments' in e else shlex.split(e['command'])
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ('-o', '-MF', '-MQ', '-MT'):
            skip = True
            continue
        if a in ('-c', '-MD'):
            continue
        if a.endswith('/' + rel) or a == e['file']:
            a = os.path.join(WT, rel)
        out.append(a)
    out.append('-fsyntax-only')
    p = subprocess.run(out, cwd=e['directory'], capture_output=True, text=True)
    errs = [l for l in p.stderr.splitlines() if 'error' in l or 'warning' in l and rel.split('/')[-1] in l]
    print('%s: exit %d, %d error/warning lines' % (rel, p.returncode, len(errs)))
    for l in errs[:20]:
        print('   ', l)
    rc |= p.returncode
sys.exit(rc)
