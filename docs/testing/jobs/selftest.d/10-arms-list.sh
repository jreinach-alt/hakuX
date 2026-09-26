# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh list: the live prediction is seen as WOULD QUEUE, and the committed
# history is fenced behind the watermark.
#
# Consumes the fixtures selftest.sh built: $EXP, the goldens tree, arms/since.
# FIRST of the arms fragments (10..50). They share one dispatcher queue and
# each consumes the state the one before it left, so their order is fixed.

echo "== arms.sh list"
out=$(bash "$HERE/arms.sh" list 2>&1)
check "list names the live prediction as WOULD QUEUE" grep -q "WOULD QUEUE .*selftest-live.json.*suites=\[Blend surface,Color mask blend\]" <<< "$out"
check "list fences the committed history behind the watermark" grep -q "older than the watermark" <<< "$out"
