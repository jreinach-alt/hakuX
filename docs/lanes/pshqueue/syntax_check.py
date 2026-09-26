#!/usr/bin/env python3
"""Compile this worktree's glsl/psh.c with -fsyntax-only, using the desktop
build's own compile line. psh.c includes "psh.h" from its own directory, so the
worktree's header is the one used. Exit status is the compiler's."""
import json, os, shlex, subprocess, sys

BUILD = '/home/justin/hakuX/build-desktop'
WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC = 'hw/xbox/nv2a/pgraph/glsl/psh.c'

entry = next(e for e in json.load(open(os.path.join(BUILD, 'compile_commands.json')))
             if e['file'].endswith(SRC))
args = entry.get('arguments') or shlex.split(entry['command'])
out, skip = [], False
for a in args:
    if skip:
        skip = False
        continue
    if a in ('-o', '-MF', '-MQ'):
        skip = True
        continue
    if a in ('-c', '-MD') or a.endswith(SRC):
        continue
    out.append(a)
out += ['-fsyntax-only', os.path.join(WT, SRC)]
r = subprocess.run(out, cwd=BUILD)
print('SYNTAX_EXIT=%d' % r.returncode)
sys.exit(r.returncode)
