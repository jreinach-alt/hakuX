# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# x1a7_forward_model.py: the evidence for any X1A7R8G8B8 change is sixteen
# golden swatch halves, and a model that fits them is only worth something if
# the rivals do NOT. This gate runs the model's own selftest, which needs no
# disc and no goldens, and asserts on the words rather than the exit status --
# a script that dies early also "passes" a bare `rc == 0` check.

echo "== x1a7_forward_model.py: two rules, sixteen goldens, four refuted rivals"
X1A7=$(python3 "$REPO/docs/testing/x1a7_forward_model.py" --selftest 2>&1)
x1a7has()   { printf '%s\n' "$2" | grep -qF -- "$1"; }
# A NEGATED helper, not `! x1a7has ...`: check() runs its arguments as "$@",
# so a leading `!` is looked up as a command name, fails to execute, and the
# assertion reports `bad` whatever the output said. That is the same shape as
# P1 -- a guard that reports on something other than what it measured.
x1a7hasnt() { ! printf '%s\n' "$2" | grep -qF -- "$1"; }

# AUDIT L2: this used to count every line containing ' ok' and require >= 16.
# The selftest prints eighteen such lines -- sixteen goldens plus the two
# coincidence checks -- so the assertion passed with two golden halves
# mismatching, and was sound only because the separate MISMATCH check caught
# them. Count the GOLDEN lines specifically, and require exactly sixteen.
x1a7goldens() { printf '%s\n' "$1" | grep -c '^  golden .* ok$'; }

check "all sixteen pinned golden halves reproduce, and exactly sixteen" \
      [ "$(x1a7goldens "$X1A7")" -eq 16 ]
check "  and no golden half mismatches" \
      x1a7hasnt "MISMATCH" "$X1A7"
# The point of the rivals: a pass must mean the goldens SELECTED these rules,
# not merely that some rule fits. If a rival stops being refuted, either the
# model lost its discriminating power or the golden table was edited to match
# the model -- both are the failure this section exists to catch.
check "today's identity destination alpha is refuted" \
      x1a7has "R1 identity (what both renderers do today)     refuted" "$X1A7"
check "  as is truncation without bit replication" \
      x1a7has "R1 truncate to 7 bits, no replication          refuted" "$X1A7"
check "  as is a readback that ignores the pad bit" \
      x1a7has "R2 no pad bit (readback is the stored alpha)   refuted" "$X1A7"
check "  as is a pad bit applied to the whole channel" \
      x1a7has "R2 pad bit as a whole-channel constant         refuted" "$X1A7"
check "no rival survives" x1a7hasnt "NOT REFUTED" "$X1A7"

# AUDIT M1: the withdrawn --proposed mode computed the same function as the
# model. The selftest now PROVES that rather than asserting it, and these two
# checks are what stop the claim being quietly reinstated.
check "the write transform is still shown to equal R1" \
      x1a7has "the write transform is r1_blend_dst_alpha on all 256 values ok" "$X1A7"
check "  and the swatch alpha is still its fixed point" \
      x1a7has "the swatch alpha 0x22 is its fixed point                   ok" "$X1A7"
check "  so the suite is stated as unable to validate the implementation" \
      x1a7has "cannot distinguish them" "$X1A7"
# AUDIT M1-R: this check used to grep $X1A7 -- the --selftest output -- for
# "scoring the PROPOSED implementation", a string only score() ever printed,
# on the --proposed path. It was green against the exact code it forbids and
# always had been: a guard that cannot fail. Grep the SOURCE for the wiring,
# and separately prove the flag changes no behaviour.
X1A7SRC=$(cat "$REPO/docs/testing/x1a7_forward_model.py")
# AUDIT L2b-1: a POSITIVE control first. If the read fails, X1A7SRC is empty
# and every x1a7hasnt over it reports ok -- a negated check over an empty
# artifact, which is the shape M1-R itself was. Anchor on a string the file
# must contain, so an empty read fails here instead of passing silently
# three lines down.
check "the model source was actually read" \
      x1a7has "def r1_blend_dst_alpha" "$X1A7SRC"
