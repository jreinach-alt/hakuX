#!/usr/bin/env python3
"""Syntax-check C files of this worktree with the Android Release build's flags.

Each file takes its own entry from the newest arm64-v8a compile_commands.json
in the main checkout; include paths under the main checkout are pointed at this
worktree where they exist (generated headers stay where the build put them).
Usage: ccheck.py hw/xbox/mcpx/apu/vp/vp.c [...]
"""
import glob
import json
import os
import shlex
import subprocess
import sys

MAIN = '/home/justin/hakuX'
WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def newest_cc():
    cands = glob.glob(MAIN + '/android/app/.cxx/Release/*/arm64-v8a/'
                      'compile_commands.json')
    return max(cands, key=os.path.getmtime)


def fix(x):
    for pre in ('-I', '-isystem', '-iquote', ''):
        if x.startswith(pre + MAIN):
            p = x[len(pre):]
            if p == MAIN or p.startswith(MAIN + '/'):
                q = WT + p[len(MAIN):]
                if os.path.exists(q):
                    return pre + q
    return x


def main():
    path = newest_cc()
    cc = json.load(open(path))
    print('compile_commands:', path)
    rc = 0
    for src in sys.argv[1:]:
        ref = [e for e in cc if e['file'] == os.path.join(MAIN, src)]
        if not ref:
            print('==', src, 'NOT IN compile_commands')
            rc = 1
            continue
        ref = ref[0]
        args = (shlex.split(ref['command']) if 'command' in ref
                else ref['arguments'])
        a, skip = [], False
        for x in args:
            if skip:
                skip = False
                continue
            if x in ('-o', '-MT', '-MF', '-MQ'):
                skip = True
                continue
            if x in ('-c', '-MD', '-MMD') or x == ref['file'] or x == src:
                continue
            a.append(fix(x))
        a += ['-fsyntax-only', '-Wall', '-Wno-unused-function',
              os.path.join(WT, src)]
        r = subprocess.run(a, cwd=ref['directory'], capture_output=True,
                           text=True)
        out = [l for l in (r.stdout + r.stderr).splitlines()
               if 'error:' in l or 'warning:' in l]
        print('==', src, 'rc', r.returncode, 'errors',
              sum('error:' in l for l in out), 'warnings',
              sum('warning:' in l for l in out))
        print('\n'.join(out[:80]))
        rc |= r.returncode
    return rc


if __name__ == '__main__':
    sys.exit(main())
