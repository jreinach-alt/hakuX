#!/bin/bash
# Which levers each reading's build already carries: for every ref, whether
# the fold commit of #475 (pg->lock at the flip), #479 (download coalescing),
# #518 (display pre-download deferral), #528 (idle halt, #525) and #536 is an
# ancestor. Run from the lane's worktree.
folds="475:bf60a2b5b8 479:de2ed0f50f 518:2e36e51d5e 528:19d39f0a25 536:9286e2d7c3"
while read -r ref; do
  [ -z "$ref" ] && continue
  line="$ref"
  git cat-file -e "$ref^{commit}" 2>/dev/null || { echo "$ref: not in this clone"; continue; }
  line="$line $(git log -1 --format=%cs "$ref")"
  for f in $folds; do
    n=${f%%:*}; s=${f#*:}
    if git merge-base --is-ancestor "$s" "$ref"; then line="$line #$n:yes"; else line="$line #$n:no"; fi
  done
  echo "$line"
done <<'EOF'
02299ec656
c0db2c0bdc
37b1b81931
f82e7e87fe
677ae13af8
e884ad260e
c6e2be0936
a593d8eb85
a5b5b628f2
06e73e9f5e
9d3656f263
9e7f8418dc
3540bf2a69
6aaa8197c5
d0e30924f8
8a64c7d41e
09fdca3ba1
EOF
