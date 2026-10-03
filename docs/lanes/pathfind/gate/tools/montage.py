# Blind labelling sheets: a seeded sample of stored probe triplets, two cases per image.
# Each case is a row of a, b, c (idle, idle + input, input) at 320x240. No measure numbers on the sheet.
import json, random, sys
from PIL import Image, ImageDraw

N = int(sys.argv[1]) if len(sys.argv) > 1 else 36
trip = json.load(open('scratch/probegate/triplets.json'))
rng = random.Random('probegate-2026-10-03')
sample = rng.sample(trip, N)
json.dump(sample, open('scratch/probegate/sample.json', 'w'), indent=1)
W, H = 320, 240
per = 2
for s in range(0, len(sample), per):
    cases = sample[s:s + per]
    sheet = Image.new('RGB', (3 * W + 10, per * (H + 24)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for r, case in enumerate(cases):
        y = r * (H + 24)
        d.text((4, y + 4), 'case %02d' % (s + r + 1), fill=(255, 255, 0))
        for c, key in enumerate(('a', 'b', 'c')):
            im = Image.open(case[key]).convert('RGB').resize((W, H))
            sheet.paste(im, (c * (W + 5), y + 24))
    sheet.save('scratch/probegate/sheet-%02d.jpg' % (s // per + 1), quality=85)
print('sheets', (len(sample) + per - 1) // per)
