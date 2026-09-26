# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# board.sh's capacity list is the board's dispatch order, and it is sorted by
# expected improvement (owner, 2026-09-25: "these broader more impactful
# issues get dispatched ahead of the smaller edge cases"). Before this, the
# list came out in gh's order -- newest first -- and the role file's "severity
# bucket, then oldest" ranked over a tracker that recorded no size, so a 5k-px
# edge case and a 1.5 M-px family looked the same.
#
# THE TRACKER IS A FIXTURE, SO board.sh RUNS FROM A COPY. board_filter reads
# nv2a_issues.toml through board_files.load, which reads beside ITSELF (git
# show <ref>:, then the working tree). Pointing it at a fixture means a
# board_files.py whose directory holds the fixture, and a board.sh whose
# `$SELF/..` is that directory: the real layout, rebuilt under $T, with
# HAKUX_BOARD_REF empty so the working-tree copy is the one read. The real
# tracker and the real board.sh are never touched.
#
# Brings its own gh shim; depends on no other fragment. Truncates
# $HAKUX_WORK/limits.env on the way out.

echo "== board.sh: the capacity list is sorted by expected improvement"
BP="$T/boardprio"; mkdir -p "$BP/bin" "$BP/testing/jobs"
cp "$HERE/board.sh" "$HERE/localtime.sh" "$HERE/window.sh" "$BP/testing/jobs/"
cp "$TESTING/board_files.py" "$BP/testing/"
cat > "$BP/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
    "auth status") exit 0 ;;
    "issue list")  cat "$BP_ISSUES"; exit 0 ;;
    "pr list")     echo '[]'; exit 0 ;;
esac
exit 0
EOF
cat > "$BP/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$BP/bin/"*

# The tracker. Every tier, and two ties:
#   #301  game-visible, no px            -> first, despite scoring 0
#   #302  800,000 structural             -> 800,000
#   #303  1,200,000 one-step only        -> 300,000, BELOW #302; weighted 1:1
#                                           it would be 1,200,000 and above it
#   #270, #310, #320  50,000 each        -> a tie, oldest first; #310 is
#                                           the FLOAT 50000.0, which must rank
#                                           by its value, not as a measured 0
#   #305  5,000 structural               -> 5,000
#   #280, #290, #304  rows, no estimate  -> a tie, oldest first; #290
#                                           holds a STRING and #304 a nan: both
#                                           unreadable, ranked with the
#                                           unestimated rows, never "measured"
#   #296, #306, #312  measured zero      -> BELOW the unestimated rows (host
#                                           decision 2026-09-25: an unknown
#                                           may be large, a measured zero is
#                                           not), a tie, oldest first
#   #299  a huge estimate, but lane-held -> never listed: startability is not
#                                           the sort's to change
#   #300  no tracker row at all          -> last, and says so
cat > "$BP/testing/nv2a_issues.toml" <<'EOF'
[issue.301]
title = "game"
game_visible = true
[issue.302]
title = "large structural"
impact_px = 800000
impact_onestep_px = 0
game_visible = false
[issue.303]
title = "one-step only"
impact_px = 0
impact_onestep_px = 1200000
game_visible = false
[issue.270]
title = "tie a"
impact_px = 50000
[issue.310]
title = "tie b"
impact_px = 50000.0
[issue.320]
title = "tie c"
impact_px = 50000
[issue.305]
title = "small structural"
impact_px = 5000
impact_onestep_px = 0
[issue.280]
title = "no estimate a"
[issue.290]
title = "no estimate b"
impact_px = "big"
[issue.304]
title = "no estimate c"
impact_onestep_px = nan
[issue.296]
title = "zero a"
impact_px = 0
impact_onestep_px = 0
[issue.306]
title = "zero b"
impact_px = 0
impact_onestep_px = 0
game_visible = false
[issue.312]
title = "zero c"
impact_px = 0
[issue.299]
title = "held"
impact_px = 9000000
EOF
# gh's order: newest first, as `gh issue list` returns it. Each tie's correct
# winner is the MIDDLE of its three in this order (#270 between #310 and
# #320; #280 between #304 and #290; #296 between #312 and #306), so neither a first-wins nor a last-wins
# tie-break can pass by accident.
cat > "$BP/issues.json" <<'EOF'
[{"number":310,"title":"tie b","labels":[]},
 {"number":270,"title":"tie a","labels":[]},
 {"number":320,"title":"tie c","labels":[]},
 {"number":305,"title":"small structural","labels":[{"name":"harness"}]},
 {"number":304,"title":"no estimate c","labels":[]},
 {"number":280,"title":"no estimate a","labels":[]},
 {"number":290,"title":"no estimate b","labels":[]},
 {"number":312,"title":"zero c","labels":[]},
 {"number":296,"title":"zero a","labels":[]},
 {"number":306,"title":"zero b","labels":[]},
 {"number":303,"title":"one-step only","labels":[]},
 {"number":302,"title":"large structural","labels":[]},
 {"number":301,"title":"game","labels":[]},
 {"number":300,"title":"no row","labels":[]},
 {"number":299,"title":"held","labels":[{"name":"lane:x"}]}]
