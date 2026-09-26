#!/bin/bash
# #287 offline falsifier, against the COMMITTED override tree.
#
# goldencorr287/falsify.sh pointed at an untracked scratch/ov and scratch
# scorer that never landed. This one derives the override-aware scorer from
# master's score_sweep.py at run time (one inserted lookup, keyed suite/test,
# the shape proposed in goldencorr287/request-toolsmith.md) and points it at
# docs/testing/golden_overrides. A = stock scorer, B = derived scorer; every
# row is diffed A vs B.
#
#   falsify.sh <captures dir> [<captures dir> ...]
set -eu
L=$(cd "$(dirname "$0")" && pwd)
T=$(cd "$L/../../.." && pwd)
G=${GOLDENS:-/home/justin/goldens/results}
OV="$T/docs/testing/golden_overrides"
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT

python3 - "$T/docs/testing/score_sweep.py" "$W/score_sweep_ov.py" <<'EOF'
import sys
src = open(sys.argv[1]).read()
anchor = '        gp = os.path.join(goldens, suite, test + ".png")\n'
assert src.count(anchor) == 1, "score_sweep.py lookup line moved; update falsify.sh"
hook = anchor + (
    '        _ov = os.path.join(os.environ["GOLDEN_OVERRIDES"], suite, test + ".png")\n'
    '        if os.path.exists(_ov):\n'
    '            gp = _ov\n')
open(sys.argv[2], "w").write(src.replace(anchor, hook))
EOF
# Any sibling module score_sweep imports resolves from the real tree.
export PYTHONPATH="$T/docs/testing${PYTHONPATH:+:$PYTHONPATH}"

for c in "$@"; do
    n=$(basename "$(dirname "$c")")
    python3 "$T/docs/testing/score_sweep.py" --flat --out "$c" --goldens "$G" \
        --tsv "$W/$n.A.tsv" >/dev/null
    GOLDEN_OVERRIDES="$OV" python3 "$W/score_sweep_ov.py" \
        --flat --out "$c" --goldens "$G" --tsv "$W/$n.B.tsv" >/dev/null
    echo "== $n"
    python3 - "$W/$n.A.tsv" "$W/$n.B.tsv" <<'EOF'
import csv, sys
a = {(r["suite"], r["test"]): r for r in csv.DictReader(open(sys.argv[1]), delimiter="\t")}
b = {(r["suite"], r["test"]): r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
assert a.keys() == b.keys(), "row sets differ"
assert a, "no rows scored"
cols = ("status", "differing", "max_rgb", "max_a", "off_by_one")
moved = [k for k in a if any(a[k][c] != b[k][c] for c in cols)]
sa = sum(int(a[k]["differing"]) for k in a)
sb = sum(int(b[k]["differing"]) for k in b)
print(f"rows {len(a)}  sum px A {sa}  B {sb}  moved {len(moved)}")
for k in moved:
    print("  moved", "::".join(k), {c: (a[k][c], b[k][c]) for c in cols})
for k in a:
    if k[1] == "TexFmt_R6G5B5":
        print("  ", "::".join(k), "A", a[k]["status"], a[k]["differing"], "B", b[k]["status"], b[k]["differing"])
EOF
done
