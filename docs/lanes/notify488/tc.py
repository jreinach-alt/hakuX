#!/usr/bin/env python3
"""Type-check one worktree TU with the NDK clang line of the shared tree's
Android build (compile_commands.json), every include path re-pointed at this
worktree. Usage: tc.py hw/xbox/nv2a/pgraph/pgraph.c"""
import glob, json, os, shlex, subprocess, sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
MAIN = '/home/justin/hakuX'
rel = sys.argv[1]
cc = sorted(glob.glob(MAIN + '/android/app/.cxx/Release/*/arm64-v8a/'
                      'compile_commands.json'), key=os.path.getmtime)[-1]
for e in json.load(open(cc)):
    if not e['file'].endswith(rel):
        continue
    args = e.get('arguments') or shlex.split(e['command'])
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ('-o', '-c'):
            skip = True
            continue
        if a == e['file']:
            continue
        if a.startswith('-I' + MAIN):
            # Source include dirs only; generated/prebuilt ones stay put.
            mine = WT + a[2 + len(MAIN):]
            if os.path.isdir(mine):
                a = '-I' + mine
        out.append(a)
    out += sys.argv[2:] + ['-c', os.path.join(WT, rel), '-o', '/dev/null',
                          '-Wall']
    r = subprocess.run(out, cwd=e['directory'], capture_output=True, text=True)
    msgs = [l for l in r.stderr.splitlines()
            if "error" in l or "warning: " in l]
    print('\n'.join(msgs))
    print('TC_EXIT=%d' % r.returncode)
    sys.exit(r.returncode)
sys.exit('no entry for ' + rel)
