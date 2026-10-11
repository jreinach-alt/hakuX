#!/usr/bin/env python3
"""Rebuild the eval frames (640 px JPEG, quality 80) from their dispatch result sources.

    make_frames.py <out dir>     # default: ./frames next to this file (not committed)
"""
import csv
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.environ.get('WORK', os.path.expanduser('~/hakux-work')), 'dispatch', 'results')

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'frames')
os.makedirs(out, exist_ok=True)
for r in csv.DictReader(open(os.path.join(HERE, 'eval_set.tsv')), delimiter='\t'):
    im = Image.open(os.path.join(RESULTS, r['source'])).convert('RGB')
    im.thumbnail((640, 640))
    im.save(os.path.join(out, r['frame']), quality=80)
print('frames in', out)
