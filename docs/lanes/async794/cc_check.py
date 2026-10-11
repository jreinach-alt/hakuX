#!/usr/bin/env python3
"""Syntax/type-check vk/ files of this worktree with the desktop build's flags.

    cc_check.py <file under hw/xbox/nv2a/pgraph/vk> ...

Takes each file's command from the desktop Linux build's compile database,
points the source at this worktree, adds -fsyntax-only (and -DNV2A_PERF_LOG=1
with --perflog, the device arms' configuration). Generated headers come from
that build dir, so this checks C, not Android-only branches (__ANDROID__ is not
defined on the desktop).
"""
import json, os, shlex, subprocess, sys

DB = '/home/justin/hakux-work/desktop/tree/build-linux/compile_commands.json'
WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
args = sys.argv[1:]
extra = []
if '--perflog' in args:
    args.remove('--perflog')
    extra.append('-DNV2A_PERF_LOG=1')
if '--android' in args:
    # The perflog instruments ([sdcall], hakuX-stall) are __ANDROID__ only.
    args.remove('--android')
    extra += ['-D__ANDROID__', '-isystem',
              os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shim')]
db = json.load(open(DB))
rc = 0
for f in args:
    rel = os.path.relpath(os.path.abspath(f), WT)
    ent = [e for e in db if e['file'].endswith(rel)]
    if not ent:
        print('no entry for', rel)
        rc = 1
        continue
    e = ent[0]
    cmd = shlex.split(e['command'])
    out = []
    skip = False
    for a in cmd:
        if skip:
            skip = False
            continue
        if a in ('-o', '-MF', '-MQ'):
            skip = True
            continue
        if a in ('-c', '-MD'):
            continue
        if a.endswith(rel):
            a = os.path.join(WT, rel)
        out.append(a)
    # The worktree's headers first, so an edited header is the one read.
    incs = ['include', os.path.dirname(rel), 'hw/xbox/nv2a',
            'hw/xbox/nv2a/pgraph', 'hw/xbox/nv2a/pgraph/glsl', 'hw/xbox', '']
    # -iquote dirs are searched before -I for "..." includes, and the build's
    # own -iquote names the stale desktop tree; ours go in front of both.
    out[1:1] = (['-iquote' + os.path.join(WT, i) for i in incs] +
                ['-I' + os.path.join(WT, i) for i in incs])
    out = [a.replace('/home/justin/hakux-work/desktop/tree/', WT + '/')
           if a.startswith(('-iquote', '-I')) and 'build-linux' not in a
           else a for a in out]
    out += ['-fsyntax-only'] + extra
    p = subprocess.run(out, cwd=e['directory'], capture_output=True, text=True)
    msgs = [l for l in p.stderr.splitlines() if 'error' in l or 'warning' in l]
    print('%s: rc=%d, %d diagnostics' % (rel, p.returncode, len(msgs)))
    for l in msgs[:40]:
        print('  ' + l)
    rc |= p.returncode
sys.exit(rc)
