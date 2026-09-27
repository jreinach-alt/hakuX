"""Is a capture's A/B difference noise? Hash the same capture across every result dir on disk.

usage: superscreen_noise.py <capture basename substring> [<A id> <B id>]
Prints each distinct hash with its count and a few result ids holding it, plus the pair's score rows.
"""
import hashlib
import os
import sys

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def main():
    name = sys.argv[1]
    seen = {}
    for rid in os.listdir(R):
        d = R + rid
        if not os.path.isdir(d):
            continue
        for sub in os.listdir(d):
            if not sub.startswith('captures'):
                continue
            p = os.path.join(d, sub, name)
            if os.path.exists(p):
                h = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]
                seen.setdefault(h, []).append(rid + '/' + sub)
    for h, ids in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        print(h, len(ids), sorted(ids)[-4:])
    for rid in sys.argv[2:]:
        for f in os.listdir(R + rid):
            if f.startswith('scores'):
                for line in open(R + rid + '/' + f):
                    if name.split('.png')[0].split('::')[-1] in line:
                        print(rid, line.rstrip())


if __name__ == '__main__':
    main()
