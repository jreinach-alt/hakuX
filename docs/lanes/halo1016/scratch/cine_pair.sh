#!/bin/sh
# cineread.py's timeline of two arms into scratch/<name>.md, then the plateau rows (+117..+199) of each arm.
# usage: cine_pair.sh <name> <A dir> <B dir>
W=/home/justin/hakux-work/wt/halo1016/docs/lanes/halo1016
out="$W/scratch/$1.md"
python3 "$W/cineread.py" "$2" "$3" > "$out" 2>&1
echo "cineread exit $? -> $out"
grep -n '^## \|^### timeline\|^| t-mark' "$out" | head -20
awk -F'|' '/^### timeline/ {arm=$0} /^\| [0-9]/ { t=$2+0; if (t >= 117 && t <= 199) print substr(arm, 15, 40) $0 }' "$out"
