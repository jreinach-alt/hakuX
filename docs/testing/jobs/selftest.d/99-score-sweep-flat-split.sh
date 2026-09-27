# Sourced by ../selftest.sh with the harness already built: $T, $REPO, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# score_sweep.py --flat splits the file list across workers (#500). A flat run
# is ONE directory, and mapping score_dir over `dirs` gave the whole run to one
# worker: 755 captures scored serially in ~10 min while the device stayed held.
# The split must change nothing but the wall time, so the TSV from --jobs 1 and
# --jobs 4 must be byte-identical, and --jobs 4 must really make more than one
# work item. A mutant that hands the whole list to every chunk scores each
# capture four times; the fold hides that from the TSV, so the capture count
# in the summary line is what catches it.
#
# NUMPY. The CI runner has no numpy or PIL. As in 83-blank-rule.sh, the image
# stack is built in a venv under $T when absent (reusing 83's if it exists);
# if that cannot be done it says SKIP in those words and counts nothing.

echo "== score_sweep --flat: the file list is split across workers, rows unchanged"
SSPY=""
if python3 -c 'import numpy, PIL' >/dev/null 2>&1; then
    SSPY=python3
elif [ -x "$T/blank-venv/bin/python" ] \
     && "$T/blank-venv/bin/python" -c 'import numpy, PIL' >/dev/null 2>&1; then
    SSPY="$T/blank-venv/bin/python"
elif python3 -m venv "$T/split-venv" >/dev/null 2>&1 \
     && timeout 300 "$T/split-venv/bin/pip" install -q numpy pillow >/dev/null 2>&1 \
     && "$T/split-venv/bin/python" -c 'import numpy, PIL' >/dev/null 2>&1; then
    SSPY="$T/split-venv/bin/python"
fi

SSSRC="$REPO/docs/testing/score_sweep.py"
if [ -z "$SSPY" ]; then
    echo "  SKIP score_sweep flat split: no numpy/PIL and no venv could be built" \
         "-- the fixture below did NOT run"
else
    SS="$T/flat-split"; rm -rf "$SS"; mkdir -p "$SS/cap" "$SS/gold/SuiteA" "$SS/gold/SuiteB" "$SS/mut"
    cat > "$SS/mk.py" <<'EOF'
import sys
import numpy as np
from PIL import Image
root = sys.argv[1]
def save(path, seed):
    a = np.zeros((96, 96, 4), np.uint8)
    a[..., 3] = 255
    a[70:90, 10:10 + seed * 8, :3] = (40 * seed % 256, 90, 200)
    Image.fromarray(a, "RGBA").save(path)
# Nine captures: six colour pairs (three exact, three differing), one _ZB
# pair differing by one depth step, one with no golden, one unreadable.
for i in range(6):
    s, t = ("SuiteA" if i < 3 else "SuiteB"), "T%d" % i
    save("%s/gold/%s/%s.png" % (root, s, t), i + 1)
    save("%s/cap/%s::%s.png" % (root, s, t), i + 1 if i % 2 == 0 else i + 2)
g = np.full((96, 96, 4), 128, np.uint8)
o = g.copy(); o[50:60, 50:60, 1] = 129        # z24 low byte +1: exact (+-1)
Image.fromarray(g, "RGBA").save(root + "/gold/SuiteA/Depth_ZB.png")
Image.fromarray(o, "RGBA").save(root + "/cap/SuiteA::Depth_ZB.png")
save(root + "/cap/SuiteB::NoGolden.png", 2)
save(root + "/gold/SuiteB/Broken.png", 3)
open(root + "/cap/SuiteB::Broken.png", "wb").write(b"\x89PNG trunc")
open(root + "/cap/run.log", "w").write("not a capture\n")
EOF
    "$SSPY" "$SS/mk.py" "$SS"
    ss_run() {  # <score_sweep.py> <jobs> <tsv>
        "$SSPY" "$1" --out "$SS/cap" --goldens "$SS/gold" --flat --jobs "$2" \
            --tsv "$3" 2>&1; }
    SS1=$(ss_run "$SSSRC" 1 "$SS/j1.tsv")
    SS4=$(ss_run "$SSSRC" 4 "$SS/j4.tsv")
    sshas() { printf '%s\n' "$2" | grep -qE -- "$1"; }
    check "--jobs 1 scores all nine captures once (positive control)" \
          sshas '^9 tests from 1 runs \(9 captures, 0 repeated\)$' "$SS1"
    check "  and makes ONE work item, the old behaviour" \
          sshas '^score_sweep: flat run split into 1 work items over 10 files$' "$SS1"
    check "--jobs 4 makes four work items" \
          sshas '^score_sweep: flat run split into 4 work items over 10 files$' "$SS4"
    check "  and still scores each capture exactly once" \
          sshas '^9 tests from 1 runs \(9 captures, 0 repeated\)$' "$SS4"
    check "the fixture's TSV has a header and nine rows" \
          [ "$(wc -l < "$SS/j4.tsv" 2>/dev/null)" = 10 ]
    check "  with a no-golden, an unreadable and a depth row among them" \
          bash -c "grep -q 'NoGolden	False	no-golden' '$SS/j4.tsv' && grep -q 'Broken	False	unreadable' '$SS/j4.tsv' && grep -q '^SuiteA	Depth_ZB	False	ok	100	' '$SS/j4.tsv'"
    check "the TSV from --jobs 1 and --jobs 4 is byte-identical" \
          cmp -s "$SS/j1.tsv" "$SS/j4.tsv"

    # Mutant: every chunk gets the whole list. Prove the sed bit first.
    sed 's/names\[i:i + step\])/names)/' "$SSSRC" > "$SS/mut/score_sweep.py"
    check "mutant (whole list per chunk) differs from the scorer" \
          bash -c "! cmp -s '$SSSRC' '$SS/mut/score_sweep.py'"
    SSM=$(ss_run "$SS/mut/score_sweep.py" 4 "$SS/mut.tsv")
    check "  and its summary counts every capture four times" \
          sshas '^9 tests from 1 runs \(36 captures, 27 repeated\)$' "$SSM"
fi
