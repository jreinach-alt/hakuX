# Second labelling sample: every CONFIRMED and letterboxed triplet not in sample 1, plus refused ones, as sheets.
import json, random
from PIL import Image, ImageDraw

trip = json.load(open('scratch/probegate/triplets.json'))
first = json.load(open('scratch/probegate/sample.json'))
seen = {(t['run'], t['pre']) for t in first}
rest = [t for t in trip if (t['run'], t['pre']) not in seen]
conf = [t for t in rest if (t['verdict'] or '').startswith('CONFIRMED')]
lb = [t for t in rest if (t['verdict'] or '').startswith('letterboxed')]
ref = [t for t in rest if (t['verdict'] or '').startswith('refused')]
rng = random.Random('probegate-2')
sample = conf + lb + rng.sample(ref, min(15, len(ref)))
json.dump(sample, open('scratch/probegate/sample2.json', 'w'), indent=1)
print('confirmed', len(conf), 'letterboxed', len(lb), 'refused used', min(15, len(ref)), 'total', len(sample))
W, H = 320, 240
per = 2
for s in range(0, len(sample), per):
    cases = sample[s:s + per]
    sheet = Image.new('RGB', (3 * W + 10, per * (H + 24)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for r, case in enumerate(cases):
        y = r * (H + 24)
        d.text((4, y + 4), 'S2 case %02d' % (s + r + 1), fill=(255, 255, 0))
        for c, key in enumerate(('a', 'b', 'c')):
            im = Image.open(case[key]).convert('RGB').resize((W, H))
            sheet.paste(im, (c * (W + 5), y + 24))
    sheet.save('scratch/probegate/s2-sheet-%02d.jpg' % (s // per + 1), quality=85)
print('sheets', (len(sample) + per - 1) // per)
