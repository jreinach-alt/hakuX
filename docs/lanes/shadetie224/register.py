#!/usr/bin/env python3
"""Register the shadetie224 arm (run once, from the repo root)."""
import json
import subprocess
import sys

PATHS = ('Fixed', 'W_Fixed')
MOVERS = ('QuadStrip_Flat_First', 'QuadStrip_Flat_Last', 'Quad_Flat_First',
          'Quad_Flat_Last', 'TriFan_Flat_First', 'TriFan_Flat_Last',
          'TriStrip_Flat_First', 'TriStrip_Flat_Last', 'Tri_Flat_First')
ZEROS = ('Poly_Flat_First', 'Poly_Flat_Last', 'Tri_Flat_Last')

PREDICTION = (
    "#224 family B: vsh-ff.c append_lighting now rounds the eye-space normal "
    "with lt() (envytools xf_s2lt, the XF->LT input rounding the file already "
    "applies to every light register and vertex colour). Offline "
    "(docs/lanes/shadetie224/price.py) this reproduces master's blue 59 for "
    "Shade model normal 3 and gives silicon's 60, with all nine other lit "
    "golden colours, including the 178.5 tie for normal 1, unchanged. "
    "EXPECT: the 18 Fixed/W_Fixed Flat captures carrying family B (every "
    "differing pixel is ours (0,85,59) vs silicon (0,85,60); baseline "
    "1789968297-arms-primpv13-fix, e.g. Fixed_Quad_Flat 54,720, "
    "W_Fixed_QuadStrip_Flat 125,652) go to exactly 0. The six B-free ones "
    "(Poly_Flat_*, Tri_Flat_Last, both paths) stay 0; they move only if "
    "lt(N) changed a normal-0/4/5 colour, which price.py says it does not. "
    "WORLD IN WHICH MUST_MOVE FAILS: the tie is not the normal's input "
    "rounding but some other light-path precision (e.g. the lit value stored "
    "at a different width before the interpolator). Then the pixel moves to "
    "59 or 61, not 60, or not at all, and these captures stay nonzero. "
    "MUST_NOT_MOVE: Prog*/ProgTex*/ProgLM* run with LIGHTING_ENABLE false, so "
    "no lighting block is emitted and their GLSL is byte-identical. "
    "FixedTex*/W_FixedTex* draw with a TEX0-only final combiner, so the "
    "diffuse never reaches the pixel. A move there means lt() leaked outside "
    "the lighting block. NOT IN ANY LEG: the 12 Fixed/W_Fixed Smooth captures "
    "(family C, #38). Vertex 3's byte goes 59->60 there too, and the "
    "baseline's signed blue error is mixed (-1 dominant, +1 present), so they "
    "move by at most the area of vertex 3's triangles, in either direction. "
    "MUST_NOT_REGRESS: every other lit suite (Lighting *, Material *, "
    "Specular, Specular back, SetVertexData). lt(N) moves N by at most 2^-14 "
    "relative per component, so a lit byte moves by at most one "
    "colorPrecision step, and only near a boundary. If lt(N) is silicon's "
    "rule, those moves go toward the goldens. A capture that gets WORSE "
    "there refutes the mechanism, not the leg.")

SUITES = ('Shade model,Lighting accumulation,Lighting control,Lighting normals,'
          'Lighting range,Lighting spotlight,Lighting Two Sided,Material alpha,'
          'Material color,Material color source,Specular,Specular back,'
          'SetVertexData')

args = ['python3', 'docs/testing/ab_compare.py',
        '--register', 'docs/testing/predictions/shadetie224-ltnormal.json',
        '--who', 'lane.shadetie224', '--issue', '224',
        '--a-ref', '0a4e284536', '--b-ref', '6765c1f5e9',
        '--prediction', PREDICTION, '--disc-suites', SUITES]
for p in PATHS:
    for t in MOVERS + ZEROS:
        args += ['--expect-value', 'Shade_model/%s_%s=0' % (p, t)]
for g in ('Shade_model/Prog*', 'Shade_model/FixedTex*',
          'Shade_model/W_FixedTex*'):
    args += ['--must-not-move', g]
rc = subprocess.call(args)
if rc:
    sys.exit(rc)

# ab_compare has no --must-not-regress flag; the judge reads the list from
# the file (as wbuf31fix-topcut-grid.json and issue164-* set it).
PATH = 'docs/testing/predictions/shadetie224-ltnormal.json'
with open(PATH) as fh:
    exp = json.load(fh)
exp['must_not_regress'] = ['Lighting_*/*', 'Material_*/*', 'Specular/*',
                           'Specular_back/*', 'SetVertexData/*']
text = json.dumps(exp, indent=2) + '\n'
json.loads(text)
with open(PATH, 'w') as fh:
    fh.write(text)
