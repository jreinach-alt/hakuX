# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# jobs/pr-sweep.sh: the five classes of open PR that no actor reaches.
#
# 76, after the arms fragments (10..60) and before the label ones, because it
# shares nothing with either: every fixture below lives under $PS and the
# sweep is run against a SCRATCH JOBS TREE, not $HERE.
#
# WHY A SCRATCH JOBS TREE AND NOT THE REAL DIRECTORY. pr-sweep.sh's one repair
# is `cloud.sh finish`, and the real cloud.sh removes the lane's territory row
# by PUSHING to origin/board. A selftest that ran it would push to a live
# branch. So $PS/jobs is a directory of symlinks to the real jobs, with
# cloud.sh, handback.sh, arms.sh and fold.sh replaced by recording fakes --
# swapped inside a symlink tree, never at the real path, so a fragment that
# dies half way cannot leave the repository holding a stub.
#
# It also makes the fold.sh ownership probe testable in both directions: the
# stale-red class is lane.stalecheck's (PR #169), and pr-sweep reports whether
# that owner is PRESENT in the trunk it ran from. On master today it is not.
#
# THE THING BEING CHECKED IS THAT A BROKEN FIXTURE TRIPS IT. A sweep that says
# "nothing stuck" against a PR that is visibly stuck is the exact failure it
# exists to catch, so every class below is run twice: once with the defect
# present (it must be named) and once with the one fact that makes it not a
# defect restored (it must go silent).

