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

echo "== the board's three states: covered, blocked, AVAILABLE"
# WHY THIS IS HERE. check_coverage.py demanded that every open issue be owned
# by a lane or carry a non-empty `blocked_on`, and a failure makes preflight
# red for every lane on the repository. A backlog's normal condition -- open,
# unblocked, nobody on it yet, waiting for capacity -- had no third state, so
# the board's only way to get a green preflight for an issue it could not
# dispatch this tick was to write into the one field that means "do not
# dispatch this". On 2026-09-18 six open rows carried a `blocked_on` whose
# first words were "NOT BLOCKED" and two more (since deleted) read "Blocked on
# local dispatch capacity this tick, not on anything technical."
#
# THE FIXTURE IS A WHOLE FAKE BOARD, not a unit test of a regex, because the
# defect is a disagreement BETWEEN two consumers of one schema: coverage
# counted those rows as blocked while fleet undid it with a substring search.
# Both scripts read the board through board_files.py, which falls back to the
# working tree when HAKUX_BOARD_REF is empty -- so a directory holding copies
# of the three modules plus two toml files IS a board, and the real scripts
# run against it unmodified.
#
# SELFTEST_BOARD_SRC exists so this section can be pointed at the OLD scripts
# (`git show origin/master:docs/testing/check_coverage.py` into a directory)
# and seen to fail, rather than being reasoned about. Verified 2026-09-19:
# against master@bdeab36f75 four of these checks fail -- the available row
# reads as an uncovered gap, the "NOT BLOCKED" opening passes as a blocker,
# and fleet calls both the unclassified row and the mid-text mention
# dispatchable.
BSRC="${SELFTEST_BOARD_SRC:-$TESTING}"
BD="$T/board"; mkdir -p "$BD" "$T/bin2" "$DISPATCH_DIR/fleet" "$DISPATCH_DIR/deliveries"
cp "$BSRC/check_coverage.py" "$BSRC/fleet.py" "$BSRC/board_files.py" "$BD/"
check "the three board modules were copied from $BSRC" \
    bash -c '[ -s "$1/check_coverage.py" ] && [ -s "$1/fleet.py" ] && [ -s "$1/board_files.py" ]' _ "$BD"
printf '{"lane":"alpha","agent":"a","issues":["1"],"state":"running","dispatched_utc":"2026-09-19T00:00:00Z","waiting_on":""}\n' > "$DISPATCH_DIR/fleet/alpha.json"
: > "$DISPATCH_DIR/deliveries/alpha.md"     # so the UNBRIEFED tail stays out of line 1
cat > "$T/bin2/gh" <<'EOF'
#!/usr/bin/env bash
# Four open issues, which is what a board fixture needs and all it needs.
[[ "$*" == *"issue list"* ]] || exit 0
echo '[{"number":1,"title":"owned by a running lane"},{"number":2,"title":"the available one"},{"number":3,"title":"really blocked"},{"number":4,"title":"mentions NOT BLOCKED mid-text"}]'
EOF
chmod +x "$T/bin2/gh"
board() {   # <variant>: write the fixture board, varying issue 2 only
    python3 - "$BD" "$1" <<'PY'
import os, sys
bd, variant = sys.argv[1], sys.argv[2]
held = "[1, 2]" if variant == "ownedavail" else "[1]"
open(os.path.join(bd, "territory.toml"), "w").write(
    '[lane.alpha]\nfiles = []\nissues = %s\n\n[free]\nnote = "x"\n' % held)
# Issue 4 is the false positive a substring search produces: the board
# recording a wording it had ALREADY corrected. It must read as blocked.
rows = [
    ('1', 'status = "open"\n'
          'status_note = "a lane is on it"\n'
          'blocked_on = ""\n'),
    ('3', 'status = "open"\n'
          'status_note = "n"\n'
          'blocker_tested = "read the spec 2026-09-19"\n'
          'blocked_on = "Blocked on real Xbox hardware, which nobody has."\n'),
    ('4', 'status = "open"\n'
          'status_note = "n"\n'
          'blocker_tested = "2026-09-19"\n'
          'blocked_on = "ORDERED behind lane.alpha. The gate was right to '
          'refuse the earlier wording: I had written NOT BLOCKED and then '
          'left it unallocated, which reads as coverage and is not. Also '
          'DIRTY_MEMORY_NV2A_TEX is test-and-cleared."\n'),
]
two = {
    # the third state, written correctly
    "base":       'status = "open"\ndispatch_state = "available"\nblocked_on = ""\n',
    # same row, but a lane holds it too -- the count must not read zero
    "ownedavail": 'status = "open"\ndispatch_state = "available"\nblocked_on = ""\n',
    # nobody classified it: still a failure, and the gate must say so
    "gap":        'status = "open"\nblocked_on = ""\n',
    # the shape being migrated away from
    "notblocked": 'status = "open"\nblocked_on = "NOT BLOCKED, and it is the '
                  'best offline-implementable prize on the board."\n',
    # the waiting-for-a-slot shape, in the field that means the opposite
    "capacity":   'status = "open"\nblocked_on = "Blocked on local dispatch '
                  'capacity this tick, not on anything technical."\n',
    # finished work reading as available is how an issue gets re-dispatched
    "done":       'status = "fixed-verified"\ndispatch_state = "available"\n'
                  'blocked_on = ""\n',
    "both":       'status = "open"\ndispatch_state = "available"\n'
                  'blocked_on = "Blocked on real hardware."\n',
    "typo":       'status = "open"\ndispatch_state = "avaliable"\n'
                  'blocked_on = ""\n',
}[variant]
rows.append(('2', 'status_note = "n"\n' + two))
out = []
for n, body in sorted(rows, key=lambda r: int(r[0])):
    out.append('[issue.%s]\ntitle = "issue %s"\n%s' % (n, n, body))
open(os.path.join(bd, "nv2a_issues.toml"), "w").write("\n".join(out))
PY
}
cov() { env PATH="$T/bin2:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$DISPATCH_DIR" \
            python3 "$BD/check_coverage.py" 2>&1; }
