# Flag frames with blocks of saturated pure green (the green-block corruption seen on
# Spikeout's loading screen). Score = share of 8x8 aligned blocks that are >=90% pure green.
# Hits are candidates only; every hit is confirmed by eye before it goes in the table.
import glob, sys
import numpy as np
from multiprocessing import Pool
from PIL import Image

PATS = [
    '/home/justin/hakux-work/wt/pathfind/scratch/runs/*/frames/*',
    '/home/justin/hakux-work/wt/greensize303/docs/lanes/pathfind/runs/*/*.jpg',
    '/home/justin/hakux-work/dispatch/results/*/frames/*',
    '/home/justin/hakux-work/dispatch/results/*/route-frames/*',
]
THRESH = 0.003


def score(path):
    try:
        im = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
    except Exception as e:
        return path, -1.0, 0, str(e)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # Calibrated on sw3 title/cutscene and Spikeout loading: green blocks sit at
    # R<=35, B<=40, G 110-255. The first pass used G>=230 and missed sw3's darker green.
    m = (g >= 110) & (r <= 40) & (b <= 40) & (g - r >= 100) & (g - b >= 100)
    h, w = m.shape
    h8, w8 = h // 8 * 8, w // 8 * 8
    blocks = m[:h8, :w8].reshape(h8 // 8, 8, w8 // 8, 8).mean(axis=(1, 3))
    gb = int((blocks >= 0.9).sum())
    frac = gb / blocks.size
    return path, frac, gb, f'{w}x{h}'


if __name__ == '__main__':
    seen = set()
    for p in PATS:
        seen.update(f for f in glob.glob(p) if f.lower().endswith(('.png', '.jpg')))
    files = sorted(seen)
    with Pool(8) as pool:
        rows = pool.map(score, files, chunksize=64)
    hits = [r for r in rows if r[1] >= THRESH]
    print(f'scanned {len(rows)} frames; flagged {len(hits)} at green-block share >= {THRESH}', file=sys.stderr)
    with open(sys.argv[1], 'w') as out:
        out.write('path\tgreen8_share\tgreen8_blocks\tsize\n')
        for p, f, gb, sz in sorted(hits, key=lambda r: -r[1]):
            out.write(f'{p}\t{f:.4f}\t{gb}\t{sz}\n')
