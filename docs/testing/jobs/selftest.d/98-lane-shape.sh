# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# WHAT A LANE IS. Four jobs tested `lane/*` when what they meant was "a branch
# a lane owns". `lane.remote` is a cloud session on
# `claude/docs-tooling-agentic-coding-u152m1` -- a real lane, contributing for
# days, and the prefix is a proxy that fails on exactly it: arms.sh never
# collected its predictions (so the device pipeline had never once been
# available to it), fleet.py counted it in no PR section and reported it as a
# claim with no agent every tick, and handback.sh called it "whoever owns this
# branch". The lane set comes from the board now: a territory row carrying
# `remote` names the branch, and `jobs/remote-lane.sh` is the one reader.
#
# 98 because it builds everything it uses and nothing after it reads its state.
# It writes only under $T/laneshape and its own $HAKUX_WORK/handback PR numbers
# (3xx, kept clear of 99-handback.sh's 2xx).
#
# TO SEE THESE CHECKS FAIL AGAINST THE CODE THEY REPLACE: unpack master's
# docs/testing into a scratch tree, copy this file into its selftest.d, and run
# that tree's selftest.sh. Master has no remote-lane.sh, so every job there is
# the old one. Measured 2026-09-19 against master@841a38736c: 19 of these fail.

echo "== a lane is a branch with an open PR, not a branch named lane/*"
LS="$T/laneshape"; rm -rf "$LS"; mkdir -p "$LS/bin" "$LS/work"

# The board this fragment reasons about. HAKUX_TERRITORY points remote-lane.sh
# at one file; the default path is board_files.py and origin/board, exercised
# at the bottom against the real board.
cat > "$LS/territory.toml" <<'TOML'
wave = 1
updated_utc = "2026-09-19T00:00:00Z"

[lane.alpha]
issues = []
files = []

[lane.elsewhere]
issues = []
files = []
remote = "claude/elsewhere-u1"

[lane.prefixed]
issues = []
files = []
remote = true
TOML

# ---------------------------------------------------------- the one reader
( . "$HERE/remote-lane.sh"
  HAKUX_TERRITORY="$LS/territory.toml" remote_map > "$LS/map.tsv" ) 2>/dev/null
check "a row's \`remote\` string is the branch it names" \
    grep -qxF "$(printf 'claude/elsewhere-u1\telsewhere')" "$LS/map.tsv"
check "\`remote = true\` means the conventional lane/<row name>" \
    grep -qxF "$(printf 'lane/prefixed\tprefixed')" "$LS/map.tsv"
check "a row with no \`remote\` names no branch" \
    bash -c '! grep -q alpha "$1"' _ "$LS/map.tsv"
# A READ FAILURE IS NOT AN EMPTY MAP. Every caller below fails in its own
# direction on this, and they are not the same direction -- so the helper has
# to be able to say which happened.
check "an unreadable board is reported as unreadable, not as no remote lanes" \
    bash -c '. "$1/remote-lane.sh"; ! HAKUX_TERRITORY="$2/nosuch.toml" remote_readable' _ "$HERE" "$LS"

