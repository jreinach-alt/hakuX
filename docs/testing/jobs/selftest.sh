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

echo "== arms.sh list"
out=$(bash "$HERE/arms.sh" list 2>&1)
check "list names the live prediction as WOULD QUEUE" grep -q "WOULD QUEUE .*selftest-live.json.*suites=\[Blend surface,Color mask blend\]" <<< "$out"
check "list fences the committed history behind the watermark" grep -q "older than the watermark" <<< "$out"

echo "== arms.sh run: queue"
bash "$HERE/arms.sh" >/dev/null 2>&1
pairs=$(ls "$HAKUX_WORK"/arms/pairs/*.json 2>/dev/null | wc -l)
reqs=$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)
check "one pair recorded" [ "$pairs" -eq 1 ]
check "two requests in the dispatcher queue" [ "$reqs" -eq 2 ]
if [ "$reqs" -eq 2 ]; then
    for r in "$DISPATCH_DIR"/queue/*.req; do
        python3 - "$r" "$EXP" <<'PY' && ok "request $(basename "$r") parses, runs is an int, expect_sha bound" || bad "request $(basename "$r") malformed"
import json, sys, hashlib
d = json.load(open(sys.argv[1]))
assert isinstance(d["runs"], int) and d["runs"] >= 1, d["runs"]
assert d["expect_sha"] == hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest(), "expect_sha"
assert d["suites"] == ["Blend surface", "Color mask blend"], d["suites"]
PY
    done
fi
check "nothing was skipped for the live prediction" bash -c '! ls "$HAKUX_WORK"/arms/skipped/* 2>/dev/null | xargs -r grep -l selftest-live'
check "a second run does not queue it again" bash -c 'bash "$HERE/arms.sh" >/dev/null 2>&1; [ "$(ls "$DISPATCH_DIR"/queue/*.req | wc -l)" -eq 2 ]'

echo "== arms.sh run: judge the ERROR path"
pair=$(ls "$HAKUX_WORK"/arms/pairs/*.json | head -1)
idb=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['id_b'])" "$pair")
sha=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['sha'])" "$pair")
mkdir -p "$DISPATCH_DIR/results/$idb"; echo "simulated device failure" > "$DISPATCH_DIR/results/$idb/ERROR"
bash "$HERE/arms.sh" >/dev/null 2>&1
check "an ERROR arm is judged as ARM ERROR" grep -q ERROR "$HAKUX_WORK/arms/judged/$sha"
check "the ARM ERROR was posted somewhere" grep -qE '^(pr|issue) comment' "$SELFTEST_GH_LOG"

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

echo "== arms.sh: an errored arm can be queued again, which is what the ARM ERROR comment promises"
# The ARM ERROR comment tells the lane to delete the pair and judged markers to
# have the job queue the arm again. It could not work: the errored result's
# request.json still carried the expect_sha, so already_ran matched it forever.
# Measured 2026-09-19, when #89's arm failed to build on both sides because
# meson was not on the daemon's PATH -- a host fault the lane could do nothing
# about and could not retry past either.
clear_markers() { rm -f "$HAKUX_WORK"/arms/judged/* "$HAKUX_WORK"/arms/pairs/*.json; }
finish_queue() {   # <marker-file-or-"">: turn the queue into results, erroring them or not
    local q id d
    for q in "$DISPATCH_DIR"/queue/*.req; do
        [ -f "$q" ] || continue
        id=$(basename "$q" .req); d="$DISPATCH_DIR/results/$id"
        mkdir -p "$d"; mv "$q" "$d/request.json"
        [ -n "$1" ] && echo simulated > "$d/$1"
    done
}
clear_markers; rm -f "$DISPATCH_DIR"/queue/*.req
bash "$HERE/arms.sh" >/dev/null 2>&1          # queue the pair afresh
finish_queue ERROR                            # both arms ran and ERRORed
clear_markers
bash "$HERE/arms.sh" >/dev/null 2>&1
check "an ERROR result is not a run, so the pair can be queued again" \
    [ "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)" -ge 2 ]
finish_queue ""                               # this time both arms completed
clear_markers
bash "$HERE/arms.sh" >/dev/null 2>&1
check "a completed result IS a run, so the pair is not queued again" \
    [ "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)" -eq 0 ]

echo "== status.sh"
printf '2026-09-19T01:00:00Z\tlane-x\t?\t?\t?\tERR\tx.json\t\n2026-09-19T01:10:00Z\tlane-y\tclaude-opus-5\t41\t1300\t0\tERR\ty.json\tsaid a thing\n' > "$HAKUX_WORK/logs/lane/index.tsv"
sout=$(bash "$HERE/status.sh" --print 2>&1); src=$?
check "status.sh exits 0" [ "$src" -eq 0 ]
for h in "### Lanes running" "### Lane sessions finished" "### Cloud-class sessions" "### Board job" "### Handhelds and arms" "### Fold job" "### Open lane PRs" "### Host"; do
    check "status has '$h'" grep -q "^$h" <<< "$sout"
done
check "status renders the eight-column row without dying" grep -q '| y | opus-5 | 41 | 21 | ERR' <<< "$sout"
check "status shows the arms refusal in full" grep -q 'last refusals' <<< "$sout"

echo "== fold.sh list, cloud.sh list"
check "fold.sh list runs with nothing labelled" bash -c 'bash "$HERE/fold.sh" list 2>&1 | grep -q "nothing labelled fold-ready"'
check "cloud.sh list runs with nothing to claim" bash -c 'bash "$HERE/cloud.sh" list 2>&1 | grep -q "nothing to claim"'

echo "== cloud.sh: the audit path cannot hold a branch a lane worktree already holds"
# Every local lane keeps its branch checked out under $WORK/wt, and git refuses
# one branch in two worktrees, so `worktree add -B "$branch"` failed for every
# PR a local lane had opened -- exit 5, before the first say(): no tick log, no
# comment, no label. A shim cannot reproduce git's refusal against the real
# lane worktrees, so this pins the mechanism.
check "the audit worktree is detached, not -B <branch>" \
    grep -q 'worktree add --quiet --detach "$wt" "origin/$branch"' "$HERE/cloud.sh"
check "the audit brief tells the session to push HEAD:<branch>" \
    grep -q 'git push origin HEAD:\$branch' "$HERE/cloud.sh"
check "no claim path exits without saying why" bash -c '! grep -nE "\|\| exit [0-9]" "$HERE/cloud.sh"'

echo "== nv2a_index.py: the fold job regenerates the index, so the tree it reads matters"
# The fold job runs `nv2a_index.py check` after a merge and, if it fails,
# `build` -- from whatever nxdk_pgraph_tests checkout the host holds. On
# 2026-09-19 that checkout was five commits behind the one the committed index
# came from, so the regeneration would have DELETED a suite (Surface as vertex
# array) and pushed the deletion to master. The gate checks the DIRECTION of
# the difference. Two throwaway repos are enough to test that; no suite parsing
# is involved.
GT="$T/gate"; mkdir -p "$GT/tests"
git -C "$GT/tests" init -q 2>/dev/null
git -C "$GT/tests" -c user.email=s@t -c user.name=s commit -q --allow-empty -m one
c1=$(git -C "$GT/tests" rev-parse HEAD)
git -C "$GT/tests" -c user.email=s@t -c user.name=s commit -q --allow-empty -m two
c2=$(git -C "$GT/tests" rev-parse HEAD)
printf '{"provenance": {"tests_commit": "%s"}}\n' "$c2" > "$GT/index.json"
gate() {   # <checkout-at> <allow_older> -> the gate's return code
    git -C "$GT/tests" checkout -q "$1"
    python3 - "$REPO/docs/testing/nv2a_index.py" "$GT/index.json" "$GT/tests" "$2" 2>"$GT/gate.err" <<'PYGATE'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("nv2a_index", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.INDEX_PATH = sys.argv[2]
print(m.tests_provenance_gate(sys.argv[3], sys.argv[4] == "1"))
PYGATE
}
check "a tests tree OLDER than the index refuses the rebuild" [ "$(gate "$c1" 0)" = 3 ]
check "the same tree with --allow-older-tests proceeds" [ "$(gate "$c1" 1)" = 0 ]
check "a tests tree AT the index's commit builds" [ "$(gate "$c2" 0)" = 0 ]
git -C "$GT/tests" -c user.email=s@t -c user.name=s commit -q --allow-empty -m three
check "a tests tree NEWER than the index builds" [ "$(gate HEAD 0)" = 0 ]
printf '{"provenance": {"tests_commit": "%s"}}\n' "0123456789012345678901234567890123456789" > "$GT/index.json"
check "a provenance commit this checkout has never seen refuses" [ "$(gate HEAD 0)" = 3 ]

echo "== labels: the state machine's only actuator"
# `gh pr edit --add-label` exits 1 on gh 2.45 (Projects-classic project cards)
# and applies nothing; every job called it with stderr discarded, so for a day
# no PR label the harness set ever took -- fold-ready, folded, needs-rebase,
# verified, regressed, claimed:cloud. The shim cannot reproduce a real gh's
# failure, so this pins the MECHANISM: no job may reach for that call, and the
# helper must go through the REST endpoint that works for issues and PRs alike.
check "no job script labels through 'gh pr edit'" bash -c '! grep -rn "^[^#]*gh pr edit[^|]*--\(add\|remove\)-label" "$HERE"/*.sh'
: > "$SELFTEST_GH_LOG"
( . "$HERE/gh-label.sh"; label_add 102 verified folded ) >/dev/null 2>&1
check "label_add posts to the REST labels endpoint" grep -q 'api -X POST repos/example/hakux/issues/102/labels' "$SELFTEST_GH_LOG"
check "label_add sends every label in one call" grep -q 'labels\[\]=verified.*labels\[\]=folded' "$SELFTEST_GH_LOG"
: > "$SELFTEST_GH_LOG"
( export SELFTEST_LABELS="fold-ready"; . "$HERE/gh-label.sh"; label_rm 102 fold-ready ) >/dev/null 2>&1
check "label_rm deletes a label that is present" grep -q 'api -X DELETE repos/example/hakux/issues/102/labels/fold-ready' "$SELFTEST_GH_LOG"
: > "$SELFTEST_GH_LOG"
( export SELFTEST_LABELS="fold-ready"; . "$HERE/gh-label.sh"; label_rm 102 regressed ) >/dev/null 2>&1
check "label_rm does not DELETE a label that is absent (a 404 is not a failure)" bash -c '! grep -q "DELETE" "$SELFTEST_GH_LOG"'
check "label_rm reports success when there was nothing to remove" bash -c '( export SELFTEST_LABELS="fold-ready"; . "$HERE/gh-label.sh"; label_rm 102 regressed ) >/dev/null 2>&1'

echo "== handback.sh: the actor for a PR a job handed back"
# `needs-rebase` was set by fold.sh, shown by status.sh and acted on by nothing,
# so a complete, audited, green PR was parked the moment master moved under it.
# These drive the REAL handback.sh and the REAL lane.sh against shims of their
# own: the shared gh shim answers every `pr list` with "[]" and every
# `systemctl is-active` with "active", which are exactly the two answers that
# make this job do nothing.
HB="$T/handback"; mkdir -p "$HB/bin" "$HAKUX_WORK/wt" "$HAKUX_WORK/briefs"
cat > "$HB/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HB_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        # The rows this tick should see, one file per label, TSV as the --jq emits.
        [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]] && { f="$HB/prs.${BASH_REMATCH[1]}.tsv"; [ -f "$f" ] && cat "$f"; }
        exit 0 ;;
    "pr comment")
        # keep the body, not just the fact of it: these checks read what it said
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HB/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HB/comments.log"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${HB_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HB/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
# $HB/active holds one unit name per line; everything else is inactive.
# ${!#} is the last argument -- the unit. NOT ${*##* }: on $* a substring
# removal applies to each positional parameter separately and the join puts
# the whole command line back, which grep then reads as an option.
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "$u" "$HB/active" 2>/dev/null ;;
    *list-units*) cat "$HB/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HB/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HB_LOG:?}"; exit 0
EOF
chmod +x "$HB/bin/"*
export HB HB_LOG="$HB/gh.log"; : > "$HB_LOG"; : > "$HB/comments.log"; : > "$HB/active"
hb() { ( export PATH="$HB/bin:$PATH"; bash "$HERE/handback.sh" "$@" 2>&1 ); }
hb_said()   { grep -qF -- "$1" "$HB/comments.log"; }
hb_ran()    { grep -q "systemd-run.*hakux-lane-$1" "$HB_LOG"; }
hb_runs()   { [ "$(grep -c "systemd-run.*hakux-lane-$1" "$HB_LOG")" -eq "$2" ]; }
hb_reset()  { : > "$HB_LOG"; : > "$HB/comments.log"; }
hb_row()    { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "${4:-needs-rebase}" > "$HB/prs.needs-rebase.tsv"; }

check "handback.sh exists at all" [ -f "$HERE/handback.sh" ]
out=$(hb list)
check "list says so when nothing is handed back" grep -q "nothing handed back" <<< "$out"
check "and names the label it looked for" grep -q "needs-rebase" <<< "$out"

# A real local lane: a worktree directory and a brief, which is all lane.sh
# resume requires. Its unit is not running.
mkdir -p "$HAKUX_WORK/wt/selftesthb"; echo "# the original brief" > "$HAKUX_WORK/briefs/selftesthb.md"
HEAD1=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
hb_row 201 lane/selftesthb "$HEAD1"
out=$(hb list)
check "list names the lane it would resume" grep -q "WOULD RESUME lane.selftesthb" <<< "$out"
check "list starts no session" bash -c '! grep -q systemd-run "$HB_LOG"'

hb_reset; hb >/dev/null
check "a handed-back PR resumes its lane" hb_ran selftesthb
check "the resume is announced on the PR" hb_said "[job.handback] Resumed \`lane.selftesthb\`"
check "the handback is appended to the lane's own brief" grep -q "no longer merges into" "$HAKUX_WORK/briefs/selftesthb.md"
check "the brief says merge, and says why not rebase" grep -q "un-ancestors any registered" "$HAKUX_WORK/briefs/selftesthb.md"
check "the brief tells the lane to re-apply fold-ready" grep -q "gh-label.sh add 201 fold-ready" "$HAKUX_WORK/briefs/selftesthb.md"
check "the original brief is still there under it" grep -q "the original brief" "$HAKUX_WORK/briefs/selftesthb.md"

# RESUME ONLY ON A NEW CAUSE. A lane resumed twice for one head has been given
# nothing new to read; it re-opens the same NOTES.md and the same diff, and
# spends one of the four attempts the escalation policy allows doing it.
hb_reset; hb >/dev/null
check "the same head does not resume the lane a second time" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and says nothing on the PR the second time" bash -c '[ ! -s "$HB/comments.log" ]'
out=$(hb list)
check "list explains the skip by naming the head" grep -q "already actioned at aaaaaaaaaa" <<< "$out"

# ...but a head that moved IS new information: the lane pushed, and the merge
# conflicts somewhere else.
HEAD2=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
printf 'label=needs-rebase\nbranch=lane/selftesthb\nhead=%s\nfiles=docs/testing/jobs/selftest.sh\n' "$HEAD2" \
    > "$HAKUX_WORK/handback/cause/201-$HEAD2"
hb_reset; hb_row 201 lane/selftesthb "$HEAD2"; hb >/dev/null
check "a new head resumes the lane again" hb_ran selftesthb
check "fold.sh's recorded cause reaches the lane's brief" grep -q "conflicting in: docs/testing/jobs/selftest.sh" "$HAKUX_WORK/briefs/selftesthb.md"

# A lane that resolved its conflict re-applies fold-ready. Its head has moved,
# so the cause looks new -- and resuming it now would put a second session on
# work that is already back in the pipeline. This is the loop this job must not
# become, and the head-sha key alone does not stop it.
hb_reset; hb_row 201 lane/selftesthb cccccccccccccccccccccccccccccccccccccccc "needs-rebase,fold-ready"
out=$(hb list); hb >/dev/null
check "a PR that also carries fold-ready is left alone" bash -c '! grep -q systemd-run "$HB_LOG"'
check "list says why it was left alone" grep -q "already moved on" <<< "$out"

# THE LANE NAME IS NOT THE PR. Both of these are live head branches on this
# repository, and neither has a local worktree to resume.
hb_reset; hb_row 202 claude/hakux-orchestration-design-e663m8 dddddddddddddddddddddddddddddddddddddddd
hb >/dev/null
check "a claude/* head starts nothing" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and the PR is told there is no local lane" hb_said "no local lane can act on it"
check "naming the shape it needed" hb_said 'is not a `lane/<name>` branch'
hb_reset; hb >/dev/null
check "a PR with no lane is told once, not once a tick" bash -c '[ ! -s "$HB/comments.log" ]'

hb_reset; hb_row 203 lane/cloud-109 eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
hb >/dev/null
check "a lane/cloud-* head starts no local lane" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and is told cloud lanes remediate themselves" hb_said "cloud lanes remediate themselves"

# A lane whose unit is still running is not stalled. systemd-run on a live unit
# fails AFTER lane.sh has counted the attempt, so this guard is one of the four
# attempts, not a tidiness.
hb_reset; echo "hakux-lane-selftesthb" > "$HB/active"
hb_row 201 lane/selftesthb ffffffffffffffffffffffffffffffffffffffff
hb >/dev/null
check "a lane whose unit is still active is not resumed" bash -c '! grep -q systemd-run "$HB_LOG"'
: > "$HB/active"

# THE FLEET CAP IS NOT A FAILURE, AND MUST NOT BE REMEMBERED AS ONE. lane.sh
# checks LANE_MAX before it counts the attempt, so nothing was spent and the
# cause is still unactioned -- writing the marker here would park the PR exactly
# the way `needs-rebase` already did.
hb_reset; printf 'hakux-lane-other1\nhakux-lane-other2\n' > "$HB/active"
HEAD3=1111111111111111111111111111111111111111
hb_row 201 lane/selftesthb "$HEAD3"
out=$(hb)
check "at LANE_MAX nothing is resumed" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and the tick says the cap is why" grep -q "fleet at cap" <<< "$out"
check "the cap leaves no marker for that head" [ ! -f "$HAKUX_WORK/handback/done/needs-rebase-201-$HEAD3" ]
# ...and it leaves no half-handback in the brief either. The section goes in
# before the resume, because that file is what the session is handed; a tick
# that appends and then does not resume appends again next tick.
check "a capped tick rolls its handback back out of the brief" \
    [ "$(grep -c 'no longer merges into' "$HAKUX_WORK/briefs/selftesthb.md")" -eq 2 ]
: > "$HB/active"; hb_reset; hb >/dev/null
check "so the next tick, under the cap, resumes it" hb_ran selftesthb
check "and the brief gains exactly one more handback" \
    [ "$(grep -c 'no longer merges into' "$HAKUX_WORK/briefs/selftesthb.md")" -eq 3 ]

# THE END OF THE LINE STAYS REACHABLE. lane.sh refuses past LANE_MAX_ATTEMPTS;
# the board opens the decision-needed issue. A job that swallowed that refusal
# would park the PR silently for the fourth time.
hb_reset; echo 9 > "$HAKUX_WORK/attempts/selftesthb"
hb_row 201 lane/selftesthb 2222222222222222222222222222222222222222
hb >/dev/null
check "an exhausted lane is not started again" bash -c '! grep -q systemd-run "$HB_LOG"'
check "the exhausted PR is labelled blocked:needs-owner" grep -q 'api -X POST repos/example/hakux/issues/201/labels.*blocked:needs-owner' "$HB_LOG"
check "and the comment hands it to the board's decision-needed path" hb_said "decision-needed"
check "quoting lane.sh's own refusal, so the count is visible" hb_said "LANE_MAX_ATTEMPTS"
rm -f "$HAKUX_WORK/attempts/selftesthb"

# The pickup is a TABLE of labels, not a branch per label: needs-remediation
# and the two audit labels join it as a row (lane.auditoutlet, PR #130).
check "the pickup is one table of labels" grep -q '^HANDBACK_ROWS=(' "$HERE/handback.sh"
check "handback.sh starts no session itself; lane.sh does" \
    bash -c '! grep -qE "^[^#]*systemd-run" "$HERE/handback.sh"'

# fold.sh's half: it records the cause and resolves nothing. A real conflict
# needs a real remote and a real push, so this pins the two lines that connect
# the jobs; the consumption of the cause file is checked behaviourally above.
check "fold.sh records the conflicting files where handback.sh reads them" \
    grep -q 'handback/cause/\$pr-\$head' "$HERE/fold.sh"
check "fold.sh calls the actor at the end of its tick" \
    grep -q 'jobs/handback.sh" "\$mode"' "$HERE/fold.sh"
check "fold.sh still resolves no conflict itself" \
    bash -c '! grep -qE "checkout --(ours|theirs)|merge -X|-s (ours|recursive)" "$HERE/fold.sh"'
check "roles/board.md tells the board handback.sh owns needs-rebase" \
    grep -q 'needs-rebase` is not yours' "$HERE/roles/board.md"

# The --jq the shim bypasses. gh runs it internally, so a typo in it is invisible
# to every check above; jq is the same program gh embeds.
if command -v jq >/dev/null 2>&1; then
    q=$(sed -n "s/.*--jq '\(sort_by(\.number).*\)' .*/\1/p" "$HERE/handback.sh" | head -1)
    got=$(printf '%s' '[{"number":9,"headRefName":"lane/x","headRefOid":"ab","labels":[{"name":"needs-rebase"},{"name":"folded"}]}]' \
          | jq -r "$q" 2>&1)
    check "the pickup query yields number/branch/head/labels" [ "$got" = "$(printf '9\tlane/x\tab\tneeds-rebase,folded')" ]
else
    echo "  note: jq not on PATH; the pickup query was not exercised"
fi

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
