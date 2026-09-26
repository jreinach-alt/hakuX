#!/usr/bin/env python3
"""-fsyntax-only on the patched psh.c (make_patch.py --emit), with the desktop
build's own compile line and this worktree's glsl/ directory first on the quote
include path, so psh.h and friends resolve as they would in the tree.
Adapted from docs/lanes/pshqueue/syntax_check.py. Exit status is the compiler's."""
import json, os, shlex, subprocess, sys, tempfile

BUILD = '/home/justin/hakuX/build-desktop'
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = 'hw/xbox/nv2a/pgraph/glsl/psh.c'

text = subprocess.run([sys.executable, os.path.join(HERE, 'make_patch.py'), '--emit'],
                      check=True, capture_output=True, text=True).stdout
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
with tempfile.TemporaryDirectory() as d:
    copy = os.path.join(d, 'psh.c')
    open(copy, 'w').write(text)
    out += ['-iquote', os.path.join(WT, os.path.dirname(SRC)), '-fsyntax-only', copy]
    r = subprocess.run(out, cwd=BUILD)
print('SYNTAX_EXIT=%d' % r.returncode)
sys.exit(r.returncode)
