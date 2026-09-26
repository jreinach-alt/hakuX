#!/usr/bin/env python3
"""Syntax-check one nv2a source from this worktree with the desktop build's
flags (-Werror). Needs the desktop channel's build tree for its generated
headers; compiles nothing into it.

  python3 docs/lanes/blinx372d/cc_surface.py [hw/xbox/nv2a/pgraph/vk/surface.c]
"""
import json
import os
import shlex
import subprocess
import sys

BUILD = os.environ.get('DC_BUILD',
                       '/home/justin/hakux-work/desktop/tree/build-linux')


def main():
    rel = sys.argv[1] if len(sys.argv) > 1 else 'hw/xbox/nv2a/pgraph/vk/surface.c'
    cc = json.load(open(os.path.join(BUILD, 'compile_commands.json')))
    entry = [e for e in cc if e['file'].endswith(rel)][0]
    args = shlex.split(entry['command'])
    for flag in ('-o', '-MQ', '-MF'):
        while flag in args:
            i = args.index(flag)
            del args[i:i + 2]
    args = [a for a in args if a != '-MD' and not a.endswith(rel)]
    args += ['-fsyntax-only', '-Werror', os.path.abspath(rel)]
    r = subprocess.run(args, cwd=BUILD, capture_output=True, text=True)
    sys.stderr.write(r.stderr)
    print('cc_surface: %s rc=%d' % (rel, r.returncode))
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
