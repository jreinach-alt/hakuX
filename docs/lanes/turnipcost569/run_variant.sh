#!/usr/bin/env bash
#   run_variant.sh <variant> <noopt|opt> [reps=5]
# Generate the catalogue under one generator variant and time it on the host
# Turnip. Writes $S/res/<variant>-<gl>.{gen.log,tsv,samples}.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$(realpath -m "${OUT:-$HERE/../../../.scratch}")"
V="$1"; GL="$2"; REPS="${3:-5}"
mkdir -p "$S/res"
bash "$HERE/gen/run_gen.sh" "$V" "$GL" 2> "$S/res/$V-$GL.gen.log"
bash "$HERE/run_harness.sh" "$S/out-$V-$GL/manifest.txt" "$REPS" "$S/res/$V-$GL.samples" \
    > "$S/res/$V-$GL.tsv" 2> "$S/res/$V-$GL.harness.log"
cp "$S/out-$V-$GL/manifest.txt" "$S/res/$V-$GL.manifest"
echo "done $V-$GL: $(($(wc -l < "$S/res/$V-$GL.tsv") - 1)) compiles; load $(cut -d' ' -f1-3 /proc/loadavg)"
