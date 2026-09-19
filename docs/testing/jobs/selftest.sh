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

echo "== fold.sh: a root NOTES.md is the one conflict it may resolve"
# roles/lane.md used to ask every lane for NOTES.md in the branch ROOT. master
# had none, so the first fold landed one and every fold after it conflicted on
# that exact path -- for good, since master then held lane A's notes and lane
# B's were a conflicting rewrite of them. Four lanes were queued behind that.
# The instruction is now docs/lanes/<lane>/NOTES.md, but the lanes already
# running never saw it, so fold.sh moves an incoming root copy to the lane's
# own path. What this pins is the BOUNDARY: that move happens only when root
# NOTES.md is the whole conflict, and any source file in the list still sends
# the PR back untouched.
FD="$T/foldnotes"
fixture() {   # <dir> [extra file both sides change] -> a repo mid-merge, conflicted
    local d="$1" also="${2:-}"; rm -rf "$d"; mkdir -p "$d"
    git -c init.defaultBranch=master init -q "$d"
    git -C "$d" config user.email s@t; git -C "$d" config user.name s
    echo base > "$d/src.c"; git -C "$d" add -A; git -C "$d" commit -q -m base
    git -C "$d" checkout -q -b lane/fixture
    echo "lane B measured the thing" > "$d/NOTES.md"
    [ -n "$also" ] && echo "lane B code" > "$d/$also"
    git -C "$d" add -A; git -C "$d" commit -q -m lane
    git -C "$d" checkout -q master
    echo "lane A measured the other thing" > "$d/NOTES.md"
    [ -n "$also" ] && echo "master code" > "$d/$also"
    git -C "$d" add -A; git -C "$d" commit -q -m master
    git -C "$d" merge --no-ff --no-edit -m "fold: PR #1 lane/fixture -- t" lane/fixture >/dev/null 2>&1
}
unmerged() { git -C "$1" diff --name-only --diff-filter=U | tr '\n' ' '; }

fixture "$FD/only"
check "the fixture really conflicts, and only in NOTES.md" [ "$(unmerged "$FD/only")" = "NOTES.md " ]
bash "$HERE/fold.sh" resolve-notes "$FD/only" lane/fixture >"$FD/only.log" 2>&1; rc=$?
check "resolve-notes accepts a NOTES.md-only conflict" [ "$rc" = 0 ]
check "nothing is left unmerged" [ -z "$(unmerged "$FD/only")" ]
check "the lane's notes are kept, at the lane's own path" \
    bash -c 'grep -q "lane B measured" "$1/docs/lanes/fixture/NOTES.md"' _ "$FD/only"
check "master's root copy is untouched" \
    bash -c 'grep -q "lane A measured" "$1/NOTES.md"' _ "$FD/only"
check "the move is staged, not left dirty" \
    bash -c '[ -z "$(git -C "$1" diff --name-only)" ]' _ "$FD/only"
git -C "$FD/only" commit -q -m "fold: PR #1 lane/fixture -- t" >/dev/null 2>&1
check "the result is still a merge commit (both parents)" git -C "$FD/only" rev-parse -q --verify HEAD^2

fixture "$FD/code" src.c
check "the second fixture conflicts in a source file too" bash -c '[ "$(git -C "$1" diff --name-only --diff-filter=U | tr "\n" " ")" = "NOTES.md src.c " ]' _ "$FD/code"
bash "$HERE/fold.sh" resolve-notes "$FD/code" lane/fixture >"$FD/code.log" 2>&1; rc=$?
check "resolve-notes REFUSES when a source file conflicts as well" [ "$rc" != 0 ]
check "  and leaves the conflict exactly as it found it" [ "$(unmerged "$FD/code")" = "NOTES.md src.c " ]
check "  and writes no per-lane notes file" [ ! -e "$FD/code/docs/lanes/fixture/NOTES.md" ]

fixture "$FD/taken"
mkdir -p "$FD/taken/docs/lanes/fixture"; echo "an earlier record" > "$FD/taken/docs/lanes/fixture/NOTES.md"
bash "$HERE/fold.sh" resolve-notes "$FD/taken" lane/fixture >"$FD/taken.log" 2>&1; rc=$?
check "resolve-notes REFUSES when the destination is occupied (that would be a content decision)" [ "$rc" != 0 ]
check "  and does not overwrite what is there" grep -q "an earlier record" "$FD/taken/docs/lanes/fixture/NOTES.md"

check "roles/lane.md asks for the per-lane path, not the branch root" \
    grep -q 'docs/lanes/<your lane name>/NOTES.md' "$HERE/roles/lane.md"
check "roles/cloud.md asks for the same" grep -q 'docs/lanes/cloud-<short>/NOTES.md' "$HERE/roles/cloud.md"
check "no role file still asks for NOTES.md in the branch root" \
    bash -c '! grep -rn "NOTES.md\` in the branch root\|NOTES.md in the branch root" "$HERE/roles/"'

