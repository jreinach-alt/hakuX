#!/usr/bin/env python3
"""Type-check this worktree's profile.c with the dispatcher's own Android
compile command (newest compile_commands.json in the build tree), with
NV2A_PERF_LOG 1 and 0. -fsyntax-only; headers come from the build tree.

    synchk.py [file under hw/...]
"""
import glob, json, os, shlex, subprocess, sys

rel = sys.argv[1] if len(sys.argv) > 1 else 'hw/xbox/nv2a/pgraph/profile.c'
here = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
best = None
for p in glob.glob('/home/justin/hakux-work/dispatch/build-tree/android/app/.cxx/**/compile_commands.json', recursive=True):
    try:
        cc = json.load(open(p))
    except Exception:
        continue
    for e in cc:
        if e.get('file', '').endswith(rel):
            m = os.path.getmtime(p)
            if not best or m > best[0]:
                best = (m, e)
e = best[1]
args = e.get('arguments') or shlex.split(e['command'])
out = []
skip = False
for a in args:
    if skip:
        skip = False
        continue
    if a in ('-o', '-MF', '-MT', '-MQ'):
        skip = True
        continue
    if a in ('-c', '-MD', '-MMD'):
        continue
    if a.endswith(rel):
        continue
    out.append(a)
rc = 0
for perf in ('1', '0'):
    cmd = [x if not x.startswith('-DNV2A_PERF_LOG') else '-DNV2A_PERF_LOG=' + perf for x in out]
    cmd += ['-fsyntax-only', '-Wall', os.path.join(here, rel)]
    r = subprocess.run(cmd, cwd=e['directory'], capture_output=True, text=True)
    print('NV2A_PERF_LOG=%s rc=%d' % (perf, r.returncode))
    print(r.stderr[-4000:])
    rc |= r.returncode
sys.exit(rc)
