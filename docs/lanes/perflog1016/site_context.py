#!/usr/bin/env python3
"""perflog1016 (#433): print every NV2A_PERF_LOG / HAKUX_TCG787 gate in a ref,
with the lines it gates, for the inventory in NOTES.md.

    python3 docs/lanes/perflog1016/site_context.py [--ref origin/master] FILE...

For an `#if` gate, prints from the `#if` to its matching `#endif` (capped);
for an expression gate (`NV2A_PERF_LOG ? ...`, `if (NV2A_PERF_LOG)`), the
statement and a few lines after. Reads the ref's blobs; no working tree.
"""
import argparse
import re
import subprocess

GATE = re.compile(r'NV2A_PERF_LOG|HAKUX_TCG787')
ROOT = __file__.rsplit('/docs/', 1)[0]


def blob(ref, path):
    return subprocess.run(['git', '-C', ROOT, 'show', '%s:%s' % (ref, path)],
                          capture_output=True, text=True, check=True).stdout


def block_end(lines, i, cap):
    depth = 0
    for j in range(i, min(len(lines), i + cap)):
        s = lines[j].lstrip()
        if s.startswith('#if'):
            depth += 1
        elif s.startswith('#endif'):
            depth -= 1
            if depth == 0:
                return j
    return min(len(lines), i + cap) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', default='origin/master')
    ap.add_argument('--cap', type=int, default=40)
    ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    for path in a.files:
        lines = blob(a.ref, path).splitlines()
        shown = -1
        for i, l in enumerate(lines):
            if i <= shown or not GATE.search(l):
                continue
            s = l.lstrip()
            if s.startswith('#if'):
                end = block_end(lines, i, a.cap)
            elif s.startswith(('#define', '#else', '#endif', '*', '/*', '//')):
                end = i
            else:
                end = min(len(lines) - 1, i + 6)
            lo = max(0, i - 3)
            print('==== %s:%d' % (path, i + 1))
            for k in range(lo, end + 1):
                print('%6d  %s' % (k + 1, lines[k]))
            shown = end
        print()


if __name__ == '__main__':
    main()