check "no --proposed mode is wired into argv" \
      x1a7hasnt "'--proposed' in sys.argv" "$X1A7SRC"
check "  and no separate prediction set exists for it to score" \
      x1a7hasnt "def proposed_predictions" "$X1A7SRC"

check "the selftest's own verdict is a pass" x1a7has "all checks pass" "$X1A7"

# AUDIT H1: score() reported "0 of 32 modelled halves differ" and exited 0
# when it had opened no goldens at all. A run that reads nothing must FAIL.
echo "== x1a7_forward_model.py: a golden it never opened is not a golden that agreed"
X1A7N=$(python3 "$REPO/docs/testing/x1a7_forward_model.py" "$T/x1a7-no-such-goldens" 2>&1)
x1a7nrc=$?
check "scoring against an absent goldens root exits non-zero" [ "$x1a7nrc" -ne 0 ]
check "  and says nothing was compared, rather than that nothing differed" \
      x1a7has "compared 0 of 32 modelled halves" "$X1A7N"
check "  and calls it a failure in those words" \
      x1a7has "NOT compared -- this is a FAILURE, not agreement" "$X1A7N"
# ...and it must REPORT that, not die on an import. The runner has no numpy or
# PIL, so the first version of this section exited non-zero on an ImportError
# and the exit-code check above passed for a reason other than the guard --
# the same shape as H1 itself. Shadow the image stack and require the report.
# On the runner the shadow is a no-op because they are absent anyway, so this
# check exercises the real condition in both places.
X1A7SHADOW="$T/x1a7-shadow"; mkdir -p "$X1A7SHADOW"
printf 'raise ImportError("shadowed")\n' > "$X1A7SHADOW/numpy.py"
printf 'raise ImportError("shadowed")\n' > "$X1A7SHADOW/PIL.py"
X1A7I=$(PYTHONPATH="$X1A7SHADOW" python3 "$REPO/docs/testing/x1a7_forward_model.py" \
        "$T/x1a7-no-such-goldens" 2>&1)
check "with no image stack it still REPORTS rather than dying on the import" \
      x1a7has "NOT compared -- this is a FAILURE, not agreement" "$X1A7I"
check "  and does not leak a traceback instead of a verdict" \
      x1a7hasnt "Traceback (most recent call last)" "$X1A7I"

# AUDIT M1-R, behavioural half, CORRECTED per L2b-2. Comparing the two
# invocations against a NONEXISTENT root proved little: both return from the
# early `if not resolved:` branch before any prediction set is consulted, so a
# mode diverging only after goldens resolve looked identical to no mode at
# all. Use a root whose globs RESOLVE -- files that exist but are not images
# -- so both runs get past resolution and into the comparison path.
X1A7G="$T/x1a7-resolvable/suite"; mkdir -p "$X1A7G"
for x1a7c in DstAlpha_XA_Z1A7RGB8 DstAlpha_XA_O1A7RGB8 \
             1-DstAlpha_XA_Z1A7RGB8 1-DstAlpha_XA_O1A7RGB8; do
    : > "$X1A7G/$x1a7c.png"
done
X1A7R=$(python3 "$REPO/docs/testing/x1a7_forward_model.py" \
        "$T/x1a7-resolvable" 2>&1)
X1A7RP=$(python3 "$REPO/docs/testing/x1a7_forward_model.py" --proposed \
         "$T/x1a7-resolvable" 2>&1)
check "a golden that resolves but will not open is reported, not a crash" \
      x1a7has "NOT compared -- this is a FAILURE, not agreement" "$X1A7R"
check "  without leaking a traceback" \
      x1a7hasnt "Traceback (most recent call last)" "$X1A7R"
check "passing --proposed selects no different mode, past resolution" \
      [ "$X1A7RP" = "$X1A7R" ]
# What this still cannot prove: a mode diverging only once real goldens open.
# That needs goldens, which the runner does not have. The two source checks
# above are what actually forbid the mode; this is corroboration.
check "and no different mode before resolution either" \
      [ "$(python3 "$REPO/docs/testing/x1a7_forward_model.py" --proposed \
           "$T/x1a7-no-such-goldens" 2>&1)" = "$X1A7N" ]
