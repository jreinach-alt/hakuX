"""Compare every capture of two result dirs byte for byte (pgraph arms pair).

usage: cmp_pair.py <A result id> <B result id>
"""
import hashlib
import os
import sys

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def caps(rid):
    out = {}
    for root, _, files in os.walk(R + rid):
        for f in files:
            if f.endswith('.png'):
                p = os.path.join(root, f)
                out[os.path.relpath(p, R + rid)] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return out


def main():
    a, b = caps(sys.argv[1]), caps(sys.argv[2])
    keys = sorted(set(a) | set(b))
    same = [k for k in keys if a.get(k) and a.get(k) == b.get(k)]
    diff = [k for k in keys if a.get(k) and b.get(k) and a[k] != b[k]]
    only = [k for k in keys if not (a.get(k) and b.get(k))]
    print(f'A {len(a)} B {len(b)} identical {len(same)} differ {len(diff)} one-arm-only {len(only)}')
    for k in diff:
        print('  DIFF', k)
    for k in only:
        print('  ONLY', 'A' if k in a else 'B', k)
    suites = {}
    for k in same:
        s = os.path.basename(k).split('::')[0]
        suites[s] = suites.get(s, 0) + 1
    for s, n in sorted(suites.items()):
        print(f'  same {n:4d} {s}')
    for rid in sys.argv[1:3]:
        top = sorted(os.listdir(R + rid))
        print(rid, [t for t in top if not t.startswith('captures')][:40])


if __name__ == '__main__':
    main()
