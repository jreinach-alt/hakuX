"""Run-length encode the Viewport suite's quad extents, ours against gold.

Prints, for each of the twelve captures, the colour runs along rows 190 and
290 and columns 170/270/370/470, classed P (programmable quad, 153,17,0),
F (fixed-function quad, 187,51,0), b (background 224,224,224), c (clear).
This is the measurement behind docs/investigations/edge-defect.md: ten
offsets identical to hardware, and the per-vertex sign table for the two
that are not.

Usage: probe_viewport_extents.py OURS_DIR [GOLD_DIR]
OURS_DIR holds "Viewport::<test>.png"; GOLD_DIR defaults to
/tmp/goldens/results/Viewport.  Needs pillow.
"""
import sys
from PIL import Image
if len(sys.argv) < 2:
    sys.exit(__doc__)
O = sys.argv[1].rstrip('/') + '/Viewport::'
G = (sys.argv[2].rstrip('/') if len(sys.argv) > 2 else '/tmp/goldens/results/Viewport') + '/'
names=['-0.438_-0.438-0.000_0.000','-0.531_-0.531-0.000_0.000','-0.531_-0.531-2.000_0.000','-1.000_-1.000-0.000_0.000','-1.000_-1.000-2.000_0.000','0.000_0.000-0.000_0.000','0.000_0.000-2.000_0.000','0.531_0.531-0.000_0.000','0.531_0.531-2.000_0.000','0.562_0.562-0.000_0.000','1.000_1.000-0.000_0.000','1.000_1.000-2.000_0.000']
def cls(p):
    r,g,b=p[:3]
    if (r,g,b)==(153,17,0): return 'P'
    if (r,g,b)==(187,51,0): return 'F'
    if (r,g,b)==(224,224,224): return 'b'
    if (r,g,b)==(64,64,64): return 'c'
    return '?'
def rle(seq,start):
    out=[];cur=None;n=0;s=start
    for i,c in enumerate(seq):
        if c!=cur:
            if cur is not None: out.append(f"{cur}[{s}..{start+i-1}]")
            cur=c;s=start+i
    out.append(f"{cur}[{s}..{start+len(seq)-1}]")
    return ' '.join(out)
for n in names:
    g=Image.open(G+n+'.png').convert('RGB'); o=Image.open(O+n+'.png').convert('RGB')
    print('=== '+n)
    for y in (190,290):
        so=''.join(cls(o.getpixel((x,y))) for x in range(110,532)); sg=''.join(cls(g.getpixel((x,y))) for x in range(110,532))
        print(f' row {y} ours: {rle(so,110)}'); print(f' row {y} gold: {rle(sg,110)}')
    for x in (170,270,370,470):
        so=''.join(cls(o.getpixel((x,y))) for y in range(130,352)); sg=''.join(cls(g.getpixel((x,y))) for y in range(130,352))
        print(f' col {x} ours: {rle(so,130)}'); print(f' col {x} gold: {rle(sg,130)}')