EOF
bprio() {
    : > "$HAKUX_WORK/limits.env"
    BP_ISSUES="$BP/issues.json" HAKUX_BOARD_REF="" HAKUX_REPO_DIR="$BP/no-such-repo" \
        PATH="$BP/bin:$PATH" bash "$BP/testing/jobs/board.sh" gate 2>&1
}
out=$(bprio)
order=$(grep -o '^#[0-9]*' <<< "$out" | tr '\n' ' ')
want="#301 #302 #303 #270 #310 #320 #305 #280 #290 #304 #296 #306 #312 #300 "
check "the capacity list is in dispatch order: game, then px descending, then no estimate, then measured zero, then no row (got: $order)" \
    test "$order" = "$want"
has() { grep -qxF -- "$1" <<< "$out"; }
check "a game-visible row says [game]" \
    has '#301 [game] game'
check "a structural row shows its score, with thousands separators" \
    has '#302 [impact 800,000 px] large structural'
check "a one-step row shows the quarter weight it was scored with" \
    has '#303 [impact 300,000 px = 0 structural + 1,200,000 one-step / 4] one-step only'
check "the labels still follow the key" \
    has '#305 [impact 5,000 px] small structural  [harness]'
check "a row with no impact fields says so" \
    has '#280 [no impact estimate] no estimate a'
check "a float estimate ranks by its value (the tie above) and shows it" \
    has '#310 [impact 50,000 px] tie b'
check "a string estimate is unreadable, not a measured zero" \
    has "#290 [impact unreadable: impact_px='big'] no estimate b"
check "a nan estimate is unreadable, not a measured zero" \
    has "#304 [impact unreadable: impact_onestep_px=nan] no estimate c"
check "a measured zero says it was measured" \
    has '#296 [impact 0 px, measured] zero a'
check "an issue with no tracker row says so" \
    has '#300 [no tracker row] no row'
check "the sort does not change what is startable: a lane-held issue stays out" \
    bash -c '! grep -q "^#299" <<< "$1"' _ "$out"
: > "$HAKUX_WORK/limits.env"

# THE RELEASE GOES FIRST (#432). An issue labelled `0.5` sorts ahead of every
# issue that is not, and the five tiers above order each group unchanged:
#   #401  0.5, measured zero       -> ahead of #301, the game-visible non-0.5
#                                     row that heads the list above
#   #403, #402, #401  all 0.5      -> game, then px, then measured zero: the
#                                     old key between them; gh's order puts
#                                     the right first one (#403) in the middle
#   #404  labels a STRING, game    -> unreadable: printed, never 0.5, ranked
#                                     with #301 by the old key (oldest first)
# Every leg fails on the pre-#432 board.sh: it has no release group, and it
# raises on #404's label string and prints nothing at all.
echo "== board.sh: issues labelled 0.5 dispatch first"
cat >> "$BP/testing/nv2a_issues.toml" <<'EOF'
[issue.401]
title = "zero release"
impact_px = 0
impact_onestep_px = 0
[issue.402]
title = "small release"
impact_px = 100
[issue.403]
title = "game release"
game_visible = true
[issue.404]
title = "bad labels"
game_visible = true
EOF
python3 - "$BP/issues.json" "$BP/issues-rel.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
rel = [{"name": "0.5"}]
rows[0:0] = [
    {"number": 401, "title": "zero release", "labels": rel},
    {"number": 403, "title": "game release", "labels": rel + [{"name": "harness"}]},
    {"number": 404, "title": "bad labels", "labels": "0.5"},
    {"number": 402, "title": "small release", "labels": rel},
]
json.dump(rows, open(sys.argv[2], "w"))
PY
bprio_rel() {
    : > "$HAKUX_WORK/limits.env"
    BP_ISSUES="$BP/issues-rel.json" HAKUX_BOARD_REF="" HAKUX_REPO_DIR="$BP/no-such-repo" \
        PATH="$BP/bin:$PATH" bash "$BP/testing/jobs/board.sh" gate 2>&1
}
out=$(bprio_rel)
order=$(grep -o '^#[0-9]*' <<< "$out" | tr '\n' ' ')
check "a 0.5 measured zero sorts before a game-visible non-0.5 issue (got: $order)" \
    bash -c '[[ " $1" == *" #401 "*" #301 "* ]]' _ "$order"
