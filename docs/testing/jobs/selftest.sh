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

echo "== affinity: the lane registration, and saying so when there is none"
# WHY. On 2026-09-19 #89's A/B pair ran base on the `thor` and fix on the
# `nova`. affinity.py exists to stop exactly that, and it was INERT: $D/lanes/
# was empty, so serving() returned [], so rule 2's _live() was false for a
# device that was in fact serving and rule 3 had no devices to hash over. The
# lane pid file was written once per worker process, so a single `rm` by
# anyone disabled pinning until the dispatcher was restarted -- and no log
# line, no status field and no note reachable by a reader said a word.
#
# These checks pin the three things that were missing, not the remover, which
# is still unidentified (NOTES.md on lane/armpin has the refuted hypotheses).
export AD="$T/aff"; mkdir -p "$AD"/{lanes,running,results,splits,queue,logs}
export TESTING AFF="$TESTING/affinity.py"
sleep 600 & export LIVEPID=$!               # a pid that is certainly alive
sleep 0   & DEADPID=$!; wait $DEADPID 2>/dev/null   # and one that certainly is not
disp() {   # run shell inside a sourced dispatcher.sh, as the nova, against $AD
    ( export DISPATCH_DIR="$AD" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}

# --- serving(): the single input every rule above is decided over.
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
printf '%s\n' "$DEADPID" > "$AD/lanes/thor"
printf '%s\n' "2026-09-14" > "$AD/lanes/remote.lastbrief"   # check_coverage.py's stamp
check "serving lists the lane whose pid is alive and not the one whose pid is dead" \
    [ "$(python3 "$AFF" "$AD" --serving 2>/dev/null)" = "nova" ]
# Counted, not grepped for absence: "no lastbrief in the output" is also true
# of no output at all, and a check that a missing feature satisfies has
# measured nothing. Three files in lanes/, exactly one device.
check "a <lane>.lastbrief stamp sharing the directory is not mistaken for a device" \
    [ "$(python3 "$AFF" "$AD" --serving 2>/dev/null | wc -w)" = 1 ]

# --- the two behaviours the brief says must stay true. CONTROLS: these pass
# against the old file too, and are here to show the fix did not buy its
# visibility by making a pin block a claim.
mkdir -p "$AD/results/r-old"
printf '{"expect":"/p/e7d2.json"}\n' > "$AD/results/r-old/request.json"
printf '{"device_label":"thor"}\n'   > "$AD/results/r-old/result.json"
printf '{"requester":"arms-x-fix","expect":"/p/e7d2.json"}\n' > "$AD/q.req"
check "CONTROL: a pin to a device that is NOT serving falls through rather than stalling" \
    [ -z "$(python3 "$AFF" "$AD" "$AD/q.req" 2>/dev/null)" ]
printf '{"device_label":"nova"}\n' > "$AD/results/r-old/result.json"
check "CONTROL: a pin to a device that IS serving is still honoured" \
    [ "$(python3 "$AFF" "$AD" "$AD/q.req" 2>/dev/null)" = "nova" ]

# --- the fallthrough must stop being silent. This is the defect: every rule
# ran over an empty device set and printed the same "" a request with no
# sibling prints.
rm -rf "$AD/lanes" "$AD/splits"; mkdir -p "$AD/lanes" "$AD/splits"
python3 "$AFF" "$AD" "$AD/q.req" >/dev/null 2>&1
check "a request that could not be pinned AT ALL leaves a note" \
    bash -c '[ -n "$(ls "$AD"/splits/*.blind.txt 2>/dev/null)" ]'
check "the note names the prediction whose pair may now split" \
    bash -c 'grep -q "e7d2.json" "$AD"/splits/*.blind.txt'
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"; printf '%s\n' "$LIVEPID" > "$AD/lanes/thor"
rm -f "$AD"/splits/*.blind.txt
python3 "$AFF" "$AD" "$AD/q.req" >/dev/null 2>&1
check "CONTROL: a request pinned normally leaves no blind note" \
    bash -c '[ -z "$(ls "$AD"/splits/*.blind.txt 2>/dev/null)" ]'

# --- the lane file itself. It was written once per process; that permanence,
# not the removal, is what cost five hours.
# Chained with && throughout, never `;`. Sequenced with `;` these all pass
# against a file that has no lane_claim in it at all -- the missing function
# fails, nothing is ever created, and "the file is absent" comes out true.
check "lane_claim restores a registration removed from outside, so a removal costs a tick not a restart" \
    disp 'lane_claim && rm -f "$D/lanes/nova" && lane_claim && [ "$(cat "$D/lanes/nova")" = "$$" ]'
check "lane_release drops my own registration" \
    disp 'lane_claim && [ -e "$D/lanes/nova" ] && lane_release && [ ! -e "$D/lanes/nova" ]'
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
check "lane_release SUCCEEDS and leaves a registration holding ANOTHER pid (a dead predecessor cannot evict its live successor)" \
    disp 'lane_release && [ "$(cat "$D/lanes/nova")" = "'"$LIVEPID"'" ]'
check "no lane file is removed by name anywhere; every removal goes through lane_release" \
    bash -c '! grep -q "rm -f \"\$D/lanes/" "$TESTING/dispatcher.sh"'
check "the registration is re-asserted after the hold check, not only at worker startup" \
    python3 -c 'import sys; s=open(sys.argv[1]).read(); i=s.index("$D/hold/$DEVICE_LABEL"); sys.exit(0 if "lane_claim" in s[i:] else 1)' "$TESTING/dispatcher.sh"
check "a held device does not re-register itself thirty seconds later" \
    python3 -c 'import sys; s=open(sys.argv[1]).read(); h=s.index("$D/hold/$DEVICE_LABEL"); sys.exit(0 if s.index("lane_claim", h) > s.index("lane_release", h) else 1)' "$TESTING/dispatcher.sh"

# --- the dispatcher must say it out loud, once, not per claim.
rm -rf "$AD/lanes"; mkdir -p "$AD/lanes"; : > "$AD/logs/dispatcher.log"
disp 'lane_blind_check one; lane_blind_check two' >/dev/null 2>&1
check "claiming with no lane registered logs AFFINITY BLIND" \
    grep -q "AFFINITY BLIND" "$AD/logs/dispatcher.log"
check "it is logged once per outage, not once per claim (the sweep queues one request per suite)" \
    [ "$(grep -c 'AFFINITY BLIND' "$AD/logs/dispatcher.log")" = 1 ]
: > "$AD/logs/dispatcher.log"
check "the outage has an END as well as a start: coming back is logged too" \
    disp 'lane_blind_check one && printf "%s\n" "'"$LIVEPID"'" > "$D/lanes/nova" && lane_blind_check two &&
          grep -q "AFFINITY BLIND" "$D/logs/dispatcher.log" && grep -q "lanes registered again" "$D/logs/dispatcher.log"'
: > "$AD/logs/dispatcher.log"
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
check "a claim made with a lane registered logs nothing at all" \
    disp 'lane_blind_check one && lane_blind_check two && [ ! -s "$D/logs/dispatcher.log" ]'

# --- $D/splits/ gets a reader. The note was always written correctly; it was
# discoverable only by someone who already suspected it and knew the path.
mkdir -p "$DISPATCH_DIR/splits" "$DISPATCH_DIR/lanes"
printf 'prediction e7d2d739.json was pinned to thor, which is not serving; freed this request\n' \
    > "$DISPATCH_DIR/splits/1789793572-arms-blitsafe-fix-3718905.req.txt"
sout=$(bash "$HERE/status.sh" --print 2>&1)
check "status.sh reports what affinity is doing at all" grep -q '^- affinity:' <<< "$sout"
check "status.sh warns when no lane is registered and pinning is inert" \
    grep -q 'no device lane is registered' <<< "$sout"
check "status.sh surfaces a recent split note, with the prediction in it" \
    grep -q 'e7d2d739.json was pinned to thor' <<< "$sout"
kill "$LIVEPID" 2>/dev/null; wait "$LIVEPID" 2>/dev/null

echo "== the audit outlet: one dispatch path, one cap, and no terminal label"
# MEASURED 2026-09-19. Pass 1 on PR #102 worked -- an audit file, a review
# reading 0 HIGH / 2 MEDIUM / 5 LOW, the label needs-remediation -- and nothing
# could ever pick it up. cloud.sh filtered the remediate pickup on the head
# prefix lane/cloud- and #102's head is lane/blitsafe, a LOCAL lane; the rule
# in roles/board.md could only run on a board tick, and a tick only starts when
# fleet.py or the coverage gate says FAIL, neither of which counts an
# unremediated audit; and hakux-cloud.timer is disabled. needs-audit-1 and
# needs-remediation were terminal states.
AO="$T/ao"; mkdir -p "$AO/bin"
cat > "$AO/bin/gh" <<'EOF'
#!/usr/bin/env bash
# A gh that answers with ONE open PR: #102, head lane/blitsafe -- a LOCAL
# lane's branch, which is exactly the case the prefix filter could not see.
# The filter itself lives in the --jq expression, which a shim does not run,
# so the one property under test is emulated directly: a query that restricts
# the head branch to lane/cloud- cannot match #102.
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *'startswith("lane/cloud-")'* ]] && exit 0
        [[ "$args" == *"--label ${AO_LABEL:-needs-remediation}"* ]] || exit 0
        printf '102\t%s\tblit: clamp the destination rect\n' "${AO_HEAD:-lane/blitsafe}"
        exit 0 ;;
    "api "*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${AO_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$AO/bin/gh"; AOPATH="$AO/bin:$PATH"

: > "$SELFTEST_GH_LOG"
aout=$(PATH="$AOPATH" bash "$HERE/cloud.sh" list 2>&1)
check "a needs-remediation PR on a LOCAL lane's branch is claimable" \
    grep -q "would claim remediate #102 (lane/blitsafe)" <<< "$aout"
check "the pickup query does not filter on the head branch at all" \
    bash -c '! grep -q "headRefName | startswith" "$HERE/cloud.sh"'
check "the pickup skips a PR already escalated to the owner" \
    grep -q 'blocked:needs-owner' "$HERE/cloud.sh"

# THE CAP IS ONE NUMBER. An audit session costs what a lane session costs, so
# it is capped by LANE_MAX and by nothing else -- and the default is read out
# of lane.sh, because a repeated default is a second cap that drifts the first
# time one of the two is edited.
lmax=$(sed -n 's/^LANE_MAX=\([0-9][0-9]*\).*/\1/p' "$TESTING/lane.sh" | head -1)
check "the cap it reports is the number lane.sh defaults to, not one of its own" \
    grep -q "cap: LANE_MAX=${lmax:-UNREADABLE} " <<< "$aout"
echo 'LANE_MAX=9' > "$HAKUX_WORK/limits.env"
aout2=$(PATH="$AOPATH" bash "$HERE/cloud.sh" list 2>&1); rm -f "$HAKUX_WORK/limits.env"
check "\$WORK/limits.env overrides it, exactly as it does for lane.sh" \
    grep -q "cap: LANE_MAX=9 " <<< "$aout2"
check "the cap counts the unit glob lane.sh counts" \
    grep -q "list-units 'hakux-lane-\*' --state=active,activating" "$HERE/cloud.sh"
check "the session's unit is a hakux-lane-* unit, so lane.sh's own count sees it" \
    grep -q 'unit="hakux-lane-\$name"' "$HERE/cloud.sh"
check "no second cap: CLOUD_MAX is gone" bash -c '! grep -q CLOUD_MAX "$HERE/cloud.sh"'

# THE TRIGGER. hakux-cloud.timer is disabled and stays disabled; the timer that
# starts lanes starts this too, and it must run BEFORE the board's own early
# exit, because a fleet with nothing actionable is exactly when an audit is
# waiting.
check "board.sh dispatches the audit outlet" \
    grep -q 'bash "\$JOBS/cloud.sh"' "$HERE/board.sh"
# Anchor on the say() CALL, not the words: the first draft of this check
# matched a comment three lines above the dispatch that happened to contain
# "nothing actionable", so the exit appeared to come first and the check
# failed against the file that was correct.
check "it does so before the 'nothing actionable' exit, which is the tick an audit needs" bash -c '
    c=$(grep -n "bash \"\$JOBS/cloud.sh\"" "$HERE/board.sh" | head -1 | cut -d: -f1)
    n=$(grep -n "say \"nothing actionable\"" "$HERE/board.sh" | head -1 | cut -d: -f1)
    [ -n "$c" ] && [ -n "$n" ] && [ "$c" -lt "$n" ]'

# CLEARING THE STATE LABEL IS PART OF THE JOB. A label that is never cleared
# makes the same PR eligible forever, and the session meant to clear it is the
# one thing here that can forget; so the unit's tail checks, and the answer
# differs by whether the session left a next state behind.
: > "$SELFTEST_GH_LOG"
PATH="$AOPATH" AO_LABELS="needs-audit-1 needs-remediation claimed:cloud" \
    bash "$HERE/cloud.sh" finish audit1 102 >/dev/null 2>&1
check "finish drops the claim" \
    grep -q 'api -X DELETE repos/example/hakux/issues/102/labels/claimed%3Acloud' "$SELFTEST_GH_LOG"
check "finish clears needs-audit-1 once the session has set a successor state" \
    grep -q 'api -X DELETE repos/example/hakux/issues/102/labels/needs-audit-1' "$SELFTEST_GH_LOG"
: > "$SELFTEST_GH_LOG"
PATH="$AOPATH" AO_LABELS="needs-audit-1 claimed:cloud" \
    bash "$HERE/cloud.sh" finish audit1 102 >/dev/null 2>&1
check "a session that set NO successor does not get needs-audit-1 cleared (the next tick retries it)" \
    bash -c '! grep -q "labels/needs-audit-1" "$SELFTEST_GH_LOG"'
check "and the PR is told, rather than the unit ending silently" \
    grep -q '^pr comment 102' "$SELFTEST_GH_LOG"

# ...AND THAT RETRY IS BOUNDED. Leaving the label is what makes a retry
# possible; the attempt counter is what stops it being endless. The refusal
# runs before any git or worktree work, so it is cheap and testable.
amax=$(sed -n 's/^LANE_MAX_ATTEMPTS=\([0-9][0-9]*\).*/\1/p' "$HERE/models.env" | head -1)
: > "$SELFTEST_GH_LOG"; echo "${amax:-4}" > "$HAKUX_WORK/attempts/cloud-remediate-102"
PATH="$AOPATH" bash "$HERE/cloud.sh" >/dev/null 2>&1
check "a PR whose sessions keep ending unfinished goes to the owner, not to a fifth session" \
    grep -q 'labels\[\]=blocked:needs-owner' "$SELFTEST_GH_LOG"
check "and no session is started for it" bash -c '! grep -q "^systemd-run" "$SELFTEST_GH_LOG"'
rm -f "$HAKUX_WORK/attempts/cloud-remediate-102"

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
