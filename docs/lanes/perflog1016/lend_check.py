#!/usr/bin/env python3
"""perflog1016 (#433): do the OUTBOX patches apply where they would land?

    python3 docs/lanes/perflog1016/lend_check.py [ref ...]

For each ref (default: origin/master and every holder's branch, lane/fps1015
and lane/x1port1012), reads the ref's tree into a scratch index and runs
`git apply --cached --check` for each patch in this directory. Touches no
working tree and no other lane's worktree; only this repo's object store.
Also says whether the ref already carries the run-time switch's
implementation (NV2A_PERFLOG_RT_IMPLEMENTATION in pgraph/profile.c), which is
what "the lend has landed" means.
"""
import glob
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
REFS = ['origin/master', 'origin/lane/fps1015', 'origin/lane/x1port1012']


def git(args, env=None, check=False):
    return subprocess.run(['git', '-C', ROOT] + args, capture_output=True,
                          text=True, env=env, check=check)


def main():
    refs = sys.argv[1:] or REFS
    patches = sorted(glob.glob(os.path.join(HERE, '*.patch')))
    bad = 0
    for ref in refs:
        sha = git(['rev-parse', '--short', ref]).stdout.strip()
        if not sha:
            print('%-26s missing' % ref)
            continue
        prof = git(['show', '%s:hw/xbox/nv2a/pgraph/profile.c' % ref]).stdout
        landed = 'NV2A_PERFLOG_RT_IMPLEMENTATION' in prof
        print('%-26s %s  switch implementation %s' %
              (ref, sha, 'LANDED' if landed else 'not landed'))
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, 'index'))
            git(['read-tree', ref], env=env, check=True)
            for p in patches:
                r = git(['apply', '--cached', '--check', p], env=env)
                ok = r.returncode == 0
                if not ok and not landed:
                    bad += 1
                why = '' if ok else '  ' + (r.stderr.strip().splitlines()
                                             or ['?'])[0]
                print('    %-18s %s%s' % (os.path.basename(p),
                                         'applies' if ok else 'DOES NOT APPLY',
                                         why))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
