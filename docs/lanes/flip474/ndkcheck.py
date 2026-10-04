#!/usr/bin/env python3
"""Syntax-check files of this worktree with the NDK compile command of a built
tree (default: the main checkout's newest arm64 Release configure).

    python3 ndkcheck.py [--perflog 0|1] <repo-relative .c> ...

The command is the built tree's, with its source root swapped for this
worktree, `-o` dropped and `-fsyntax-only` added; generated headers still come
from the built tree. NV2A_PERF_LOG is forced to the given value so both modes
of a perflog-guarded block are compiled.
"""
import glob
import json
import os
import shlex
import subprocess
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
SRC = '/home/justin/hakuX'


def newest_db():
    dbs = glob.glob(SRC + '/android/app/.cxx/Release/*/arm64-v8a/compile_commands.json')
    return max(dbs, key=os.path.getmtime)


def swap(a):
    # Only source paths this worktree has; generated and prebuilt trees
    # (glib, the configure's build dir) stay the built tree's.
    if a.endswith(SRC):
        return a[:-len(SRC)] + WT
    i = a.find(SRC + '/')
    if i < 0:
        return a
    path = a[i:]
    rel = path[len(SRC) + 1:]
    if rel.startswith('android/') or not os.path.exists(os.path.join(WT, rel)):
        return a
    return a[:i] + os.path.join(WT, rel)


def main(argv):
    perflog = None
    if argv[:1] == ['--perflog']:
        perflog = argv[1]
        argv = argv[2:]
    db = json.load(open(newest_db()))
    rc = 0
    for rel in argv:
        want = os.path.join(SRC, rel)
        ent = next((e for e in db if os.path.normpath(e['file']) == want), None)
        if ent is None:
            print(f'{rel}: no entry in {newest_db()}')
            rc = 1
            continue
        args = ent.get('arguments') or shlex.split(ent['command'])
        out = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == '-o':
                skip = True
                continue
            if perflog is not None and a.startswith('-DNV2A_PERF_LOG'):
                continue
            a = swap(a)
            out.append(a)
        out.append('-fsyntax-only')
        if perflog is not None:
            out.append('-DNV2A_PERF_LOG=' + perflog)
        r = subprocess.run(out, cwd=ent['directory'], capture_output=True, text=True)
        errs = [l for l in r.stderr.splitlines() if 'error' in l]
        warns = [l for l in r.stderr.splitlines()
                 if 'warning:' in l and os.path.basename(rel) in l]
        print(f'{rel} perflog={perflog}: exit {r.returncode}, {len(errs)} error lines, '
              f'{len(warns)} warnings in the file')
        for l in (errs + warns)[:20]:
            print('   ', l)
        rc |= r.returncode
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
