#!/usr/bin/env bash
#
#   compare.sh <tag> <A spec> <B spec> [reps=5] [manifest filter regex]
#
# spec = <variant>:<noopt|opt>[:optsize], e.g. base:noopt, c7_lt_plain:noopt,
# base:opt:optsize. Generates both catalogues, interleaves them in one manifest
# (A and B of each pipeline on adjacent lines; vkharness runs reps round-robin)
# and times them in one process. Writes $S/res/<tag>.{tsv,samples,manifest,
# A.gen.log,B.gen.log} and prints compare.py's report.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$(realpath -m "${OUT:-$HERE/../../../.scratch}")"
TAG="$1"; A="$2"; B="$3"; REPS="${4:-5}"; FILTER="${5:-.}"
mkdir -p "$S/res"
gen() {  # spec side
    IFS=: read -r v gl fl <<< "$1"
    local flag=""
    [ "${fl:-}" = optsize ] && flag=--optimize-size
    bash "$HERE/gen/run_gen.sh" "$v" "$gl" "$S/out-$TAG-$2" $flag 2> "$S/res/$TAG.$2.gen.log"
}
gen "$A" A
gen "$B" B
python3 - "$S/out-$TAG-A/manifest.txt" "$S/out-$TAG-B/manifest.txt" "$FILTER" \
    > "$S/res/$TAG.manifest" <<'EOF'
import re, sys
a = [l.split() for l in open(sys.argv[1]) if l.strip()]
b = {l.split()[0]: l.split() for l in open(sys.argv[2]) if l.strip()}
for row in a:
    if not re.search(sys.argv[3], row[0]):
        continue
    print(" ".join(["A|" + row[0]] + row[1:]))
    print(" ".join(["B|" + row[0]] + b[row[0]][1:]))
EOF
bash "$HERE/run_harness.sh" "$S/res/$TAG.manifest" "$REPS" "$S/res/$TAG.samples" \
    > "$S/res/$TAG.tsv" 2> "$S/res/$TAG.harness.log"
echo "# $TAG: A=$A B=$B reps=$REPS load $(cut -d' ' -f1-3 /proc/loadavg)"
python3 "$HERE/compare.py" "$S/res/$TAG.tsv"