echo "== pr-sweep.sh: the PRs no actor can reach"
PS="$T/pr-sweep"; mkdir -p "$PS/bin" "$PS/jobs"
for f in "$HERE"/*.sh "$HERE"/*.py "$HERE"/*.env "$HERE"/allowed-tools.*; do
    [ -e "$f" ] && ln -sf "$f" "$PS/jobs/$(basename "$f")"
done
ln -sfn "$HERE/roles" "$PS/jobs/roles" 2>/dev/null || true
# THE SCRATCH TREE IS A docs/testing, NOT JUST A jobs/. pr-sweep.sh sources
# remote-lane.sh, which reads territory.toml through board_files.py from
# `dirname $J` -- so without these two the map read comes back `unreadable`
# and the sweep refuses every tick below for a fault the fixture invented.
# HAKUX_BOARD_REF= in ps() is what makes this file the board rather than a
# fold-lagged fallback; see 78-sweep-remote.sh for the checks on that
# distinction, which are that fragment's whole subject.
ln -sf "$(dirname "$HERE")/board_files.py" "$PS/board_files.py"
printf 'wave = 1\nupdated_utc = "2026-09-19T00:00:00Z"\n' > "$PS/territory.toml"

# `rm -f` BEFORE EVERY WRITE INTO THE SCRATCH TREE, AND IT IS NOT A TIDINESS
# HABIT. `cat > $PS/jobs/cloud.sh` FOLLOWS the symlink and writes the stub into
# docs/testing/jobs/cloud.sh -- the real file, in the real worktree. That is
# not hypothetical: the first run of this fragment truncated cloud.sh, fold.sh,
# handback.sh and arms.sh to three lines each, and the only reason it was
# visible at all is that 189 unrelated checks went red in the same run. A
# falsification fixture must swap inside the symlink tree, never at the path
# the tree points to. ps_stub() is the only writer here, and it unlinks first.
ps_stub() { rm -f "$PS/jobs/$1"; cat > "$PS/jobs/$1"; chmod +x "$PS/jobs/$1"; }

# ------------------------------------------------------------------- the fakes
ps_stub cloud.sh <<'EOF'
#!/usr/bin/env bash
# Records the tail pr-sweep ran, and nothing else. The real one pushes to
# origin/board; see this fragment's header.
echo "cloud.sh $*" >> "${PS_LOG:?}"
[ -f "$PS_DIR/cloud-fails" ] && exit 3
exit 0
EOF
ps_stub handback.sh <<'EOF'
#!/usr/bin/env bash
# `handback.sh list` and nothing else; $PS_DIR/handback.list is what it says.
[ "${1:-}" = list ] || exit 0
cat "$PS_DIR/handback.list" 2>/dev/null
exit 0
EOF
ps_stub arms.sh <<'EOF'
#!/usr/bin/env bash
# `arms.sh state <branch>`: the label the verdicts on disk add up to.
[ "${1:-}" = state ] || exit 0
cat "$PS_DIR/arms.state" 2>/dev/null
exit 0
EOF

# THE GUARD ON THE PARAGRAPH ABOVE. Every stub must be a regular file in the
# scratch tree; one that is still a symlink is one whose next write lands in
# the repository. Checked here rather than trusted, because the failure is
# silent at the moment it happens and only shows up as unrelated red.
ps_not_link() { [ -f "$PS/jobs/$1" ] && [ ! -L "$PS/jobs/$1" ]; }
check "the cloud.sh stub is a real file, not a symlink into the repo"    ps_not_link cloud.sh
check "the handback.sh stub is a real file, not a symlink into the repo" ps_not_link handback.sh
check "the arms.sh stub is a real file, not a symlink into the repo"     ps_not_link arms.sh
check "and the real cloud.sh is still the real cloud.sh"  grep -q "the audit outlet" "$HERE/cloud.sh"
check "and the real arms.sh is still the real arms.sh"    grep -q "WHY IT IS A SCRIPT" "$HERE/arms.sh"

cat > "$PS/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${PS_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list") cat "$PS_DIR/prs.json" 2>/dev/null || echo "[]"; exit 0 ;;
    "pr view")
        # pr-sweep asks for `comments` and --jq's out the last [job.cloud]
        # claim body. The shim answers with what that jq would have printed.
        [[ "$args" == *comments* ]] && { cat "$PS_DIR/claim.body" 2>/dev/null; exit 0; }
        exit 0 ;;
    "pr comment")
        b=0; for a in "$@"; do [ "$b" = 1 ] && { printf '%s\n--- end comment\n' "$a" >> "$PS_DIR/comments.log"; b=0; }; [ "$a" = --body ] && b=1; done
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$PS/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*) cat "$PS_DIR/active" 2>/dev/null; exit 0 ;;
    *is-active*)  cat "$PS_DIR/board-timer" 2>/dev/null || echo active; exit 0 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$PS/bin/"*
export PS_DIR="$PS" PS_LOG="$PS/calls.log"

# The sweep's own state lives beside the fake work dir, not in $HAKUX_WORK's
# real one, so `said` markers from one check cannot silence the next.
PS_WORK="$PS/work"
ps_reset() { rm -rf "$PS_WORK"; mkdir -p "$PS_WORK/logs/board"; : > "$PS_LOG"; : > "$PS/comments.log"
             : > "$PS/active"; : > "$PS/handback.list"; : > "$PS/arms.state"; : > "$PS/claim.body"
             echo active > "$PS/board-timer"; touch "$PS_WORK/logs/board/tick.log"; }
ps() { ( export PATH="$PS/bin:$PATH" HAKUX_WORK="$PS_WORK" HAKUX_BOARD_REF=
          bash "$PS/jobs/pr-sweep.sh" "$@" 2>&1 ); }
ps_said()   { grep -qF -- "$1" "$PS/comments.log"; }
ps_unsaid() { ! grep -qF -- "$1" "$PS/comments.log"; }
# ANCHORED ON THE CALL, NOT ON THE WORDS. The gh shim logs every argument it
# was handed, and one of pr-sweep's own comment bodies tells a person to run
# `cloud.sh finish <kind> <n>` by hand -- so an unanchored grep for that string
# matches the PROSE and reports a repair that never happened. The fake
# cloud.sh writes its line at the start of a line; nothing else does.
ps_ran()    { grep -q "^cloud.sh $1" "$PS_LOG"; }
ps_no_tail(){ ! grep -q "^cloud.sh finish" "$PS_LOG"; }
ps_in()     { grep -q -- "$1" <<< "$got"; }
ps_notin()  { ! grep -q -- "$1" <<< "$got"; }
ps_row()    { grep -q "^$1$(printf '\t')$2$(printf '\t')" <<< "$got"; }
ps_norow()  { ! grep -q "^$1$(printf '\t')$2$(printf '\t')" <<< "$got"; }
ps_report() { grep -qF -- "$1" "$PS_WORK/status/pr-sweep.md"; }
# Negatives run as FUNCTIONS and never as `bash -c '! grep ... "$var"'`: a
# child shell sees only exported variables, so such a check is green against
# anything the moment the variable it reads is fragment-local.

# The trunk head's commit time, as pr-sweep reads it from git.
#
# EVERY CHECK TIMESTAMP BELOW IS AN OFFSET FROM THIS, NOT AN AGE FROM `now`,
# and that is not a style preference. The first version of this fragment
# placed each check `TRUNK_AGO + 600` seconds in the past, which is 600s
# before the trunk head ONLY at the instant TRUNK_AGO was computed -- and a
# dozen `ps` runs, each with a real `git fetch` in it, sit between that
# instant and the stale-red block. The fixture drifted past the trunk head and
# the class stopped being stale, so the whole class went quiet and every
# NEGATIVE check on it passed for free. Offsets from the trunk head cannot
# drift: the quantity they are compared against is the one they are built from.
TRUNK_CT=$(git -C "$REPO" log -1 --format=%ct refs/remotes/origin/master 2>/dev/null \
           || git -C "$REPO" log -1 --format=%ct HEAD)

# One PR, as `gh pr list --json ...` emits it. <num> <branch> <draft>
# <mergeable> <labels csv> <quiet secs> [<name:conclusion:offset> ...] where
# the offset is SIGNED SECONDS RELATIVE TO THE TRUNK HEAD (-600 = ten minutes
# before it, so stale; +600 = after it, so live), or `none` for a check entry
# carrying no timestamp at all.
ps_pr()     { ps_pr_write new "$@"; }
ps_pr_add() { ps_pr_write add "$@"; }
ps_pr_write() {
    python3 - "$PS/prs.json" "$TRUNK_CT" "$@" <<'PY'
import datetime, json, os, sys
out, trunk, how, num, branch, draft, mergeable, labels, quiet = sys.argv[1:10]
trunk = int(trunk)
now = datetime.datetime.now(datetime.timezone.utc)
def at(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rollup = []
for spec in sys.argv[10:]:
    name, concl, off = spec.split(":")
    rollup.append({"name": name, "conclusion": concl,
                   "startedAt": None if off == "none" else at(trunk + int(off))})
rows = []
if how == "add" and os.path.exists(out):
    rows = json.load(open(out))
rows.append({"number": int(num), "headRefName": branch, "headRefOid": "deadbeef" + num,
             "isDraft": draft == "true", "mergeable": mergeable,
             "labels": [{"name": l} for l in labels.split(",") if l],
             "updatedAt": at(now.timestamp() - int(quiet)), "statusCheckRollup": rollup,
             "title": "a PR the fixture made"})
json.dump(rows, open(out, "w"))
PY
}
# The positive control every negative in class 4 is measured against: a PR
# that IS stale, in the same fixture, so a classifier that has stopped
# detecting staleness altogether fails instead of passing every negative.
ps_stale_control() { ps_pr_add 214 lane/reallystale false MERGEABLE fold-ready 200000 "old:FAILURE:-600"; }

# ==================================================================== class 1
# AN ORPHANED `claimed:cloud`. #141 and #148 sat in it for 6.5 hours on
# 2026-09-19: cloud.sh's pickup EXCLUDES a PR carrying the label and
# `cloud.sh finish` is the only thing that removes it, so a session whose tail
# died made its PR unclaimable by anything, permanently and silently.
ps_reset
ps_pr 201 lane/orphan false MERGEABLE claimed:cloud,needs-audit-1 9000
echo "[job.cloud] claimed for audit1 (unit hakux-lane-cloud-audit1-201, model x, attempt 1 of 4)." > "$PS/claim.body"
got=$(ps list)
check "list names the orphaned claim"            ps_in "would repair #201"
check "list names the tail it would run"         ps_in "cloud.sh finish audit1 201"
check "list runs nothing"                        ps_no_tail

ps_reset
ps_pr 201 lane/orphan false MERGEABLE claimed:cloud,needs-audit-1 9000
echo "[job.cloud] claimed for audit1 (unit hakux-lane-cloud-audit1-201, model x, attempt 1 of 4)." > "$PS/claim.body"
ps >/dev/null
check "an orphaned claim runs the tail that did not" ps_ran "finish audit1 201"
check "and the kind comes from the claim comment's unit name" ps_ran "finish audit1 201"
check "the repair is said on the PR"             ps_said "[job.pr-sweep] this PR carried \`claimed:cloud\`"
check "and it says why nothing else could reach it" ps_said "pickup excludes a PR with that label"
check "the report page records the repair"       ps_report "**repaired**"

# IDEMPOTENT: a second pass over the same state is a no-op, not a second
# comment. These run unattended every three hours.
: > "$PS/comments.log"
ps >/dev/null
check "a second pass says nothing again"         ps_unsaid "[job.pr-sweep] this PR carried"

# THE FIXTURE MADE HEALTHY: the unit is running, so there is no orphan.
ps_reset
ps_pr 201 lane/orphan false MERGEABLE claimed:cloud,needs-audit-1 9000
echo "hakux-lane-cloud-audit1-201.service" > "$PS/active"
got=$(ps list)
check "a claim whose unit IS running is not touched" ps_notin "would repair #201"

# THE GRACE PERIOD. cloud.sh labels and comments BEFORE systemd-run, so for a
# moment a live claim has no unit; a sweep without this window would "repair" a
# session that is starting.
ps_reset
ps_pr 201 lane/orphan false MERGEABLE claimed:cloud 60
got=$(ps list)
check "a claim made a minute ago is inside the start grace" ps_notin "would repair #201"

# NOT A GUESS. `finish` clears a different state label per kind, so with no
# readable claim comment there is no kind and no repair -- and it says so on
# the PR rather than defaulting to the earliest state.
ps_reset
ps_pr 201 lane/orphan false MERGEABLE claimed:cloud 9000
ps >/dev/null
check "an unreadable claim comment repairs nothing" ps_no_tail
check "and the PR is told the kind could not be derived" ps_said "could not repair it"

# ==================================================================== class 2
# A DRAFT WHOSE LANE HAS EXITED. handback.sh owns this outright, down to a
# strand budget and a once-per-head key, so the sweep's only job is to notice
# when that owner is silent about one.
ps_reset
ps_pr 202 lane/strandy true UNKNOWN "" 9000
echo "#202 lane/strandy: draft-strand-quiet WOULD RESUME lane.strandy" > "$PS/handback.list"
ps >/dev/null
check "a draft handback already sees is left alone" ps_unsaid "[job.pr-sweep] this PR is a draft"

ps_reset
ps_pr 202 lane/strandy true UNKNOWN "" 9000
ps >/dev/null
check "a draft handback says nothing about is reported" ps_said "[job.pr-sweep] this PR is a draft"
check "and the sweep does not mark it ready"        ps_said "Nothing here marks a PR ready"

# A BARE NUMBER IS NOT A CLAIM OF OWNERSHIP. handback's rows start with the
# number; the same digits inside a sentence about another PR must not silence
# a real finding.
ps_reset
ps_pr 202 lane/strandy true UNKNOWN "" 9000
echo "#999 lane/other: superseded by #202 and already actioned" > "$PS/handback.list"
ps >/dev/null
check "a number quoted mid-sentence does not count as handback owning it" ps_said "[job.pr-sweep] this PR is a draft"

# A running lane's draft is a lane at work, which is what draft MEANS.
ps_reset
ps_pr 202 lane/strandy true UNKNOWN "" 9000
echo "hakux-lane-strandy.service" > "$PS/active"
got=$(ps list)
check "a draft whose lane IS running is not a finding" ps_notin "draft-strand"

# ==================================================================== class 3
# READY, NO STATE LABEL. board.sh is the only actor that may set the first
# one, so the useful half of the report is whether that actor is alive.
ps_reset
ps_pr 203 lane/nolabel false MERGEABLE harness 200000
ps >/dev/null
check "a long-unlabelled ready PR is reported"   ps_said "[job.pr-sweep] this PR is out of draft and carries none of"
check "and the report names the board's health"  ps_said "Board health: **healthy"

# A HEALTHY BOARD AND A RECENT PR IS NOT A FINDING: it is a tick's worth of
# work already queued, and a comment every three hours would be a nag.
ps_reset
ps_pr 203 lane/nolabel false MERGEABLE harness 600
ps >/dev/null
check "a freshly-ready PR under a healthy board gets no comment" ps_unsaid "[job.pr-sweep] this PR is out of draft"

# A DEAD BOARD IS THE CAUSE OF EVERY SUCH PR AT ONCE, so it is said
# immediately and it is said in the comment.
ps_reset
ps_pr 203 lane/nolabel false MERGEABLE harness 600
echo inactive > "$PS/board-timer"
ps >/dev/null
check "a dead board makes it a finding at once"  ps_said "[job.pr-sweep] this PR is out of draft"
check "and the comment names the timer to enable" ps_said "systemctl --user enable --now hakux-board.timer"

# A PR already in the pipeline is not waiting on the board.
ps_reset
ps_pr 203 lane/nolabel false MERGEABLE harness,fold-ready 200000
got=$(ps list)
check "a labelled ready PR is not in class 3"    ps_notin "no-state-label"

# THE STATE SET MUST NOT DRIFT FROM board.sh's. There is no way to source that
# function -- board.sh runs a whole tick when sourced -- so the list is copied,
# and a copy nothing compares is a copy that drifts. Compared as SETS: the
# order differs between the two files and order is not what matters.
ps_states=$(sed -n 's/^STATE_LABELS=.\(.*\).$/\1/p' "$HERE/pr-sweep.sh" | tr ' ' '\n' | sort | tr -d '"' | paste -sd,)
bd_states=$(sed -n '/^STATE = {/,/}/p' "$HERE/board.sh" | tr -d '\n' | sed 's/.*STATE = {//; s/}.*//' \
            | tr ',' '\n' | tr -d ' "' | grep . | sort | paste -sd,)