echo "== fold.sh: a folded lane branch is deleted, and nothing else is"
# Nothing ever removed a lane ref. arms.sh's collect() walks
# refs/remotes/origin/lane/* every tick and its fetch refspec does not prune,
# so the tick's cost grew with the number of lanes the project had EVER run:
# 25 refs on 2026-09-19, 8 of them folded days earlier. The fold is the moment
# that has just proved every commit is on the trunk, so that is where the
# delete belongs. What has to be pinned is that it deletes exactly the right
# three refs and refuses everything else -- a delete that reaches one ref too
# far un-arms a registered b_ref silently. A scratch bare "origin" makes all
# of it real: no shim can refuse a push or hold a branch in a worktree.
PD="$T/prune"; rm -rf "$PD"; mkdir -p "$PD"
pg() { git -C "$PD/repo" -c user.email=s@t -c user.name=s "$@"; }
git -c init.defaultBranch=master init -q --bare "$PD/origin.git"
git -c init.defaultBranch=master clone -q "$PD/origin.git" "$PD/repo" 2>/dev/null
echo base > "$PD/repo/f"; pg add -A; pg commit -q -m base; pg push -q origin master
# lane/gone: folded -- its commit reached master through a --no-ff merge, the
# shape a real fold leaves, so every commit keeps its sha and is an ancestor.
pg checkout -q -b lane/gone; echo g > "$PD/repo/g"; pg add -A; pg commit -q -m lane
pg push -q origin lane/gone
pg checkout -q master; pg merge -q --no-ff --no-edit lane/gone; pg push -q origin master
# lane/live: a commit that is NOT on master -- a lane that pushed after the
# fold's fetch looks exactly like this, and deleting it destroys work.
pg checkout -q -b lane/live master; echo l > "$PD/repo/l"; pg add -A; pg commit -q -m live
pg push -q origin lane/live; pg checkout -q master
# board: fully merged, so the ancestry test would PASS on it. Only the name
# saves it, which is the point of testing with this one rather than a fiction.
pg push -q origin master:refs/heads/board
MSHA=$(pg rev-parse master)

( export HAKUX_REPO_DIR="$PD/repo"; bash "$HERE/fold.sh" prune ) > "$PD/dry.log" 2>&1
check "prune's dry run names the folded lane branch" grep -q "would prune lane/gone" "$PD/dry.log"
check "prune's dry run keeps the one with commits not on master" grep -q "^keep  *lane/live" "$PD/dry.log"
check "prune's dry run counts what it saw" grep -q "total lane refs: 2, fully merged into master: 1" "$PD/dry.log"
check "prune's dry run deletes NOTHING" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/gone

( export HAKUX_REPO_DIR="$PD/repo"; bash "$HERE/fold.sh" prune --apply ) > "$PD/apply.log" 2>&1
check "prune --apply deletes the folded lane ref on origin" \
    bash -c '! git -C "$1/origin.git" rev-parse -q --verify refs/heads/lane/gone >/dev/null' _ "$PD"
check "  and the tracking ref, which is the one arms.sh actually walks" \
    bash -c '! git -C "$1/repo" rev-parse -q --verify refs/remotes/origin/lane/gone >/dev/null' _ "$PD"
check "  and the local head, which no worktree holds" \
    bash -c '! git -C "$1/repo" rev-parse -q --verify refs/heads/lane/gone >/dev/null' _ "$PD"
check "  and the merge commit it reached master by is still there" \
    bash -c 'git -C "$1/origin.git" merge-base --is-ancestor "$2" refs/heads/master' _ "$PD" "$MSHA"
check "prune --apply leaves a lane ref whose commits are not on master" \
    git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/live
check "  and leaves its tracking ref bound" git -C "$PD/repo" rev-parse -q --verify refs/remotes/origin/lane/live
check "prune --apply never touches a non-lane branch, however merged" \
    git -C "$PD/origin.git" rev-parse -q --verify refs/heads/board
check "prune --apply never touches the trunk" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/master

# The name guard, against the two refs that would pass every other test.
pg fetch -q origin '+refs/heads/board:refs/remotes/origin/board'
for bad in master board claude/hakux-orchestration-design-e663m8; do
    bash "$HERE/fold.sh" prune-branch "$PD/repo" "$bad" "$MSHA" > "$PD/bad.log" 2>&1; rc=$?
    check "prune-branch REFUSES '$bad'" [ "$rc" != 0 ]
    # An exit code alone is a coarse discriminator: a script that died before
    # reaching the guard exits non-zero too. Assert on the sentence.
    check "  and says which rule refused it" grep -q "only lane/\* refs are ever deleted" "$PD/bad.log"
