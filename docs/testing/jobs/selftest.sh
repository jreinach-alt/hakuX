#!/usr/bin/env bash
#
# The jobs' self-test: run the real job scripts against a fake host.
#
#   docs/testing/jobs/selftest.sh          # exits non-zero on any failure
#
# WHY. The jobs run only on the owner's host -- systemd, gh, adb, the
# dispatch directory, the goldens tree -- and the session that writes them
# cannot execute any of it. On 2026-09-19 that put the owner in a loop:
# merge, run, paste the error, wait for the fix, merge again. Three of the
# four defects that day (a watermark seeded at install time, an arithmetic
# error on a "?" field, an empty --runs handed to request.sh) fall out of
# one run of this file. So: nothing under jobs/ is pushed until this passes,
# and the check is in CI (.github/workflows/jobs-selftest.yml) as well.
#
# WHAT IS REAL AND WHAT IS FAKED. Real: git, python3, request.sh's whole
# queue path (its gates, its JSON writer), arms.sh, fold.sh, cloud.sh,
# status.sh. Faked, as shims on PATH under $T/bin: gh (canned answers, every
# call logged), systemctl, systemd-run, adb. The goldens tree is generated
# from the prediction under test, so request.sh's every-key-must-bind gate
# runs for real.
set -u
export HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; TESTING="$(dirname "$HERE")"; REPO="$(cd "$TESTING/../.." && pwd)"
T="${SELFTEST_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/hakux-selftest.XXXXXX")}"
export HAKUX_WORK="$T/work" HAKUX_REPO_DIR="$REPO" DISPATCH_DIR="$T/work/dispatch" GOLDENS="$T/goldens" GH_REPO="example/hakux"
export HOME="${HOME:-$T}"
mkdir -p "$T/bin" "$HAKUX_WORK"/{arms,logs/arms,logs/lane,logs/board,logs/fold,logs/cloud,status,briefs,attempts} "$DISPATCH_DIR"/{queue,running,results,expect} "$GOLDENS"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }

# ------------------------------------------------------------------ shims
cat > "$T/bin/gh" <<'EOF'
#!/usr/bin/env bash
# gh shim: log every call, answer the shapes the jobs ask for.
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list")
        if [[ "$args" == *"--head lane/selftest"* ]]; then
            [[ "$args" == *".[0].number"* ]] && { echo 102; exit 0; }
            echo "#102 draft"; exit 0
        fi
        [[ "$args" == *"--jq"* ]] && exit 0
        echo "[]"; exit 0 ;;
    "pr view") echo GREEN; exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo 107; exit 0 ;;
    "issue create") echo "https://github.com/example/hakux/issues/107"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }
        # the labels currently on an issue/PR, for label_rm's "is it there" probe
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${SELFTEST_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$T/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) echo active ;;
    *show*ActiveEnterTimestamp*) date ;;
    *) exit 0 ;;
esac
EOF
cat > "$T/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${SELFTEST_GH_LOG:?}"; exit 0
EOF
cat > "$T/bin/adb" <<'EOF'
#!/usr/bin/env bash
printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n'
EOF
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" SELFTEST_GH_LOG="$T/gh.log"; : > "$SELFTEST_GH_LOG"

# ------------------------------------------------------- the prediction
# A registration naming two real, live refs of this repository: the trunk's
# tip and its parent. It has NO runs_per_arm and NO disc, which is the shape
# that broke the first real tick.
git -C "$REPO" fetch -q origin master 2>/dev/null || true
B=$(git -C "$REPO" rev-parse --short origin/master 2>/dev/null || git -C "$REPO" rev-parse --short HEAD)
A=$(git -C "$REPO" rev-parse --short "$B~1")
EXP="$DISPATCH_DIR/expect/selftest-live.json"
python3 - "$EXP" "$A" "$B" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.selftest", "issue": "1", "prediction": "selftest: the fix arm moves TestA to 0",
           "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": ["Color_mask_blend/*"],
           "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
mkdir -p "$GOLDENS/Blend_surface" "$GOLDENS/Color_mask_blend"
: > "$GOLDENS/Blend_surface/TestA.png"; : > "$GOLDENS/Color_mask_blend/Sample.png"
date -u -d '1 minute ago' '+%FT%TZ' > "$HAKUX_WORK/arms/since"   # fences every committed prediction; only ours is live
# Make our registration look like it came from a lane branch, so the verdict/refusal path targets a PR.
mkdir -p "$HAKUX_WORK/arms"

# --------------------------------------------------------------- the checks
# Every check lives in its own file under selftest.d/, sourced here in sorted
# order with everything above already built: $T, $HERE, $REPO, the shims on
# PATH, ok/bad/check, the live prediction and its goldens.
#
# WHY IT IS NOT ONE FILE. This is the gate every change under jobs/ must pass,
# so a lane that fixes something here also adds the check that proves it: on
# 2026-09-19 nine harness lanes ran and all nine appended to this file. The
# fold job folds one PR per tick and each fold moves master, so the conflict
# rate on this one path was not high, it was ~100% -- two of the first three
# folds attempted were handed back on selftest.sh alone, each costing a full
# lane.sh resume to re-land work that was already finished and green. A
# fragment is separately ownable; two lanes adding checks now touch two paths.
#
# ADDING A CHECK: write, or edit, selftest.d/NN-<concern>.sh.
#   - NN is exactly two digits. A three-digit prefix would sort before every
#     two-digit one, so the loop below refuses a name that is not NN-*.sh
#     rather than silently never sourcing it.
#   - The number fixes the order, and order matters: fragments 10..50 drive
#     arms.sh over one shared dispatcher queue in sequence, and 60 reads what
#     they left. Each fragment's header says what it depends on.
#   - Fragments are sourced, not executed: no shebang, no exit. `pass`, `fail`
#     and the fixtures are shared state, so a failing check in a fragment
#     fails the whole run, which is the point.
frags=()
while IFS= read -r f; do                         # LC_ALL=C: the runner's
    [ -e "$f" ] || continue                      # collation is not this box's
    case "${f##*/}" in
        [0-9][0-9]-*.sh) frags+=("$f") ;;
        *.md|*~)         ;;                      # a README, an editor backup
        *) echo "selftest: $f is not selftest.d/NN-<concern>.sh and would never be sourced" >&2
           exit 2 ;;
    esac
done < <(printf '%s\n' "$HERE/selftest.d/"* | LC_ALL=C sort)
[ "${#frags[@]}" -gt 0 ] || {
    echo "selftest: no fragments under $HERE/selftest.d -- nothing would be checked" >&2
    exit 2
}
for f in "${frags[@]}"; do
    . "$f"
done

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

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