check "pr-sweep's state-label set is board.sh's, character for character" \
      test "$ps_states" = "$bd_states"
[ "$ps_states" = "$bd_states" ] || echo "     pr-sweep: $ps_states"$'\n'"     board.sh: $bd_states"

# ==================================================================== class 4
# A STALE RED. fold-ready, MERGEABLE, and every failing check started before
# the current trunk head was committed -- the red is about a base that moved,
# and GitHub never re-runs a PR's checks when its base does.
#
# REPORTED, NEVER RELABELLED: lane.stalecheck (PR #169) owns this class in
# fold.sh, and two actors moving one PR's labels from two timers is worse than
# the state either fixes. So what is checked here is that the sweep names the
# owner AND says truthfully whether it is present.
ps_reset
printf '#!/usr/bin/env bash\n# this one has no such function\n' | ps_stub fold.sh
check "the fold.sh stub is a real file, not a symlink into the repo" ps_not_link fold.sh
check "and the real fold.sh is untouched"  grep -q "one fold per tick" "$HERE/fold.sh"
ps_pr 204 lane/stale false MERGEABLE fold-ready 200000 "selftest:FAILURE:-600"
ps >/dev/null
check "a stale red is found"                     ps_said "started **before** the current"
check "and the comment names fold.sh as its owner" ps_said "lane.stalecheck, PR #169"
check "and says the owner is ABSENT from this trunk" ps_said "Present in the trunk this sweep ran from: **no**"
check "and it relabels nothing"                  ps_unsaid "fold-ready removed"

