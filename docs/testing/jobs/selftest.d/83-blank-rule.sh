# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# score_sweep.is_blank(): a capture is `blank` when OURS is flat AND it painted
# over >= 1% of the image where the golden drew something (below the label
# band). The rule it replaced asked only "does the golden have > 4 colours",
# and a golden that is 99% background with a sliver of ink passes that -- so
# 15 near-exact captures were filed as blank and never triaged (#297). Each
# case below is a synthetic pair built so the old rule and the new one answer
# differently, or so one clause of the new rule is the only thing deciding it;
# and the old rule, restored as a mutant, must get the first case wrong.
#
# NUMPY. The CI runner has no numpy or PIL, and a behavioural check that skips
# there is a check that never runs where it gates. So when the image stack is
# absent the fragment builds it in a venv under $T (no system Python is
# touched). If that cannot be done either -- no network -- it says SKIP in
# those words and counts nothing as passed.

echo "== score_sweep.is_blank: blank means flat AND lost >= 1% of the golden's ink"
BLANKPY=""
if python3 -c 'import numpy, PIL' >/dev/null 2>&1; then
    BLANKPY=python3
elif python3 -m venv "$T/blank-venv" >/dev/null 2>&1 \
     && timeout 300 "$T/blank-venv/bin/pip" install -q numpy pillow >/dev/null 2>&1 \
     && "$T/blank-venv/bin/python" -c 'import numpy, PIL' >/dev/null 2>&1; then
    BLANKPY="$T/blank-venv/bin/python"
fi

# The rule's source shape, checkable with no image stack at all. Anchored on
# the code, not on a word the docstring also contains.
BLANKSRC="$REPO/docs/testing/score_sweep.py"
check "the scorer calls is_blank() to decide the blank status" \
      grep -qE '^        blank = is_blank\(o, g, LABEL_ROWS\)$' "$BLANKSRC"
check "  and the rule keys on the ink it lost, against BLANK_MIN_LOST" \
      grep -qE '^ +and lost\.sum\(\) >= BLANK_MIN_LOST \* flat\.shape\[0\]\)$' "$BLANKSRC"
check "  and no code line tests the golden's colour count" \
      bash -c "! grep -nE '^[^#]*gold_colours *> *4' '$BLANKSRC'"

if [ -z "$BLANKPY" ]; then
    echo "  SKIP is_blank behaviour: no numpy/PIL and no venv could be built" \
         "-- the synthetic pairs below did NOT run"
else
    mkdir -p "$T/blank-real" "$T/blank-mut" "$T/blank-noband"
    cp "$BLANKSRC" "$T/blank-real/score_sweep.py"
    # Mutant 1: the rule this replaced, golden-side "> 4 colours".
    sed 's/and lost\.sum() >= BLANK_MIN_LOST \* flat\.shape\[0\])/and len(gcols) > 4)/' \
        "$BLANKSRC" > "$T/blank-mut/score_sweep.py"
    # Mutant 2: the label band no longer masked out of the golden's ink.
    sed 's/^    ink\[:label_rows\] = False$/    pass/' \
        "$BLANKSRC" > "$T/blank-noband/score_sweep.py"
    cat > "$T/blank-cases.py" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import numpy as np
import score_sweep

H = W = 200          # 40,000 px; 1% is 400 px
BAND = 64


def img(bg=(0, 0, 0)):
    a = np.zeros((H, W, 4), np.int16)
    a[..., :3] = bg
    a[..., 3] = 255
    return a


def rainbow(a, y0, y1, x0, x1):
    """Paint a patch with many distinct colours, so the golden has > 4."""
    for y in range(y0, y1):
        for x in range(x0, x1):
            a[y, x, :3] = (40 + (x * 7) % 200, 40 + (y * 11) % 200, 99)
    return a