# ------------------------------------------------------------------ arms.sh
# THE DEVICE PIPELINE, WHICH THIS LANE HAD NEVER REACHED. A bare origin with a
# non-lane/* branch carrying three registrations, and a gh that says the branch
# has an open PR. Everything real: the fetch, collect(), the watermark.
LSA="$LS/arms"; mkdir -p "$LSA"
ag() { git -C "$LSA/repo" -c user.email=s@t -c user.name=s "$@"; }
git -c init.defaultBranch=master init -q --bare "$LSA/origin.git"
git -c init.defaultBranch=master clone -q "$LSA/origin.git" "$LSA/repo" 2>/dev/null
mkdir -p "$LSA/repo/docs/testing/predictions"
echo base > "$LSA/repo/f"; ag add -A; ag commit -q -m base; ag push -q origin master
LSA_A=$(ag rev-parse HEAD)
ag checkout -q -b claude/elsewhere-u1
echo work > "$LSA/repo/g"; ag add -A; ag commit -q -m work
LSA_B=$(ag rev-parse HEAD)
lsa_pred() {   # <file> <registered_utc> <a_ref> <b_ref>
    python3 - "$LSA/repo/docs/testing/predictions/$1" "$2" "$3" "$4" <<'PY'
import json, sys
p, reg, a, b = sys.argv[1:]
json.dump({"registered_utc": reg, "who": "lane.elsewhere", "issue": "34",
           "prediction": "laneshape fixture", "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": [],
           "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
}
lsa_pred live.json "$(date -u -d '1 minute ago' '+%FT%TZ')" "$LSA_A" "$LSA_B"
lsa_pred ancient.json "2020-01-01T00:00:00Z" "$LSA_A" "$LSA_B"
lsa_pred degenerate.json "$(date -u -d '1 minute ago' '+%FT%TZ')" "$LSA_B" "$LSA_B"
ag add -A; ag commit -q -m predictions; ag push -q origin claude/elsewhere-u1
mkdir -p "$LSA/goldens/Blend_surface"; : > "$LSA/goldens/Blend_surface/TestA.png"
cat > "$LS/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${LS_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        # The tick's one map call, and the per-branch fallback.
        [[ "$args" == *"--head claude/elsewhere-u1"* ]] && { echo 777; exit 0; }
        [[ "$args" == *"--head "* ]] && exit 0
        [[ "$args" == *"headRefName"* ]] && { printf 'claude/elsewhere-u1\t777\n'; exit 0; }
        exit 0 ;;
    "pr comment"|"issue comment") exit 0 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$LS/bin/gh"; export LS_GH_LOG="$LS/gh.log"; : > "$LS_GH_LOG"
mkdir -p "$LSA/work/arms" "$LSA/dispatch"/{queue,running,results,expect}
date -u -d '1 hour ago' '+%FT%TZ' > "$LSA/work/arms/since"
arms_ls() { ( export PATH="$LS/bin:$PATH" HAKUX_WORK="$LSA/work" HAKUX_REPO_DIR="$LSA/repo" \
                     DISPATCH_DIR="$LSA/dispatch" GOLDENS="$LSA/goldens" GH_REPO="example/hakux"
              bash "$HERE/arms.sh" "$@" 2>&1 ); }

out=$(arms_ls list)
check "a prediction on a non-lane/* branch with an open PR is collected at all" \
    grep -q "claude/elsewhere-u1:docs/testing/predictions/live.json" <<< "$out"
check "  and is WOULD QUEUE, not merely seen" \
    grep -q "WOULD QUEUE .*live.json.*suites=\[Blend surface\]" <<< "$out"
check "  and its b_ref counts as live: the branch is one of the tips now" \
    bash -c '! grep -q "live.json.*not an ancestor" <<< "$1"' _ "$out"
# THE WATERMARK STILL FENCES HISTORY. Collecting more branches must not re-run
# what has already been measured, and this is the leg that would catch it: the
# ancient registration is on the newly-visible branch and must be counted as
# history, not queued.
check "a pre-watermark registration on the newly-visible branch is still history" \
    grep -q -- "--- 1 prediction(s) older than the watermark" <<< "$out"
check "  so it is not queued" bash -c '! grep -q "WOULD QUEUE .*ancient.json" <<< "$1"' _ "$out"
check "the degenerate registration is refused, on the branch as anywhere else" \
    grep -q "would skip.*a_ref == b_ref" <<< "$out"

# WHERE THE VERDICT GOES. pr_for() used to map only `lane/*` to a PR, so this
# lane's refusals and verdicts fell through to its issue -- graceful, and the
# wrong place, because fold.sh and the board both read the PR. Run mode, with
# the pair cap at zero so nothing reaches request.sh: the skip still fires and
# still has to be told to somebody.
: > "$LS_GH_LOG"
( export ARMS_MAX_PAIRS_PER_TICK=0; arms_ls ) > "$LSA/run.log" 2>&1
check "a structural skip on a non-lane/* branch is told to its PR" \
    grep -q "^pr comment 777" "$LS_GH_LOG"
check "  and NOT to its issue instead" \
    bash -c '! grep -q "^issue comment" "$1"' _ "$LS_GH_LOG"
check "  while the live registration is still held by the pair cap, not queued" \
    grep -q "pair cap 0 reached" "$LSA/run.log"

# AND `state` STAYS READ-ONLY. Its header promises it reads $WORK/arms and
# nothing else. The first version of the PR map above asked gh in every mode,
# and on a host where gh answers nothing the WARNING landed on stdout ahead of
# the `STATE=` line that callers read with `sed -n 1p` -- 94's "verified and
# regressed are never both live" is the check that caught it. This is the same
# invariant stated from this side, so the collect step cannot quietly grow a
# network call back into a mode that must not make one.
: > "$LS_GH_LOG"
out=$(arms_ls state lane/nobody)
check "arms.sh state asks gh nothing" [ ! -s "$LS_GH_LOG" ]
check "  and its first line is the STATE= line, unprefixed by any warning" \
    grep -q '^STATE=' <<< "$(head -1 <<< "$out")"

# ----------------------------------------------------------------- fleet.py
# The board's only sensor. A directory holding the three modules plus two toml
# files IS a board when HAKUX_BOARD_REF is empty -- the pattern 93's fixture
# established -- so the real script runs against it unmodified.
LSF="$LS/fleet"; mkdir -p "$LSF" "$LS/fleetdisp/fleet"
cp "$TESTING/fleet.py" "$TESTING/board_files.py" "$LSF/"
cp "$LS/territory.toml" "$LSF/territory.toml"
printf '[issue]\n' > "$LSF/nv2a_issues.toml"
cat > "$LS/bin2-gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$1 $2" in
    "pr list") printf '[{"number":777,"headRefName":"claude/elsewhere-u1","isDraft":true,"labels":[],"updatedAt":"2026-09-19T00:00:00Z","title":"the remote lane"}]\n'; exit 0 ;;
    "issue list") echo '[]'; exit 0 ;;
    *) exit 0 ;;
