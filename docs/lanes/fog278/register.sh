#!/bin/bash
# Registers the #278 arm: a = master before the hunk, b = the one-commit hunk.
# runs_per_arm 2 is added after --register (no flag for it), as pshqueue did.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
out=docs/testing/predictions/fog278-inf-m0.json
S=Fog_exceptional_value
python3 docs/testing/ab_compare.py --register "$out" \
  --who lane.fog278 --issue 278 \
  --a-ref 6550967a5e --b-ref eb6ce3a908 \
  --prediction "#278 (docs/lanes/cloud-278/NOTES.md): in the exp modes an infinite fog coordinate with fogParam.y == 0 is 0 * INF = 0 and runs the ordinary formula on x = bias - 1.5; every other cell keeps the special value, NaN stays special, linear keeps its special value at m = 0. MUST MOVE, structural (differing minus off-by-one): INF-FogExc-exp-* 9,029 -> 837 each and INF-FogExc-{exp_abs,exp2,exp2_abs}-* 4,096 -> 18 each, 85,268 -> 3,564 over the 16. The judge classes on differing, which counts one-step pixels, so the classes are NOT all better: the bias-1/m0 quad (f = 2^-8 exactly) becomes one-step in all 16 (our exp path rounds, silicon truncates; FogZeroBias quad 0 shows the same today). For exp that quad was structural, so the 4 exp captures go better (differing drops by the 4,096-px bias -1/m0 quad plus the rest of the structural). For exp_abs, exp2, exp2_abs that quad is exact today only because the special value 0 matches, so it turns 4,096 px one-step while the bias-1.5/m0 quad goes 4,096 structural -> 18: differing rises by about 18 and the 12 class worse. That is the predicted shape: better=4, worse=12, and the magnitude leg is read off the structural column. A worse capture with structural not falling by ~4,078, or an exp capture not near 837 structural, refutes the model; name the mode x abs cell. MUST NOT MOVE, with what would move each: NaN-FogExc-* (all six modes) move if NaN were treated like INF; INF-FogExc-linear-* and -linear_abs-* move if the exemption leaked to linear; FogExc-* and RCP-FogExc-* have m != 0 on every draw, so they move only if the m test is wrong; Fog_param/* and Fog/* have finite coordinates (flag stays 0.0); Fog_inf_coord/* uses the Fog base draw with density 0.025, m != 0." \
  --disc-suites "Fog,Fog param,Fog inf coord,Fog exceptional value" \
  --must-not-move "$S/NaN-FogExc-*" \
  --must-not-move "$S/INF-FogExc-linear-*" \
  --must-not-move "$S/INF-FogExc-linear_abs-*" \
  --must-not-move "$S/FogExc-*" \
  --must-not-move "$S/RCP-FogExc-*" \
  --must-not-move "Fog_param/*" \
  --must-not-move "Fog/*" \
  --must-not-move "Fog_inf_coord/*" \
  --expect-count better=4 \
  --expect-count worse=12
python3 - "$out" <<'EOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["runs_per_arm"] = 2
json.dump(d, open(p, "w"), indent=2)
open(p, "a").write("\n")
EOF
sha256sum "$out"
