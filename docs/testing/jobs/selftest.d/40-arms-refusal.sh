# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh: a request.sh refusal reaches the lane and is reconsidered when
# arms.sh changes -- and a structural skip is not.
#
# Registers two more predictions of its own ($EXP2, $EXP3) from the $A/$B refs
# selftest.sh resolved, and runs arms.sh over the queue 20/30 left standing.

echo "== arms.sh: a request.sh refusal reaches the lane, and is retried when arms.sh changes"
EXP2="$DISPATCH_DIR/expect/selftest-badkey.json"
python3 - "$EXP2" "$A" "$B" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.selftest", "issue": "1", "prediction": "a key that binds no golden",
           "a_ref": a, "b_ref": b, "expect": {"Blend_surface/NoSuchCapture": 0},
           "must_not_move": [], "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
: > "$SELFTEST_GH_LOG"
bash "$HERE/arms.sh" >/dev/null 2>&1
sha2=$(sha256sum "$EXP2" | cut -d' ' -f1)
check "the bad key is recorded as skipped with request.sh's reason" grep -q "request.sh refused" "$HAKUX_WORK/arms/skipped/$sha2"
check "the refusal was posted as a comment" grep -qE '^(pr|issue) comment' "$SELFTEST_GH_LOG"
check "the refusal comment names REFUSED" grep -q REFUSED "$HAKUX_WORK/arms/log/$sha2.refused.md"
check "the skipped marker carries the arms.sh version" grep -q '^arms=' "$HAKUX_WORK/arms/skipped/$sha2"

# The retry must reach the markers written BEFORE the stamp existed -- which is
# every marker that was already on the host when the retry shipped, including
# the single refusal (#89's, 02:56Z) the retry was written for. The first
# version tested `grep -q '^arms='` first, so an unstamped marker took the
# `else` and was skipped forever: the guard exempted exactly the backlog it was
# meant to clear. Reproduce the host's marker by stripping the stamp.
sed -i 's/^arms=[^ ]* //' "$HAKUX_WORK/arms/skipped/$sha2"
: > "$SELFTEST_GH_LOG"
out=$(bash "$HERE/arms.sh" 2>&1)
check "an unstamped refusal (written before the stamp existed) is reconsidered" grep -q "reconsidering $sha2" <<< "$out"
check "the rewritten marker carries the stamp, so it is not retried every tick" grep -q '^arms=' "$HAKUX_WORK/arms/skipped/$sha2"
check "a stamped refusal at this version is left alone" bash -c 'out2=$(bash "$HERE/arms.sh" 2>&1); ! grep -q "reconsidering" <<< "$out2"'

# ...and must NOT reach a structural skip. No edit to arms.sh turns "this
# prediction names no suite with goldens" into a run, so retrying it every time
# the script changes is a comment on a PR that says nothing new. The
# discriminator is the refusal text; both marker kinds are unstamped here, so
# this is the case that tells them apart.
EXP3="$DISPATCH_DIR/expect/selftest-nosuite.json"
python3 - "$EXP3" "$A" "$B" <<'PY2'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.selftest", "issue": "1", "prediction": "a suite with no goldens on this host",
           "a_ref": a, "b_ref": b, "expect": {"No_such_suite/Test": 0},
           "must_not_move": [], "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY2
sha3=$(sha256sum "$EXP3" | cut -d' ' -f1)
bash "$HERE/arms.sh" >/dev/null 2>&1
check "a prediction naming no suite with goldens is skipped" grep -q "no suite with goldens" "$HAKUX_WORK/arms/skipped/$sha3"
check "that structural skip carries no stamp" bash -c '! grep -q "^arms=" "$HAKUX_WORK/arms/skipped/$sha3"'
check "and it is not reconsidered on the next tick" bash -c 'out3=$(bash "$HERE/arms.sh" 2>&1); ! grep -q "reconsidering $sha3" <<< "$out3"'