esac
EOF
mkdir -p "$LS/bin2"; cp "$LS/bin2-gh" "$LS/bin2/gh"
cat > "$LS/bin2/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in *list-units*) exit 0 ;; *) exit 0 ;; esac
EOF
chmod +x "$LS/bin2/"*
flt_ls=$( ( export PATH="$LS/bin2:$PATH"; cd "$LSF" && HAKUX_BOARD_REF= DISPATCH_DIR="$LS/fleetdisp" \
            python3 "$LSF/fleet.py" ) 2>&1 )
check "fleet.py counts an open PR on a branch a territory row names" \
    grep -q "REMOTE LANES (2)" <<< "$flt_ls"
check "  naming the branch and the PR, so the report says where the lane is" \
    grep -q "elsewhere .*claude/elsewhere-u1 .*PR #777 draft" <<< "$flt_ls"
check "  and a remote row with no PR says so rather than being dropped" \
    grep -q "prefixed .*lane/prefixed .*no open PR" <<< "$flt_ls"
# THE DIRECTION THAT COSTS SOMETHING. This section is the evidence a reader
# uses to retire a claim; retiring lane.remote's row would free eleven files a
# live session pushes to hourly.
check "a remote lane is NOT reported as a claim with no running agent" \
    bash -c '! grep -qE "^  (elsewhere|prefixed) +holds" <<< "$1"' _ "$flt_ls"
check "  while a local lane with no unit still is -- the target is narrowed, not widened" \
    grep -qE "^  alpha +holds" <<< "$flt_ls"

# --------------------------------------------------------------- handback.sh
# `needs-rebase` on a remote lane's PR. The old `*)` arm told it "whoever owns
# this branch merges origin/master into it by hand" -- true of a person's
# branch, wrong about a lane. Nothing local should act; saying WHY is the fix.
LSH="$LS/handback"; mkdir -p "$LSH/bin"
cat > "$LSH/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$1 $2" in
    "pr list") [ -f "$LSH/prs.tsv" ] && cat "$LSH/prs.tsv"; exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$LSH/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$LSH/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in *is-active*) exit 1 ;; *) exit 0 ;; esac