done
check "  and master is still on origin afterwards" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/master
check "  and board is too" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/board

# The ancestry guard, which is what keeps a registered b_ref bound.
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/live "$MSHA" > "$PD/live.log" 2>&1; rc=$?
check "prune-branch REFUSES a lane ref whose commits are not on the proof commit" [ "$rc" != 0 ]
check "  and says it kept the ref, naming the sha it judged" grep -q "is NOT fully merged into .*ref KEPT" "$PD/live.log"
check "  and lane/live survives on origin" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/live

# A worktree holding the branch is not the edge case: on 2026-09-19 all eight
# already-merged lane branches had one. git refuses `branch -d` there, and
# that refusal is the wanted answer -- the remote ref and the tracking ref
# (the ones that cost a tick anything) still go.
pg checkout -q -b lane/held master; pg push -q origin lane/held; pg checkout -q master
git -C "$PD/repo" worktree add -q "$PD/heldwt" lane/held 2>/dev/null
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/held "$MSHA" > "$PD/held.log" 2>&1
check "a worktree-held branch still loses its ref on origin" \
    bash -c '! git -C "$1/origin.git" rev-parse -q --verify refs/heads/lane/held >/dev/null' _ "$PD"
check "  and its tracking ref" \
    bash -c '! git -C "$1/repo" rev-parse -q --verify refs/remotes/origin/lane/held >/dev/null' _ "$PD"
check "  but the local head the worktree holds is KEPT, not forced" \
    git -C "$PD/repo" rev-parse -q --verify refs/heads/lane/held
check "  and the log says so rather than passing over it" grep -q "local refs/heads/lane/held KEPT" "$PD/held.log"
check "  and names the command that removes the worktree" grep -q "lane.sh rm held" "$PD/held.log"
check "  and the worktree is left with a HEAD that resolves" git -C "$PD/heldwt" rev-parse --verify HEAD
# Run it again: the ref is gone from origin now. ls-remote --exit-code says 2
# for "no such ref" and something else for "could not ask", and those must not
# be confused -- a network failure that read as "already gone" would drop a
# tracking ref that is still bound to a live branch.
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/held "$MSHA" > "$PD/again.log" 2>&1; rc=$?
check "prune-branch is idempotent: a second run on a gone ref succeeds" [ "$rc" = 0 ]
check "  and says the ref was already gone rather than claiming a delete" \
    bash -c 'grep -q "origin has no such ref" "$1" && ! grep -q "deleted origin" "$1"' _ "$PD/again.log"
# The other half of that, and the half with teeth: an origin that cannot be
# reached at all must NOT read as "already gone". ls-remote --exit-code says 2
# for no-matching-ref and 128 for a fatal, and a `-ne 0` that lumps them
# together drops a tracking ref still bound to a live branch -- on a bad
# network, for every lane at once. lane/unreach is an ancestor of master, so
# only the unreachable-origin path can save it.
pg checkout -q -b lane/unreach master; pg push -q origin lane/unreach; pg checkout -q master
git -C "$PD/repo" remote set-url origin "$PD/no-such-remote.git"
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/unreach "$MSHA" > "$PD/unreach.log" 2>&1; rc=$?
git -C "$PD/repo" remote set-url origin "$PD/origin.git"
check "prune-branch REFUSES when it cannot reach origin at all" [ "$rc" != 0 ]
check "  and does NOT report it as already gone" \
    bash -c 'grep -q "cannot reach origin" "$1" && ! grep -q "no such ref" "$1"' _ "$PD/unreach.log"
check "  and KEEPS the tracking ref, which is still bound to a live branch" \
    git -C "$PD/repo" rev-parse -q --verify refs/remotes/origin/lane/unreach
check "  and leaves the branch on origin" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/unreach

# Where the delete sits in the fold path. A branch deleted on a fold whose
# push failed is work destroyed, so the call must come AFTER that push -- a
# line-number test, not a search for a word that could be in a comment.
pushln=$(grep -n 'push -q origin "HEAD:$TIP"' "$HERE/fold.sh" | head -1 | cut -d: -f1)
pruneln=$(grep -n '^ *prune_branch "$WT" "$branch" HEAD$' "$HERE/fold.sh" | head -1 | cut -d: -f1)
check "the fold path prunes the branch it just folded" bash -c '[ -n "${1:-}" ]' _ "$pruneln"
check "  and only after the push to the trunk succeeded" \
    bash -c '[ -n "${1:-}" ] && [ -n "${2:-}" ] && [ "$2" -gt "$1" ]' _ "$pushln" "$pruneln"
check "no job script forces a branch deletion or a push" \
    bash -c '! grep -nE "branch +-D|push [^|#]*--force" "$1"/*.sh' _ "$HERE"

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
