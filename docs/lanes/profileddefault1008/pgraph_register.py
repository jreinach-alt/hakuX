#!/usr/bin/env python3
"""Register the pgraph safety-net prediction for TU_AUTOTUNE_ALGO=profiled.

    python3 docs/lanes/profileddefault1008/pgraph_register.py <ref>

Same binary, same ref, both arms: A has no TU_AUTOTUNE_ALGO, B has
TU_AUTOTUNE_ALGO=profiled via --env. profiled and bandwidth are both Turnip
binning choices (sysmem vs. GMEM tiling), the same axis flip474's sysmem
flag exercises, so this reuses flip474-sysmem-pgraph.json's 27-suite list
and risk surface (MSAA resolves, loadOp/storeOp DONT_CARE, occlusion
counts).
"""
import json
import subprocess
import sys

REF = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
P = 'docs/testing/predictions/'

env = json.load(open(P + 'flip474-sysmem-pgraph.json'))
cmd = ['python3', 'docs/testing/ab_compare.py', '--register',
       P + 'profileddefault1008-pgraph.json', '--who', 'lane.profileddefault1008',
       '--issue', '433,474', '--a-ref', REF, '--b-ref', REF,
       '--disc-suites', ','.join(env['disc']['suites']),
       '--disc-skip-tests', ','.join(env['disc']['skip_tests']),
       '--prediction',
       '#433/#474: ApplyRenderMode (xemu_android.cpp) now sets '
       'TU_AUTOTUNE_ALGO=profiled via a per-game override or the compiled '
       'default; A has no TU_AUTOTUNE_ALGO (bandwidth, Turnip\'s own '
       'default), B sets it to profiled via --env on the same apk. Both '
       'are driver-side binning-algorithm choices (sysmem vs. GMEM '
       'tiling), the same axis flip474-sysmem-pgraph.json already cleared '
       'for the sysmem/bandwidth pair; this prediction is that profiled '
       'does not move any capture either, for the same reason (same '
       'shaders, same fixed-function state, same attachment formats).']
for g in env['must_not_move']:
    cmd += ['--must-not-move', g]
subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
print('profileddefault1008-pgraph.json', REF[:10])