EOF
cat > "$LSH/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "$LSH/started.log"; exit 0
EOF
chmod +x "$LSH/bin/"*
export LSH; : > "$LSH/comments.log"; : > "$LSH/started.log"
printf '301\tclaude/elsewhere-u1\t%s\tneeds-rebase\n' aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa > "$LSH/prs.tsv"
( export PATH="$LSH/bin:$PATH" HAKUX_TERRITORY="$LS/territory.toml"
  bash "$HERE/handback.sh" ) > "$LSH/tick.log" 2>&1
check "a remote lane's handed-back PR starts nothing locally" \
    bash -c '[ ! -s "$1/started.log" ]' _ "$LSH"
check "  and is told its own routine picks it up, by lane name" \
    grep -q "lane.elsewhere.*runs somewhere this host cannot see" "$LSH/comments.log"
check "  and is NOT told a person has to merge it by hand" \
    bash -c '! grep -q "merges .origin/master. into it by hand" "$1/comments.log"' _ "$LSH"
check "  while still naming the work: merge, resolve, push, re-apply fold-ready" \
    grep -q "re-apply .fold-ready" "$LSH/comments.log"
# A remote lane whose branch is someday named lane/* must not fall into the
# local arm. That is the second agent on one branch, arriving by the front door.
: > "$LSH/comments.log"; : > "$LSH/started.log"
printf '302\tlane/prefixed\t%s\tneeds-rebase\n' bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb > "$LSH/prs.tsv"
mkdir -p "$HAKUX_WORK/wt/prefixed"; echo brief > "$HAKUX_WORK/briefs/prefixed.md"
( export PATH="$LSH/bin:$PATH" HAKUX_TERRITORY="$LS/territory.toml"
  bash "$HERE/handback.sh" ) >> "$LSH/tick.log" 2>&1
check "a remote lane named lane/* is still not resumed locally" \
    bash -c '[ ! -s "$1/started.log" ]' _ "$LSH"
check "  even though it has a worktree and a brief on this host" \
    [ -d "$HAKUX_WORK/wt/prefixed" ]

# ----------------------------------------------------------------- lane.sh
# THE SINGLE MOST EXPENSIVE THING THAT COULD GO WRONG. `lane.sh resume
# elsewhere` would have made $WORK/wt/elsewhere, started a headless session and
# pushed to the branch a cloud container pushes to hourly: two agents, one
# branch, no lock. It is one `case` away and it is checked here as behaviour.
lane_ls() { ( export PATH="$LSH/bin:$PATH" HAKUX_WORK="$LS/work" HAKUX_REPO_DIR="$LSA/repo" \
                     HAKUX_TERRITORY="${2:-$LS/territory.toml}"
              bash "$TESTING/lane.sh" $1 2>&1 ); }
out=$(lane_ls "resume elsewhere"); rc=$?
# 76, not "non-zero". A lane with no worktree already exits 3, so `-ne 0` is
# green against a build with no guard at all -- an exit code is a coarse
# discriminator, and this one had two ways to be non-zero for opposite reasons.
check "lane.sh resume REFUSES a remote lane, and refuses it as one" [ "$rc" -eq 76 ]
check "  naming the branch it would have collided on" grep -q "claude/elsewhere-u1" <<< "$out"
check "  and naming the routine as the way to wake it" grep -qi "routine" <<< "$out"
check "  and it creates no worktree on the way out" [ ! -e "$LS/work/wt/elsewhere" ]
out=$(lane_ls "start prefixed $LS/territory.toml")
check "lane.sh start refuses one too -- resume is not the only door" \
    grep -q "REFUSED: lane.prefixed is marked" <<< "$out"
# NARROW. A local lane must be entirely unaffected: this one gets as far as the
# missing worktree, which is the answer it gave before any of this.
out=$(lane_ls "resume alpha")
check "a local lane is not refused by the remote guard" \
    bash -c '! grep -q "marked .remote." <<< "$1"' _ "$out"
