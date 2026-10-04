#!/usr/bin/env python3
"""Compile this lane's changed files with the NDK command the dispatcher's
build tree used, retargeted at this worktree. Plain and NV2A_PERF_LOG=1.

A compile check, not a build: it catches syntax, types and missing
declarations in the three files, not a link error. The gradle build is the
build of record.

usage: ndk_check.py [compile_commands.json]
"""
import json
import os
import shlex
import subprocess
import sys

CC = ('/home/justin/hakux-work/dispatch/build-tree/android/app/.cxx/'
      'tools/debug2/arm64-v8a/compile_commands.json')
SRC_ROOT = '/home/justin/hakux-work/dispatch/build-tree'
FILES = ['accel/tcg/translate-all.c', 'accel/tcg/cputlb.c',
         'accel/tcg/cpu-exec.c']


def main():
    cc = sys.argv[1] if len(sys.argv) > 1 else CC
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
                                        '..'))
    db = json.load(open(cc))
    rc = 0
    for f in FILES:
        ent = [e for e in db if e['file'].endswith('/' + f)]
        if not ent:
            print('no entry for', f)
            rc = 1
            continue
        e = ent[0]
        args = e.get('arguments') or shlex.split(e['command'])
        out = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == '-o':
                skip = True
                continue
            if a.endswith('/' + f) or a == f:
                a = os.path.join(here, f)
            elif (a.startswith('-I' + SRC_ROOT) and
                  '/.cxx/' not in a and
                  os.path.isdir(here + a[2 + len(SRC_ROOT):])):
                # Source include dirs come from this tree; generated ones
                # (glib, config headers under .cxx) stay the build tree's.
                a = '-I' + here + a[2 + len(SRC_ROOT):]
            out.append(a)
        for extra in ([], ['-DNV2A_PERF_LOG=1']):
            cmd = out + extra + ['-o', '/dev/null', '-Werror=implicit-function-declaration']
            p = subprocess.run(cmd, cwd=e['directory'], capture_output=True,
                               text=True)
            tag = 'perflog' if extra else 'plain'
            warn = [l for l in p.stderr.splitlines()
                    if 'warning' in l or 'error' in l]
            print('%-28s %-7s rc=%d %s' % (f, tag, p.returncode,
                                          '; '.join(warn[:6])))
            if p.returncode:
                print(p.stderr[-3000:])
                rc = 1
    sys.exit(rc)


if __name__ == '__main__':
    main()