ps_reset
printf '#!/usr/bin/env bash\nstale_red() { :; }\n' | ps_stub fold.sh
ps_pr 204 lane/stale false MERGEABLE fold-ready 600 "selftest:FAILURE:-600"
ps >/dev/null
check "with the owner present and the PR fresh, the sweep stays out of its way" \
      ps_unsaid "started **before** the current"

# CONSERVATIVE IN EVERY DIRECTION, the same three ways fold.sh is. "Cannot
# tell" is not "it is stale", and a wrong STALE verdict tells a lane its red
# is somebody else's problem.
#
# EVERY NEGATIVE BELOW CARRIES #214, WHICH IS STALE, IN THE SAME FIXTURE. A
# bare "#204 is not reported" is satisfied by a classifier that reports
# nothing at all -- which is precisely how these four checks passed while the
# class was silently broken by the drifting fixture above. The control makes
# the blind answer fail.
ps_reset
ps_pr 204 lane/stale false MERGEABLE fold-ready 200000 "old:FAILURE:-600" "live:FAILURE:+600"
ps_stale_control
got=$(ps list)
check "a stale failure ALONGSIDE a live one is a live red" ps_norow stale-red 204
check "  (control: the plainly stale PR in the same fixture IS reported)" ps_row stale-red 214

ps_reset
ps_pr 204 lane/stale false MERGEABLE fold-ready 200000 "nostamp:FAILURE:none"
ps_stale_control
got=$(ps list)
check "a failing check with no readable timestamp is live, not stale" ps_norow stale-red 204
check "  (control)"                                                   ps_row stale-red 214

