"""Does a 30-s-apart frame pair tell a standing player from a moving one?
For each run dir, consecutive kept hold frames (and 'after' frames, ~4 s apart) -> change at the probe's
contrast-scaled step, plus the change between frames N apart (a 30-s window from 'after' frames)."""
import glob, os, sys
sys.path.insert(0, 'docs/testing/titles')
import numpy as np
import pathfind
from PIL import Image
import classify


def change(a, b):
    ga = pathfind.grey(a)
    std = float(np.asarray(ga.resize(classify.MOTION_SIZE, Image.BILINEAR), dtype=np.float64).std())
    step = min(classify.MOTION_PIXEL, max(4.0, pathfind.PROBE_DARK * std))
    return classify.motion(ga, pathfind.grey(b), pixel=step)[0], std


for run in sys.argv[1:]:
    for kind in ('hold', 'after'):
        fs = sorted(glob.glob(os.path.join(run, 'frames', '*-%s.jpg' % kind)))
        if len(fs) < 2:
            continue
        vals = []
        for a, b in zip(fs, fs[1:]):
            c, std = change(a, b)
            vals.append(c)
        # first vs last of the set: the whole window
        whole, _ = change(fs[0], fs[-1])
        v = np.array(vals)
        print('%-45s %-5s n=%2d  pair min %.3f med %.3f max %.3f  first-last %.3f  std0 %.0f' % (
            os.path.basename(run), kind, len(fs), v.min(), np.median(v), v.max(), whole, std))
