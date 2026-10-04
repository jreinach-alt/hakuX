#!/bin/bash
# lane.uberspike569 attempt 8: the third queueing of the six requests the 16:23-16:29 PDT wipe took
# (BUILD.md section 9). Same refs, flags and predictions as section 8; soaks hard-pinned to the Nova.
set -u
R=docs/testing/request.sh
P=docs/testing/predictions
LOG=docs/lanes/uberspike569/host/requeue3.log
: > "$LOG"
SUITES="3D primitive,Attrib float,Attrib setter,Clear,Depth buffer,Fog,Fog coord vec4,Fog gen,Fog vsh,Front face,Lighting Two Sided,Lighting accumulation,Lighting control,Lighting normals,Lighting range,Lighting spotlight,Material alpha,Material color,Material color source,Point params,Point size,Shade model,Specular,Specular back,Texgen,Texgen with texture matrix,Texture Matrix,Texture format,Vertex shader independence tests,Vertex shader rounding tests,Vertex shader swizzle tests,Viewport,W param,Weight setter,Window clip,Zero stride"
q() { echo "== $1" >> "$LOG"; shift; "$R" --who uberspike569 --issue 569 "$@" >> "$LOG" 2>&1; echo "exit=$?" >> "$LOG"; }

q "E H" --purpose "#569 E pixel arm H (6bec23c3f4, GPL 4), third queueing after the 16:25 wipe; pairs with 1790724542-uberspike569-1360739" \
  --program pgraph --suites "$SUITES" --ref 6bec23c3f4 --runs 2 --priority arm \
  --expect "$P/uberspike569-gpl-pixels.json"

DOA=54430006-Dead_or_Alive_1_Ultimate.xiso.iso
for arm in "A 23543417aa" "B 752b4f0f7b" "H 6bec23c3f4"; do
  set -- $arm
  q "DOA $1" --purpose "#569 DOA cold soak arm $1 ($2), third queueing after the 16:25 wipe" \
    --title "$DOA" --route survey --seconds 440 --perflog --device nova --hard-pin --ref "$2" \
    --expect "$P/uberspike569-gpl-doa-soak.json"
done

KAB=43560001-Kabuki_Warriors.xiso.iso
for arm in "A 8b15159b2f" "B2 d0152f9c44"; do
  set -- $arm
  q "Kabuki $1" --purpose "#569 Kabuki cold soak arm $1 ($2), third queueing after the 16:25 wipe" \
    --title "$KAB" --route kabuki-warriors --seconds 600 --perflog --device nova --hard-pin --ref "$2" \
    --expect "$P/uberspike569-gpl-kabuki-soak.json"
done
