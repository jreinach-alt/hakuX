# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# score_sweep.is_blank(): a capture is `blank` when OURS is flat, the golden
# has > 4 colours, AND ours painted over >= 1% of the image where the golden
# drew something (below the label band). The rule it replaced stopped at the
# golden's colour count, and a golden that is 99% background with a sliver of
# ink passes that -- so 15 near-exact captures were filed as blank and never
# triaged (#297). Dropping the colour count instead would call few-colour
# goldens (Stencil, W_param) blank: 436 `ok` rows on disk. Each case below is
# built so one clause is the only thing deciding it; the old rule and the
# rule without the colour count, restored as mutants, must each get their
# case wrong.
#
# NUMPY. The CI runner has no numpy or PIL, and a behavioural check that skips
# there is a check that never runs where it gates. So when the image stack is
# absent the fragment builds it in a venv under $T (no system Python is
# touched). If that cannot be done either -- no network -- it says SKIP in
# those words and counts nothing as passed.

echo "== score_sweep.is_blank: blank means flat, golden > 4 colours, AND lost >= 1% of its ink"
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
check "  and it still requires the golden to have > 4 colours" \
      grep -qE '^ +and len\(gcols\) > 4$' "$BLANKSRC"

if [ -z "$BLANKPY" ]; then
    echo "  SKIP is_blank behaviour: no numpy/PIL and no venv could be built" \
         "-- the synthetic pairs below did NOT run"
else
    mkdir -p "$T/blank-real" "$T/blank-mut" "$T/blank-noband" "$T/blank-nocount"
    cp "$BLANKSRC" "$T/blank-real/score_sweep.py"
    # Mutant 1: the rule this replaced, golden-side "> 4 colours" only.
    sed 's/and lost\.sum() >= BLANK_MIN_LOST \* flat\.shape\[0\])/and len(gcols) > 4)/' \
        "$BLANKSRC" > "$T/blank-mut/score_sweep.py"
    # Mutant 2: the label band no longer masked out of the golden's ink.
    sed 's/^    ink\[:label_rows\] = False$/    pass/' \
        "$BLANKSRC" > "$T/blank-noband/score_sweep.py"
    # Mutant 3: `lost` alone, the golden's colour count dropped.
    sed '/^ \+and len(gcols) > 4$/d' \
        "$BLANKSRC" > "$T/blank-nocount/score_sweep.py"
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
# lost ink just under and just over 1%, golden > 4 colours so only `lost` decides.
cases.append(("lost-0.95pct", rainbow(img(), 100, 119, 100, 120), img(), False))  # 380 px
cases.append(("lost-1.05pct", rainbow(img(), 100, 121, 100, 120), img(), True))   # 420 px
# few-colour golden: a one-colour quad over 25%, ours flat background. Lost is
# large, but a golden this flat is Stencil / W_param's shape, not a blank.
g = img(); g[100:200, 0:100, :3] = (200, 0, 0)
cases.append(("few-colour-golden", g, img(), False))
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
    check "the driver ran all eight cases (positive control)" \
          [ "$(printf '%s\n' "$BLANKOUT" | grep -c '^case ')" -eq 8 ]
    check "tiny golden ink, flat ours -> ok"       blankhas '^case tiny-ink +want False got False +ok$' "$BLANKOUT"
    check "large lost ink, flat ours -> blank"     blankhas '^case large-lost-ink +want True +got True +ok$' "$BLANKOUT"
    check "flat ours, flat golden -> ok"           blankhas '^case flat-both +want False got False +ok$' "$BLANKOUT"
    check "lost 0.95% -> ok, 1.05% -> blank"       blankhas '^case lost-1\.05pct +want True +got True +ok$' "$BLANKOUT"
    check "  (the 0.95% side)"                     blankhas '^case lost-0\.95pct +want False got False +ok$' "$BLANKOUT"
    check "few-colour golden, large lost -> ok"    blankhas '^case few-colour-golden +want False got False +ok$' "$BLANKOUT"
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
    check "mutant 3 (golden colour count dropped) differs from the scorer" \
          bash -c "! cmp -s '$BLANKSRC' '$T/blank-nocount/score_sweep.py'"
    BLANKNC=$("$BLANKPY" "$T/blank-cases.py" "$T/blank-nocount" 2>&1)
    check "  and it calls the few-colour golden blank" \
          blankhas '^case few-colour-golden +want False got True +MISMATCH$' "$BLANKNC"
fi
