"""srstrip.py <run> <drive start HH:MM:SS.fff, PDT, 2026-10-02> <out> <t0> <t1> <step> <cols> <WxH of the stream>:
brightened frames of a srgrab.py stream (<run>/sr/) between drive times t0..t1. Lane tool, not harness."""
import sys, datetime, zoneinfo, numpy as np
from PIL import Image, ImageDraw
run, start, out, a, b, step, cols, wh = sys.argv[1:9]
sw, sh = map(int, wh.split('x')); cols = int(cols)
h, m, s = start.split(':')
t0 = datetime.datetime(2026, 10, 2, int(h), int(m), int(float(s)), int((float(s) % 1) * 1e6),
                       tzinfo=zoneinfo.ZoneInfo('America/Los_Angeles')).timestamp()
ts = np.array([float(l.split('\t')[1]) for l in open(run + '/sr/frames.tsv')])
raw = np.memmap(run + '/sr/frames.raw', dtype=np.uint8, mode='r').reshape(-1, sh, sw, 3)
times = np.arange(float(a), float(b), float(step))
W, H = 200, 150
sheet = Image.new('RGB', (cols * W, ((len(times) + cols - 1) // cols) * (H + 12)))
d = ImageDraw.Draw(sheet)
for i, t in enumerate(times):
    k = min(int(np.searchsorted(ts, t0 + t)), len(ts) - 1)
    im = (255 * (np.array(raw[k]).astype(float) / 255) ** 0.5).astype(np.uint8)
    x, y = (i % cols) * W, (i // cols) * (H + 12)
    sheet.paste(Image.fromarray(im).resize((W, H)), (x, y))
    d.text((x + 2, y + H), '%.2f' % t, fill='yellow')
sheet.save(out)
