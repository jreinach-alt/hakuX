#!/usr/bin/env python3
"""Type-check vk/surface.c from this worktree with the NDK line the shared
tree's CMake recorded, once for the perflog configuration and once without.
Only the source file and the source include roots are re-pointed; generated
headers still come from the shared tree's .cxx build directories."""
import json, glob, os, shlex, subprocess, sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SHARED = '/home/justin/hakuX'
SRC = 'hw/xbox/nv2a/pgraph/vk/surface.c'
rc = 0
for f in sorted(glob.glob(SHARED + '/android/app/.cxx/Release/*/arm64-v8a/compile_commands.json')):
    for e in json.load(open(f)):
        if not e['file'].endswith(SRC):
            continue
        args = shlex.split(e['command'])
        out = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == '-o':
                skip = True
                continue
            if a.startswith('-I' + SHARED) and '/android/app/.cxx' not in a:
                a = '-I' + WT + a[len('-I' + SHARED):]
            if a.endswith(SRC):
                a = os.path.join(WT, SRC)
            out.append(a)
        out += ['-o', '/dev/null', '-Wall', '-Wno-unused-function']
        perf = 'NV2A_PERF_LOG=1' in e['command']
        p = subprocess.run(out, cwd=e['directory'], capture_output=True, text=True)
        errs = [l for l in p.stderr.splitlines() if 'surface.c' in l and ('error' in l or 'warning' in l)]
        print('%s perflog=%s rc=%d' % (os.path.basename(os.path.dirname(os.path.dirname(f))), perf, p.returncode))
        for l in errs:
            print('  ' + l)
        rc |= p.returncode
        break
sys.exit(rc)