check "0.5 issues keep the old key between them: game, px, measured zero (got: $order)" \
    bash -c '[[ " $1" == " #403 #402 #401 "* ]]' _ "$order"
want="#403 #402 #401 #301 #404 #302 #303 #270 #310 #320 #305 #280 #290 #304 #296 #306 #312 #300 "
check "an unreadable label list is printed and leaves the old order below the release (got: $order)" \
    test "$order" = "$want"
check "a 0.5 line's key is tagged [0.5]" \
    has '#401 [0.5] [impact 0 px, measured] zero release  [0.5]'
check "a 0.5 line keeps its old key and its labels after the tag" \
    has '#403 [0.5] [game] game release  [0.5,harness]'
check "an unreadable label list says so and is not read as 0.5" \
    has '#404 [labels unreadable] [game] bad labels'
check "a non-0.5 line is untagged" \
    has '#301 [game] game'
: > "$HAKUX_WORK/limits.env"

# THE FOCUS EXCLUDES (#432 addendum). With BOARD_FOCUS_LABEL=0.5 in
# limits.env the list offers only 0.5 issues: #301, the game-visible non-0.5
# row that heads every list above, is absent, #401 (a 0.5 measured zero) is
# present, and one line counts the 15 left out (#404's unreadable labels
# among them) -- said to the log, never a capacity line. Unset, the list is
# the one above, line for line. Fails on the pre-#432 board.sh, which reads
# no focus and offers #301.
echo "== board.sh: BOARD_FOCUS_LABEL offers only the focus"
bprio_focus() {
    printf '%s\n' "$1" > "$HAKUX_WORK/limits.env"
    BP_ISSUES="$BP/issues-rel.json" HAKUX_BOARD_REF="" HAKUX_REPO_DIR="$BP/no-such-repo" \
        PATH="$BP/bin:$PATH" bash "$BP/testing/jobs/board.sh" gate 2>&1
}
unset_out=$(bprio_focus "")
out=$(bprio_focus "BOARD_FOCUS_LABEL=0.5")
forder=$(grep -o '^#[0-9]*' <<< "$out" | tr '\n' ' ')
check "with the focus set, a non-focus game-visible issue is not offered (got: $forder)" \
    bash -c '[[ " $1" != *" #301 "* ]]' _ "$forder"
check "with the focus set, the focus issues are offered in the old order (got: $forder)" \
    test "$forder" = "#403 #402 #401 "
check "with the focus set, one line counts what it left out" \
    grep -qF "15 startable issue(s) outside the 0.5 focus are not offered" <<< "$out"
check "the focus count is not printed as a capacity line" \
    bash -c '! grep -q "^FOCUS: " <<< "$1"' _ "$out"
check "with the focus unset, the list is unchanged" \
    test "$(grep '^#' <<< "$unset_out")" = "$(grep '^#' <<< "$(bprio_rel)")"
check "with the focus unset, no focus line" \
    bash -c '! grep -q "outside the .* focus" <<< "$1"' _ "$unset_out"
: > "$HAKUX_WORK/limits.env"
