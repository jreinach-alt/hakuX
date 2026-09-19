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
