# Side-by-side idle (b) and input (c) frames for one stored triplet, full size, for a by-eye check.
import json, sys
from PIL import Image, ImageDraw
run, pre, out = sys.argv[1], sys.argv[2], sys.argv[3]
trip = json.load(open('scratch/probegate/triplets.json'))
t = [x for x in trip if x['run'] == run and x['pre'] == pre][0]
ims = [Image.open(t[k]).convert('RGB') for k in ('a', 'b', 'c')]
w, h = ims[0].size
sheet = Image.new('RGB', (w * 3 + 8, h), (40, 40, 40))
for i, im in enumerate(ims):
    sheet.paste(im.resize((w, h)), (i * (w + 4), 0))
sheet.save(out, quality=88)
print(out, w, h)