ps_reset
ps_pr 204 lane/stale false MERGEABLE fold-ready 200000 "selftest:SUCCESS:-600"
ps_stale_control
got=$(ps list)
check "a rollup with no failing check is never stale" ps_norow stale-red 204
check "  (control)"                                   ps_row stale-red 214

ps_reset
ps_pr 204 lane/stale false CONFLICTING fold-ready 200000 "selftest:FAILURE:-600"
ps_stale_control
got=$(ps list)
check "a CONFLICTING PR is the rebase path's, not this one's" ps_norow stale-red 204
check "  (control)"                                           ps_row stale-red 214

ps_reset
ps_pr 204 lane/stale false MERGEABLE harness 200000 "selftest:FAILURE:-600"
ps_stale_control
got=$(ps list)
check "a PR that is not fold-ready is not in this class" ps_norow stale-red 204
check "  (control)"                                      ps_row stale-red 214

# NO TRUNK TIME, NO CLASS. A stale verdict computed without the one timestamp
# it is a comparison against would be a guess, and the report says the class
# did not run rather than printing an empty list that reads as "none".
ps_reset
ps_pr 204 lane/stale false MERGEABLE fold-ready 200000 "selftest:FAILURE:-600"
( export PATH="$PS/bin:$PATH" HAKUX_WORK="$PS_WORK" HAKUX_REPO_DIR="$PS/not-a-repo" HAKUX_TIP=nope \
         HAKUX_BOARD_REF=
  bash "$PS/jobs/pr-sweep.sh" >/dev/null 2>&1 )
