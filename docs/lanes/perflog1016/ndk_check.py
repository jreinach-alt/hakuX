#!/usr/bin/env python3
"""perflog1016 (#433): compile this worktree's nv2a sources with the NDK, the
way the Android build does, without a gradle build.

    python3 docs/lanes/perflog1016/ndk_check.py --base BASEDIR
            [--db compile_commands.json] [--asm OUTDIR] [files...]

Takes each nv2a source's command from an existing Android build's compile
database (the main checkout's, by default), points every source include path
at this worktree instead (generated headers stay where the build put them),
and compiles twice: as the default build, and with -DNV2A_PERF_LOG=1 as a
perflog build. -fsyntax-only, with unused variables made errors: the switch
turns compiled-out timers into declared ones.

BASEDIR is the base commit's source tree, extracted with
    git archive -o base.tar <base> hw include ui linux-headers target/i386 \\
        tcg host android/app/src/main/cpp
and is compiled the same way. An error the base also has (same file, same
message, line numbers aside) is pre-existing and listed, not counted.

With --asm, also writes the default build's assembly for the named files to
OUTDIR, to read the OFF path of a gated site.

Exit 0 only if no file has an error its base does not.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DB = ('/home/justin/hakuX/android/app/.cxx/tools/debug2/arm64-v8a/'
      'compile_commands.json')
SRC = '/home/justin/hakuX'
ERR = re.compile(r'^(\S+?):\d+:\d+: error: (.*)$')


def retarget(cmd, src_file, root):
    """The database's argv, with source paths moved to `root` and the output
    and input dropped."""
    argv = shlex.split(cmd)
    out = []
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a == '-o':
            skip = True
            continue
        if a == '-c' or a == src_file:
            continue
        if a.startswith('-I' + SRC) and '/.cxx/' not in a:
            a = '-I' + root + a[len('-I' + SRC):]
        out.append(a)
    return out


def errors(stderr, root):
    """{(file relative to its tree, message)} for every error line."""
    got = set()
    for line in stderr.splitlines():
        m = ERR.match(line)
        if m:
            got.add((os.path.relpath(m.group(1), root), m.group(2)))
    return got


def compile_one(entry, root, perf_log, asm_dir=None):
    rel = os.path.relpath(entry['file'], SRC)
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return set(), ''
    argv = retarget(entry['command'], entry['file'], root)
    argv += ['-Werror=unused-variable', '-Werror=unused-but-set-variable']
    if perf_log:
        argv.append('-DNV2A_PERF_LOG=1')
    if asm_dir:
        argv += ['-S', '-o', os.path.join(asm_dir, rel.replace('/', '_') + '.s')]
    else:
        argv.append('-fsyntax-only')
    argv.append(path)
    r = subprocess.run(argv, cwd=entry['directory'], capture_output=True,
                       text=True)
    if r.returncode and not errors(r.stderr, root):
        return {(rel, 'compiler exit %d' % r.returncode)}, r.stderr
    return errors(r.stderr, root), r.stderr


def check(job, base):
    entry, perf_log = job
    rel = os.path.relpath(entry['file'], SRC)
    mine, text = compile_one(entry, ROOT, perf_log)
    old, _ = compile_one(entry, base, perf_log) if mine else (set(), '')
    return rel, perf_log, mine - old, mine & old, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DB)
    ap.add_argument('--base', required=True)
    ap.add_argument('--asm')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('files', nargs='*',
                    help='source paths relative to the tree; default: every '
                         'hw/xbox/nv2a source in the database')
    a = ap.parse_args()
    base = os.path.abspath(a.base)

    db = json.load(open(a.db))
    want = set(a.files)
    entries = []
    seen = set()
    for e in db:
        rel = os.path.relpath(e['file'], SRC)
        if rel in seen:
            continue
        if want and rel not in want:
            continue
        if not want and not rel.startswith('hw/xbox/nv2a/'):
            continue
        if not os.path.exists(os.path.join(ROOT, rel)):
            continue
        seen.add(rel)
        entries.append(e)

    if a.asm:
        os.makedirs(a.asm, exist_ok=True)
        for e in entries:
            compile_one(e, ROOT, 0, a.asm)

    jobs = [(e, pl) for e in entries for pl in (0, 1)]
    bad = 0
    pre = 0
    with ThreadPoolExecutor(a.jobs) as ex:
        for rel, pl, new, old, text in ex.map(lambda j: check(j, base), jobs):
            tag = 'perflog' if pl else 'default'
            pre += len(old)
            for f, msg in sorted(old):
                print('pre  %s (%s): %s: %s' % (rel, tag, f, msg))
            if new:
                bad += 1
                print('NEW  %s (%s)\n%s' % (rel, tag, text))
            else:
                print('ok   %s (%s)' % (rel, tag))
    print('NDK CHECK: %d files x 2 builds, %d with a new error, '
          '%d pre-existing errors' % (len(entries), bad, pre))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
