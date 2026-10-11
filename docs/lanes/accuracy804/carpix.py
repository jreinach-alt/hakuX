"""Per unique video frame: share of 'livery' pixels (saturated blue or red, the Nissan's
colours) in the frame below the HUD row, with the tachometer box masked. Prints u-index,
frame name, blue share, red share."""
import sys, os, glob
from PIL import Image, ImageChops, ImageStat
run = sys.argv[1]
fs = sorted(glob.glob(run + '/fr/*.png'))
prev = None; u = 0
for f in fs:
    im = Image.open(f).convert('RGB').resize((320, 180))
    if prev is not None:
        d = sum(ImageStat.Stat(ImageChops.difference(im, prev)).mean) / 3
        if d < 0.5:
            continue
    prev = im
    px = im.load(); n = blue = red = 0
    for y in range(int(180 * 0.30), 180):
        for x in range(320):
            if x > 320 * 0.62 and y > 180 * 0.45:
                continue  # tachometer
            r, g, b = px[x, y]; n += 1
            if b > 90 and b > r + 40 and b > g + 25:
                blue += 1
            elif r > 150 and r > g + 90 and r > b + 90:
                red += 1
    print('u%d\t%s\t%.4f\t%.4f' % (u, os.path.basename(f)[:-4], blue / n, red / n))
    u += 1
