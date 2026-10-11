# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# and ok/bad/check. Not executable, no shebang, no exit (see 55-localtime.sh).
#
# hangwatch: the HANG rule that pathfind's claim and hold stop on. A locked-up title
# is judged on its telemetry in about HANG_S, not waited out to the budget (owner,
# 2026-10-04). The module's own selftest is the evidence: real logcat lines, the
# Whiteout shape, and the cases that must NOT trip (a busy guest, an idling vCPU, a
# moving screen, audio still producing, no telemetry, a press that changes things).

echo "== hangwatch: a locked-up title is caught on telemetry, not waited out"

check "hangwatch selftest passes (real logcat lines, the Whiteout shape, the no-trip cases)" \
    python3 "$REPO/docs/testing/hangwatch.py" selftest
