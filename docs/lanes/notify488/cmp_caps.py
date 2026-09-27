"""Compare ST_Done_* captures A vs B region by region (P0 hand-read).

usage: cmp_caps.py <A result id> <B result id>
Prints size, distinct-colour count and the bounding box of differing pixels.
"""
import os
import sys

from PIL import Image

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def find(rid, name):
    for root, _, files in os.walk(R + rid):
        for f in files:
            if f.endswith('::' + name + '.png'):
                return os.path.join(root, f)
    return None


def main():
    a, b = sys.argv[1], sys.argv[2]
    for t in ['AlphaFuncAlways_Disabled', 'ST_Calibrate', 'ST_VBlank_Spin',
              'ST_Done_Tiny', 'ST_Done_DOA', 'ST_Done_DOA_Read']:
        fa, fb = find(a, t), find(b, t)
        print('==', t, fa and fa[len(R):], fb and fb[len(R):])
        if not (fa and fb):
            continue
        ia, ib = Image.open(fa).convert('RGB'), Image.open(fb).convert('RGB')
        if ia.size != ib.size:
            print('   size', ia.size, ib.size)
            continue
        pa, pb = ia.load(), ib.load()
        w, h = ia.size
        diff = [(x, y) for y in range(h) for x in range(w) if pa[x, y] != pb[x, y]]
        print('   colours A', len(ia.getcolors(1 << 20)), 'B', len(ib.getcolors(1 << 20)),
              'diff px', len(diff), 'of', w * h)
        if diff:
            xs, ys = [p[0] for p in diff], [p[1] for p in diff]
            print('   bbox', min(xs), min(ys), max(xs), max(ys))


if __name__ == '__main__':
    main()