cases = []
# tiny ink: golden > 4 colours but only 0.25% ink below the band; ours flat.
cases.append(("tiny-ink", rainbow(img(), 100, 110, 100, 110), img(), False))
# large lost ink: 25% of the image drawn in the golden, ours flat background.
cases.append(("large-lost-ink", rainbow(img(), 100, 200, 0, 100), img(), True))
# flat ours with flat golden: nothing drew on either side, nothing was lost.
cases.append(("flat-both", img((30, 30, 30)), img((30, 30, 30)), False))
# lost ink just under and just over 1%, one colour so only `lost` decides.
g = img(); g[100:119, 100:120, :3] = (200, 0, 0)       # 380 px
cases.append(("lost-0.95pct", g, img(), False))
g = img(); g[100:121, 100:120, :3] = (200, 0, 0)       # 420 px
cases.append(("lost-1.05pct", g, img(), True))
# ink only in the label band: 25% of the image, ours flat below and above.
cases.append(("label-band-only", rainbow(img(), 0, 50, 0, 200), img(), False))
# ours is NOT flat: it drew a different large picture. Wrong, not blank.
o = rainbow(img(), 0, 200, 0, 200)
cases.append(("ours-not-flat", rainbow(img(), 100, 200, 0, 100), o[::-1].copy(), False))

for name, g, o, want in cases:
    got = score_sweep.is_blank(o, g, BAND)
    print("case %-16s want %-5s got %-5s %s" % (name, want, got,
          "ok" if got == want else "MISMATCH"))
EOF
    BLANKOUT=$("$BLANKPY" "$T/blank-cases.py" "$T/blank-real" 2>&1)
    blankhas()   { printf '%s\n' "$2" | grep -qE -- "$1"; }
    blankhasnt() { ! printf '%s\n' "$2" | grep -qE -- "$1"; }
    check "the driver ran all seven cases (positive control)" \
          [ "$(printf '%s\n' "$BLANKOUT" | grep -c '^case ')" -eq 7 ]
    check "tiny golden ink, flat ours -> ok"       blankhas '^case tiny-ink +want False got False +ok$' "$BLANKOUT"
    check "large lost ink, flat ours -> blank"     blankhas '^case large-lost-ink +want True +got True +ok$' "$BLANKOUT"
    check "flat ours, flat golden -> ok"           blankhas '^case flat-both +want False got False +ok$' "$BLANKOUT"
    check "lost 0.95% -> ok, 1.05% -> blank"       blankhas '^case lost-1\.05pct +want True +got True +ok$' "$BLANKOUT"
    check "  (the 0.95% side)"                     blankhas '^case lost-0\.95pct +want False got False +ok$' "$BLANKOUT"
    check "ink only in the label band -> ok"       blankhas '^case label-band-only +want False got False +ok$' "$BLANKOUT"
    check "ours not flat -> ok, however wrong"     blankhas '^case ours-not-flat +want False got False +ok$' "$BLANKOUT"
    check "  and no case mismatches"               blankhasnt 'MISMATCH|Traceback' "$BLANKOUT"

    # Mutants. First prove each sed changed the rule, or a mutant identical to
    # the real file would "fail to fail" for no reason worth reporting.
    check "mutant 1 (golden > 4 colours) differs from the scorer" \
          bash -c "! cmp -s '$BLANKSRC' '$T/blank-mut/score_sweep.py'"
    BLANKMUT=$("$BLANKPY" "$T/blank-cases.py" "$T/blank-mut" 2>&1)
    check "  and it calls the tiny-ink capture blank, as the old rule did" \
          blankhas '^case tiny-ink +want False got True +MISMATCH$' "$BLANKMUT"
    check "mutant 2 (label band unmasked) differs from the scorer" \
          bash -c "! cmp -s '$BLANKSRC' '$T/blank-noband/score_sweep.py'"
    BLANKNB=$("$BLANKPY" "$T/blank-cases.py" "$T/blank-noband" 2>&1)
    check "  and it calls the label-band-only capture blank" \
          blankhas '^case label-band-only +want False got True +MISMATCH$' "$BLANKNB"
fi
