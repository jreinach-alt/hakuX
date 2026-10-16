#!/usr/bin/env python3
"""Syntax-checks C files of this worktree with the Android build's flags.

The flags come from the main checkout's compile_commands.json; include paths
under the main checkout are pointed at this worktree where they exist.
"""
import json
import os
import shlex
import subprocess
import sys

MAIN = '/home/justin/hakuX'
CC = MAIN + '/android/app/.cxx/Release/3z4l2q3k/arm64-v8a/compile_commands.json'
WT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def fix(x):
    for pre in ('-I', '-isystem', ''):
        if x.startswith(pre + MAIN):
            p = x[len(pre):]
            if p == MAIN or p.startswith(MAIN + '/'):
                q = WT + p[len(MAIN):]
                if os.path.exists(q):
                    return pre + q
    return x


def main():
    cc = json.load(open(CC))
    rc = 0
    for src in sys.argv[1:]:
        # C files of xemu_core take savevm.c's flags; C++ files of the
        # shared library take xemu_android.cpp's.
        model = ('cpp/xemu_android.cpp' if src.endswith('.cpp')
                 else 'migration/savevm.c')
        ref = [e for e in cc if e['file'].endswith(model)][0]
        args = (shlex.split(ref['command']) if 'command' in ref
                else ref['arguments'])
        a, skip = [], False
        for x in args:
            if skip:
                skip = False
                continue
            if x in ('-o', '-MT', '-MF'):
                skip = True
                continue
            if x in ('-c', '-MD') or x == ref['file']:
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
