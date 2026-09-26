# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh: a STRUCTURAL skip reaches the lane too, exactly once.
# Written as an append to selftest.sh (#123, lane/armsskip) and carried here
# unchanged when that split (#136) landed under it.
#
# Registers two more predictions of its own ($EXP4, $EXP5) from the $B ref
# selftest.sh resolved, and reads $sha2 -- the request.sh refusal that
# 40-arms-refusal.sh leaves standing -- to assert it gets no SECOND comment.
# So it must run after 40, and after 50, which drives the whole queue itself.
# 92 because it needs those and nothing after it needs this.

echo "== arms.sh: a STRUCTURAL skip reaches the lane too, exactly once"
# Until 2026-09-19 only a request.sh refusal was posted; the six structural
# refusals wrote a marker under $WORK/arms/skipped and said nothing. PR #115's
# registration had English prose where the a_ref belonged -- "4129a349e6 with
# xemu.toml [display] renderer = OpenGL" -- and the job had been refusing it
# silently since 04:29Z while the lane believed an arm was running. A cloud
# lane has no host disk, so for it the marker did not exist at all.
#
# This is that registration's exact shape.
EXP4="$DISPATCH_DIR/expect/selftest-prose-aref.json"
python3 - "$EXP4" "$B" <<'PY4'
import json, sys, datetime
p, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.selftest", "issue": "1", "prediction": "prose where the a_ref belongs",
           "a_ref": "4129a349e6 with xemu.toml [display] renderer = OpenGL", "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": [], "must_not_regress": [],
           "expect_counts": {}}, open(p, "w"), indent=2)
PY4
sha4=$(sha256sum "$EXP4" | cut -d' ' -f1)
: > "$SELFTEST_GH_LOG"
bash "$HERE/arms.sh" >/dev/null 2>&1
check "the prose a_ref is recorded as a structural skip" grep -q "a_ref .* does not resolve" "$HAKUX_WORK/arms/skipped/$sha4"
check "the structural skip was posted as a comment" grep -qE '^(pr|issue) comment' "$SELFTEST_GH_LOG"
check "the comment says SKIPPED, not REFUSED" grep -q '^\[job.arms\] SKIPPED' "$HAKUX_WORK/arms/log/$sha4.skipped.md"
check "the comment carries the same reason the marker holds" grep -q "does not resolve" "$HAKUX_WORK/arms/log/$sha4.skipped.md"
check "the marker records that the lane was told" grep -q '^told=' "$HAKUX_WORK/arms/skipped/$sha4"
# Once per registration. The marker survives the tick, so the next 47 ticks of
# the day must add nothing; a corrected file is a new sha and a new marker,
# which is what makes this "once", not "once ever".
: > "$SELFTEST_GH_LOG"
bash "$HERE/arms.sh" >/dev/null 2>&1
check "a second tick does not tell it again" bash -c '! grep -qE "^(pr|issue) comment" "$SELFTEST_GH_LOG"'

# The backlog. Both markers on the host when this shipped were written by a
# version that told nobody -- including #115's, the one it exists for. Had the
# marker's existence been the record of "said", the fix would have exempted
# exactly the two cases it was written for, which is the mistake the `arms=`
# retry above made once already. So told= is a separate line and an unstamped
# structural marker is announced on the next tick.
sed -i '/^told=/d' "$HAKUX_WORK/arms/skipped/$sha4"
: > "$SELFTEST_GH_LOG"
bash "$HERE/arms.sh" >/dev/null 2>&1
check "a structural marker written before told= existed is announced" grep -qE '^(pr|issue) comment' "$SELFTEST_GH_LOG"
check "and stamped, so it is announced only that once" grep -q '^told=' "$HAKUX_WORK/arms/skipped/$sha4"

# A request.sh refusal must NOT get a second comment: refused() posts its own,
# richer one with the stderr in it. sha2's marker is the refusal kind.
check "a request.sh refusal is not also told as a structural skip" [ ! -f "$HAKUX_WORK/arms/log/$sha2.skipped.md" ]

# AND THE 38 BEHIND THE WATERMARK STAY SILENT. Predictions older than
# $WORK/arms/since are history, not refusals: arms.sh counts them and continues
# before any skip() and writes no marker. Telling them would put a comment on
# 38 old PRs and issues in a single tick. This one would skip structurally --
# its a_ref is prose too -- and must still produce nothing at all.
EXP5="$DISPATCH_DIR/expect/selftest-old-and-broken.json"
python3 - "$EXP5" "$B" <<'PY5'
import json, sys
p, b = sys.argv[1:]
json.dump({"registered_utc": "2026-01-01T00:00:00Z", "who": "lane.selftest", "issue": "1",
           "prediction": "history: registered long before the watermark",
           "a_ref": "not a sha at all", "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": [], "must_not_regress": [],
           "expect_counts": {}}, open(p, "w"), indent=2)
PY5
sha5=$(sha256sum "$EXP5" | cut -d' ' -f1)
: > "$SELFTEST_GH_LOG"
bash "$HERE/arms.sh" >/dev/null 2>&1
check "a broken prediction behind the watermark is counted as history, not skipped" \
    [ ! -f "$HAKUX_WORK/arms/skipped/$sha5" ]
check "and nothing is posted for it" bash -c '! grep -qE "^(pr|issue) comment" "$SELFTEST_GH_LOG"'