check "  it reaches its own check instead" grep -q "no worktree at" <<< "$out"
# AND A BOARD IT CANNOT READ IS A REFUSAL. "I do not know whether another agent
# holds this branch" must not be answered by starting one.
out=$(lane_ls "resume alpha" "$LS/nosuch.toml")
check "lane.sh refuses when territory.toml cannot be read at all" \
    grep -q "could not be read" <<< "$out"
# AND SO IS A MISSING READER. There is no `set -e` in lane.sh, so a bare `.` of
# an absent remote-lane.sh would leave refuse_if_remote undefined,
# command-not-found would not stop the script, and the one gate above would run
# to completion having checked nothing. A jobs/ directory with models.env and
# nothing else is that mutant.
mkdir -p "$LS/nohelper/jobs"
cp "$TESTING/lane.sh" "$LS/nohelper/lane.sh"; cp "$HERE/models.env" "$LS/nohelper/jobs/"
out=$( ( export HAKUX_WORK="$LS/work"; bash "$LS/nohelper/lane.sh" resume alpha ) 2>&1 )
check "lane.sh refuses outright when remote-lane.sh is not there to load" \
    grep -q "could not load" <<< "$out"

# ----------------------------------------------------------------- fold.sh
# The exemption, and the proof it is an exemption: the target is narrowed and
# never widened. A real bare origin, because no shim can refuse a push.
LSP="$LS/prune"; mkdir -p "$LSP"
pg_ls() { git -C "$LSP/repo" -c user.email=s@t -c user.name=s "$@"; }
git -c init.defaultBranch=master init -q --bare "$LSP/origin.git"
git -c init.defaultBranch=master clone -q "$LSP/origin.git" "$LSP/repo" 2>/dev/null
echo base > "$LSP/repo/f"; pg_ls add -A; pg_ls commit -q -m base; pg_ls push -q origin master
# Both are fully merged, so the ancestry test PASSES on both and only the
# territory row separates them. lane/ordinary is the must-not-move leg: if the
# exemption widened, this one would survive too and the check would not notice.
for b in prefixed ordinary; do
    pg_ls checkout -q -b "lane/$b" master; echo "$b" > "$LSP/repo/$b"
    pg_ls add -A; pg_ls commit -q -m "$b"; pg_ls push -q "origin" "lane/$b"
    pg_ls checkout -q master; pg_ls merge -q --no-ff --no-edit "lane/$b"
done
pg_ls push -q origin master
fold_ls() { ( export HAKUX_REPO_DIR="$LSP/repo" HAKUX_TERRITORY="${2:-$LS/territory.toml}"
              bash "$HERE/fold.sh" prune $1 2>&1 ); }
out=$(fold_ls --apply)
check "fold.sh never prunes a remote lane's branch, even named lane/*" \
    git -C "$LSP/origin.git" rev-parse -q --verify refs/heads/lane/prefixed
check "  and says whose it is, so the refusal is diagnosable" \
    grep -q "NOT pruning 'lane/prefixed'.*lane.prefixed" <<< "$out"
check "  while an ordinary folded lane branch is still deleted" \
    bash -c '! git -C "$1/origin.git" rev-parse -q --verify refs/heads/lane/ordinary >/dev/null' _ "$LSP"
# An un-pruned ref costs a few bytes. "I could not check" is not "safe to
# delete", and this is the direction that has to be wrong for it to matter.
pg_ls push -q origin master:refs/heads/lane/second
out=$(fold_ls --apply "$LS/nosuch.toml")
check "fold.sh keeps every ref when territory.toml cannot be read" \
    git -C "$LSP/origin.git" rev-parse -q --verify refs/heads/lane/second
check "  and says that is why" grep -q "could not be read" <<< "$out"

# --------------------------------------------------- against the real board
# Every check above runs on a fixture. This one runs the default path -- no
# HAKUX_TERRITORY, board_files.py, origin/board or the working tree -- because
# a reader that only ever sees its own fixture has been tested against nothing.
# It asserts the read SUCCEEDS and parses; which lanes are marked is the
# board's business and changes without this file.
check "remote-lane.sh reads the live board without HAKUX_TERRITORY set" \
    bash -c 'cd "$2" && . "$1/remote-lane.sh" && remote_readable' _ "$HERE" "$TESTING"
