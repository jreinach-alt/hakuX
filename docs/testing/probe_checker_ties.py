"""Locate the checkerboard cell edges in a Material_color_source capture.

DrawCheckerboardUnproject stretches a 256-texel board with 20-texel cells
over 640x480, so cell edges sit at y = 37.5k and x = 50k.  For each image
this prints the first row of each new cell down three columns right of the
quads and the first column of each new cell along four rows clear of the
foreground.  Where an image's edge lands one pixel over is the texel-tie
measurement in docs/investigations/edge-defect.md.

Usage: probe_checker_ties.py NAME=PATH [NAME=PATH ...]
e.g.   probe_checker_ties.py gold=/tmp/goldens/results/Material_color_source/Emissive_me0.png \
           ours=results/Material_color_source::Emissive_me0.png
Needs pillow.
"""
import sys
from PIL import Image
if len(sys.argv) < 2:
    sys.exit(__doc__)
srcs = dict(a.split('=', 1) for a in sys.argv[1:])
ims={k:Image.open(v).convert('RGB') for k,v in srcs.items()}
def cls(p):
    r=p[0]
    return 'D' if r==32 else ('L' if r==144 else '?')
def trans(seq,start):
    # return list of (pos, from, to) transitions
    out=[]
    for i in range(1,len(seq)):
        if seq[i]!=seq[i-1]: out.append((start+i,seq[i-1]+'>'+seq[i]))
    return out
# vertical probe at columns right of the quads
for x in (560,600,630):
    print(f'--- column {x}: first row of each new cell (expected 37.5k)')
    for k,im in ims.items():
        s=''.join(cls(im.getpixel((x,y))) for y in range(0,480))
        t=trans(s,0)
        print(f'  {k:5s}: '+' '.join(f'{p}{c[0]}{c[2]}' for p,c in t))
for y in (50,90,420,470):
    print(f'--- row {y}: first column of each new cell (expected 50k)')
    for k,im in ims.items():
        s=''.join(cls(im.getpixel((x,y))) for x in range(0,640))
        t=trans(s,0)
        print(f'  {k:5s}: '+' '.join(f'{p}{c[0]}{c[2]}' for p,c in t))
