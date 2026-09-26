#!/bin/bash
# Registers docs/testing/predictions/cull13-linemode-cull.json (run once,
# before any device arm; the refs are the hunk commit and its master parent).
set -euo pipefail
cd "$(dirname "$0")/../../.."
python3 docs/testing/ab_compare.py \
    --register docs/testing/predictions/cull13-linemode-cull.json \
    --who lane.cull13 --issue 13 \
    --prediction "$(cat docs/lanes/cull13/prediction.txt)" \
    --a-ref 02374a6847 --b-ref d750443b2a \
    --must-not-move 'Front_face/FrontFace_FM_*' \
    --must-not-move 'Shade_model/ProgLM_*' \
    --must-not-move 'Line_width/*' \
    --must-not-move '3D_primitive/Lines*' \
    --must-not-move '3D_primitive/LineStrip*' \
    --must-not-move '3D_primitive/LineLoop*' \
    --expect-count better=12 --expect-count worse=0 \
    --disc-suites Front_face,Shade_model,Line_width,3D_primitive
