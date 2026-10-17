#!/usr/bin/env python3
"""Syntax-check a worktree C file with the desktop build's compile command.

usage: syntax_check.py <repo-relative path> [...]
Source headers come from this worktree (-I.. is mapped to it); generated
headers from ~/hakuX/build-desktop.
"""
import json
import os
import shlex
import subprocess
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
BD = '/home/justin/hakuX/build-desktop'
cc = json.load(open(os.path.join(BD, 'compile_commands.json')))
rc = 0
for rel in sys.argv[1:]:
    ent = [c for c in cc if c['file'].endswith(rel)]
    if not ent:
        print('no compile command for', rel)
        rc = 1
        continue
    args = shlex.split(ent[0]['command'])
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ('-o', '-MF', '-MQ'):
            skip = True
            continue
        if a in ('-MD', '-c') or a.endswith(rel):
            continue
        if a.startswith('-I..'):
            # source headers from this worktree; subprojects it lacks from ~/hakuX
            a = ('-I' + WT + a[4:] if os.path.isdir(WT + a[4:])
                 else '-I/home/justin/hakuX' + a[4:])
        elif a.startswith('/home/justin/hakuX') and not a.startswith(BD):
            a = WT + a[len('/home/justin/hakuX'):]   # -iquote and -isystem paths
        out.append(a)
    out += ['-fsyntax-only', os.path.join(WT, rel)]
    p = subprocess.run(out, cwd=BD, capture_output=True, text=True)
    print('%s: exit %d' % (rel, p.returncode))
    sys.stdout.write(p.stderr[-4000:])
    rc |= p.returncode
sys.exit(rc)
