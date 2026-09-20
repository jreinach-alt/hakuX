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
x1a7cnt()   { printf '%s\n' "$2" | grep -cF -- "$1"; }

check "the model reproduces every pinned golden half" \
      [ "$(x1a7cnt ' ok' "$X1A7")" -ge 16 ]
check "  and reports no mismatch" \
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
check "the selftest's own verdict is a pass" x1a7has "all checks pass" "$X1A7"
