"""Hand-score the refs6743-disc arm pair's Surface_as_vertex_array captures
against the console root (the suite has no published golden)."""
import os
import sys

import numpy as np
from PIL import Image

G = ('/home/justin/hakux-work/hardware/runs/2026-09-25-refs6743/console-run/'
     'console/Surface_as_vertex_array')
R = '/home/justin/hakux-work/dispatch/results/'
ARMS = (('base', '1790368380-vtxarr262-base-iso-1676913'),
        ('fix', '1790368384-vtxarr262-fix-iso-1679009'))
TESTS = ('DynamicUpdateLoop', 'LinearDiffuseArray', 'MultiStream',
         'RenderScalePattern', 'SwizzledDiffuseArray')


def load(p):
    return np.asarray(Image.open(p).convert('RGB')).astype(int)


print(sorted(os.listdir(G)))
for t in TESTS:
    gp = [f for f in os.listdir(G) if f.startswith(t)]
    if not gp:
        print(t, 'no console golden')
        continue
    g = load(os.path.join(G, gp[0]))
    row, caps = [t], {}
    for arm, r in ARMS:
        c = load(R + r + '/captures1/Surface_as_vertex_array::' + t + '.png')
        caps[arm] = c
        if c.shape != g.shape:
            row.append('%s: shape %s vs %s' % (arm, c.shape, g.shape))
            continue
        d = np.abs(c - g).max(axis=2)
        row.append('%s: %d px maxd %d' % (arm, (d > 0).sum(), d.max()))
    row.append('base==fix' if np.array_equal(caps['base'], caps['fix'])
               else 'arms differ')
    print(' | '.join(row))

for arm, r in ARMS + (('console', None),):
    if r:
        p = R + r + '/captures1/Surface_as_vertex_array::DynamicUpdateLoop.png'
    else:
        p = os.path.join(G, [f for f in os.listdir(G)
                             if f.startswith('DynamicUpdateLoop')][0])
    c = load(p)
    cols, n = np.unique(c.reshape(-1, 3), axis=0, return_counts=True)
    print(arm, [(tuple(int(v) for v in x), int(k))
                for x, k in zip(cols, n) if k > 1000])
sys.exit(0)