check "with no readable trunk head the stale class is disabled, and says so" \
      ps_report "did not run this tick"

# ==================================================================== class 5
# `regressed`. The label is a function of EVERY judged verdict on the branch,
# so arms.sh is the only thing that can say whether the FAIL still stands --
# and `regression-accepted:` is the owner's to grant, so nothing here writes a
# label in either direction.
ps_reset
ps_pr 205 lane/regr false MERGEABLE regressed,harness 9000
echo "STATE=regressed" > "$PS/arms.state"
ps >/dev/null
check "a standing FAIL is reported as standing"  ps_said "still recomputes \`regressed\`"
check "and the sweep grants no regression-accepted" ps_said "grants no \`regression-accepted:\` label"

ps_reset
ps_pr 205 lane/regr false MERGEABLE regressed,harness 9000
echo "STATE=verified" > "$PS/arms.state"
ps >/dev/null
check "a label the verdicts no longer support is reported as a disagreement" \
      ps_said "the label and the evidence disagree"
check "and the sweep still does not move the label" ps_said "The sweep does not move it"

ps_reset
ps_pr 205 lane/regr false MERGEABLE harness 9000
echo "STATE=regressed" > "$PS/arms.state"
got=$(ps list)
check "an unlabelled PR is not in class 5"       ps_notin "regressed"

# ====================================================== the quiet fixture
# THE CONTROL. Nothing stuck must produce nothing said. Without this, every
# check above is satisfied by a sweep that comments on everything.
ps_reset
ps_pr 206 lane/fine false MERGEABLE fold-ready 9000 "selftest:SUCCESS:+600"
got=$(ps list)
check "a healthy PR produces no finding"         ps_in "nothing stuck"
ps >/dev/null
check "and no comment"                           test ! -s "$PS/comments.log"

# ====================================================== failing quiet
# A gh that cannot answer must make this sweep SILENT, not make every PR read
# as stuck. It is the same choice board.sh's positive gate makes, and for the
# same reason: a blind sensor that reports alarm is worse than one that reports
# nothing.
ps_reset
ps_pr 201 lane/orphan false MERGEABLE claimed:cloud 9000
cat > "$PS/bin/gh" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$PS/bin/gh"
got=$(ps)
check "no usable gh makes the sweep blind, not loud" ps_in "this tick is blind"
check "and it repairs nothing while blind"       ps_no_tail
