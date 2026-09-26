#!/bin/bash
# #287 offline falsifier: re-score real sweep captures with the stock scorer
# against the upstream goldens (A) and with the override-aware scratch copy
# against the same goldens plus one console-sourced override (B). Every row of
# the two suites that carry a TexFmt_R6G5B5 is diffed A vs B.
#
#   falsify.sh <captures dir> [<captures dir> ...]
set -eu
L=$(cd "$(dirname "$0")" && pwd)
T=$(cd "$L/../../.." && pwd)
G=/home/justin/goldens/results
for c in "$@"; do
    n=$(basename "$(dirname "$c")")
    python3 "$T/docs/testing/score_sweep.py" --flat --out "$c" --goldens "$G" \
        --tsv "$L/scratch/$n.A.tsv" >/dev/null
    GOLDEN_OVERRIDES="$L/scratch/ov" python3 "$L/scratch/score_sweep_patched.py" \
        --flat --out "$c" --goldens "$G" --tsv "$L/scratch/$n.B.tsv" >/dev/null
    echo "== $n"
    python3 - "$L/scratch/$n.A.tsv" "$L/scratch/$n.B.tsv" <<'EOF'
import csv, sys
a = {(r["suite"], r["test"]): r for r in csv.DictReader(open(sys.argv[1]), delimiter="\t")}
b = {(r["suite"], r["test"]): r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
assert a.keys() == b.keys(), "row sets differ"
cols = ("status", "differing", "max_rgb", "max_a", "off_by_one")
moved = [k for k in a if any(a[k][c] != b[k][c] for c in cols)]
exact_a = sum(a[k]["differing"] == "0" for k in a)
print(f"rows {len(a)}  exact A {exact_a}  exact B {sum(b[k]['differing'] == '0' for k in b)}  moved {len(moved)}")
for k in moved:
    print("  moved", "::".join(k), {c: (a[k][c], b[k][c]) for c in cols})
for k in a:
    if k[1] == "TexFmt_R6G5B5":
        print("  ", "::".join(k), "A", a[k]["status"], a[k]["differing"], "B", b[k]["status"], b[k]["differing"])
EOF
done