flt() { env PATH="$T/bin2:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$DISPATCH_DIR" \
            python3 "$BD/fleet.py" 2>&1; }
# Every assertion below is on the OUTPUT WORDS, never on the exit code alone:
# the old scripts exit 1 on most of these variants too, for the wrong reason
# (the available row reads as an uncovered gap), so rc is far too coarse to
# tell the fix from the defect.
board base; out=$(cov)
check "an explicitly AVAILABLE row is covered -- the third state" \
    grep -q "^coverage ok (4 open: 1 AVAILABLE, 2 blocked, 1 owned by a lane" <<< "$out"
out=$(flt)
check "fleet calls exactly the available row dispatchable" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (1)$" <<< "$out"
check "...and it is #2, by its structured field and not by its prose" \
    grep -q "^  #2 .*dispatch_state=available" <<< "$out"
check "a mid-text 'NOT BLOCKED' about another row is NOT dispatchable" \
    bash -c '! grep -q "^  #4 " <<< "$1"' _ "$out"
check "nothing is unclassified on a fully classified board" \
    grep -q "^=== NEITHER BLOCKED NOR MARKED AVAILABLE (0)$" <<< "$out"

# EVERY MIGRATED ROW ON THE REAL BOARD IS ALSO HELD BY A LANE, so a count of
# "available and not owned" reads 0 exactly when the state is in use. That was
# the first version of the summary line and it is the reason this variant
# exists: the number must be over ALL open issues, overlap and all.
board ownedavail; out=$(cov)
check "the AVAILABLE count does not read zero when a lane also holds the row" \
    grep -q "^coverage ok (4 open: 1 AVAILABLE, 2 blocked, 2 owned by a lane" <<< "$out"
out=$(flt)
check "an available row held by a RUNNING lane is not dispatchable" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (0)$" <<< "$out"

board gap; out=$(cov)
check "an UNCLASSIFIED row still fails -- the gate is not weakened" \
    grep -q "FAIL: 1 open issue(s) with neither a lane nor a blocker" <<< "$out"
check "the failure names all three ways to clear it" \
    grep -q 'dispatch_state = "available"' <<< "$out"
out=$(flt)
check "fleet does not call an unclassified row dispatchable" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (0)$" <<< "$out"
check "fleet reports it as neither blocked nor available instead" \
    grep -q "^  #2 " <<< "$(sed -n '/NEITHER BLOCKED NOR MARKED/,$p' <<< "$out")"
# The old code called this row DISPATCHABLE, which was the wrong description
# and a non-zero exit. Describing it accurately must not turn it into a note:
# the FAIL is the only thing that makes anyone classify it.
check "an unclassified row still costs fleet a FAIL, not just a note" \
    grep -q "FAIL: 1 open issue(s) are NEITHER BLOCKED NOR MARKED AVAILABLE" <<< "$out"

board notblocked; out=$(cov)
check "a blocked_on that OPENS with NOT BLOCKED fails" \
    grep -q "FAIL: 1 .blocked_on. that OPENS BY SAYING IT IS NOT BLOCKED" <<< "$out"
board capacity; out=$(cov)
check "'blocked on dispatch capacity, not on anything technical' fails" \
    grep -q "OPENS BY SAYING IT IS NOT BLOCKED" <<< "$out"
board done; out=$(cov)
check "AVAILABLE on work that is no longer open fails" \
    grep -q '`available` with status' <<< "$out"
board both; out=$(cov)
check "AVAILABLE alongside a blocker fails as the contradiction it is" \
    grep -q '`available` with a non-empty `blocked_on`' <<< "$out"
board typo; out=$(cov)
check "an unrecognised dispatch_state fails rather than reading as classified" \
    grep -q "is not one of available, blocked" <<< "$out"

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
