#!/usr/bin/env python3
"""Register the shadetie224b arm (run once, from the repo root).

usage: register_b.py SCORES_TSV A_REF B_REF
SCORES_TSV is any recent scores1.tsv over the 13 lit suites; it only supplies
the capture names, so every leg is named individually.
"""
import csv
import json
import subprocess
import sys

scores, a_ref, b_ref = sys.argv[1:4]
OUT = 'docs/testing/predictions/shadetie224b-celsius-lt.json'

PATHS = ('Fixed', 'W_Fixed')
MOVERS = ('QuadStrip_Flat_First', 'QuadStrip_Flat_Last', 'Quad_Flat_First',
          'Quad_Flat_Last', 'TriFan_Flat_First', 'TriFan_Flat_Last',
          'TriStrip_Flat_First', 'TriStrip_Flat_Last', 'Tri_Flat_First')
ZEROS = ('Poly_Flat_First', 'Poly_Flat_Last', 'Tri_Flat_Last')
EXPECT = ['Shade_model/%s_%s' % (p, t) for p in PATHS for t in MOVERS + ZEROS]

SUITES = ('Shade model,Lighting accumulation,Lighting control,Lighting normals,'
          'Lighting range,Lighting spotlight,Lighting Two Sided,Material alpha,'
          'Material color,Material color source,Specular,Specular back,'
          'SetVertexData')

rows = list(csv.DictReader(open(scores), delimiter='\t'))
keys = sorted('%s/%s' % (r['suite'], r['test']) for r in rows)


def no_lighting_block(k):
    suite, test = k.split('/')
    # LIGHTING_ENABLE false (shade_model_tests.cpp:397,
    # lighting_control_tests.cpp:397) or a TEX0-only final combiner: no
    # lighting code reaches the pixel.
    if suite == 'Shade_model':
        return test.startswith(('Prog', 'FixedTex', 'W_FixedTex'))
    if suite == 'Lighting_control':
        return test.startswith('VS_')
    return False


must_not_move = [k for k in keys if no_lighting_block(k)]
must_not_regress = [k for k in keys
                    if k not in EXPECT and k not in must_not_move]

PREDICTION = (
    "#224 family B: vsh-ff.c's light loop computes with the Celsius lighting "
    "unit's own arithmetic, ported bit for bit from envytools "
    "(nvhw/pgraph_celsius_xfrm.c pgraph_celsius_lt_full: truncating 14-bit "
    "lt_mul/lts_mul/lt_add3/lts_add, the 64-entry-table lt_rcp, inputs "
    "through xf_s2lt), in place of float32 after lt(). Offline "
    "(docs/lanes/shadetie224/price.py --three, celsius_lt.py), the model, "
    "with nothing fitted, gives all nine Shade model flat colours including "
    "normal 3's blue 60 (float32 lands one ulp under the 13-bit step) and "
    "normal 1's 179; Lighting range Directional's specular byte 203, so its "
    "flat block stays (255,255,224) (lt(N) alone gave 204 and refuted "
    "shadetie224); and 127 for five 0.1 ambients (Lighting accumulation "
    "Directional-5). The GLSL helpers match the Python port on 60,000 random "
    "operands. EXPECT = 0: the 18 Fixed/W_Fixed Flat captures carrying B "
    "(ours (0,85,59), silicon (0,85,60)) and the six B-free Flat ones. "
    "MUST_NOT_MOVE: Shade model Prog*/FixedTex*/W_FixedTex* and Lighting "
    "control VS_*_LightOff: lighting is off or the diffuse never reaches the "
    "pixel, so no LT code runs. MUST_NOT_REGRESS: every other capture in "
    "the 13 lit suites, named individually, including the 20 that lt(N) "
    "broke and all 24 Fixed/W_Fixed Smooth. Where the model is silicon's "
    "arithmetic, a lit byte moves only toward the golden; Lighting "
    "accumulation Point/Spot, where ours is +1 over silicon on master "
    "(52/51, 76/75, 103/102), are the rows the truncation should improve. "
    "WORLD IN WHICH IT FAILS: Lighting_range/Directional moves off 224 "
    "(66,328 as before), or Lighting control / Specular get worse by 1-LSB "
    "blocks: then NV2A's LT is not Celsius's, or a stage I ported (the "
    "local-light attenuation input (1, d, d^2), the spot factor rounding, "
    "the per-light specular fold) is not silicon's, and the regressing "
    "suite names which. Spot captures carry the one un-modelled stage "
    "(envytools: XXX spotlight) and are the likeliest to move either way.")

args = ['python3', 'docs/testing/ab_compare.py', '--register', OUT,
        '--who', 'lane.shadetie224b', '--issue', '224',
        '--a-ref', a_ref, '--b-ref', b_ref,
        '--prediction', PREDICTION, '--disc-suites', SUITES]
for k in EXPECT:
    args += ['--expect-value', '%s=0' % k]
for k in must_not_move:
    args += ['--must-not-move', k]
rc = subprocess.call(args)
if rc:
    sys.exit(rc)

# ab_compare has no --must-not-regress flag; the judge reads the list from
# the file.
with open(OUT) as fh:
    exp = json.load(fh)
exp['must_not_regress'] = must_not_regress
text = json.dumps(exp, indent=2) + '\n'
json.loads(text)
with open(OUT, 'w') as fh:
    fh.write(text)
print('expect %d  must_not_move %d  must_not_regress %d'
      % (len(EXPECT), len(must_not_move), len(must_not_regress)))
