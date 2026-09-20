#!/usr/bin/env bash
#
# The audit outlet: one unit of no-device work, dispatched on the lane path.
#
#   cloud.sh                     claim one unit and start a session on it
#   cloud.sh list                what it would claim, and the cap it is under
#   cloud.sh finish <kind> <num> the unit's tail: drop the claim, clear the
#                                state label the session has moved past
#
# ONE DISPATCH PATH, NOT TWO (measured 2026-09-19). Pass 1 on PR #102 worked:
# an audit file, a PR review reading 0 HIGH / 2 MEDIUM / 5 LOW, and the label
# `needs-remediation`. Nothing could ever pick that up.
#
#   - This script filtered the remediate pickup on the head-branch prefix
#     `lane/cloud-`. #102's head is `lane/blitsafe` -- a LOCAL lane. Invisible.
#   - roles/board.md carried the other half of the rule, but the board only
#     starts a tick when fleet.py or the coverage gate says FAIL, and an
#     unremediated audit is neither. So that rule never ran either.
#   - hakux-cloud.timer was disabled by the owner at 06:10Z, so even the
#     prefix-matching path no longer fires on a timer.
#
# `needs-audit-1` and `needs-remediation` were terminal states: a PR that
# reached one stopped there, silently, forever. Producing findings and handing
# them to nobody is worse than not auditing.
#
# The fix is that there is no second mechanism. An audit is a model session in
# a worktree -- which is what a lane is -- so it is dispatched by what
# dispatches lanes (the board's timer, jobs/board.sh, script-first and before
# its own gates), under the cap that caps lanes, in a unit named
# `hakux-lane-*` so that lane.sh's own count sees it. Two mechanisms that
# differ only in which labels they read is the reason one of them could be
# switched off without anyone noticing the other never covered its work.
#
# WHY THIS RUNS ON THE HOST AND NOT IN THE CLOUD (measured 2026-09-19). A
# Routine created from a session fires a fresh cloud session that has NO
# repository checkout, NO GitHub tooling, and stalls forever on the first
# permission prompt nobody is there to answer; a session created directly
# with the repo attached wrote its file and was then refused the commit and
# the push by the auto-mode classifier. Four diagnostic sessions, zero
# branches pushed. Until a Routine can be created with the repo, a GitHub
# connector and a non-prompting permission mode (the claude.ai Routines UI
# can do that; this tool cannot), the cloud role runs here. The role file
# (roles/cloud.md) is the same either way, so moving it later is a change of
# launcher, not of contract.
#
# WHAT IT CLAIMS, in order: a needs-remediation PR (any open PR, whoever
# opened it), a needs-audit-2 PR, a needs-audit-1 PR, an issue labelled
# `cloud` with no lane: label. The claim (label claimed:cloud, a [job.cloud]
# comment) is made HERE, by the script, before the session starts; the unit's
# `ExecStopPost=` calls `cloud.sh finish`, so a stale claim cannot outlive its
# session.
#
# THAT LAST CLAUSE WAS FALSE FOR AS LONG AS THE TAIL WAS A TRAILING `;`
# (measured 2026-09-19). A command appended to the unit's `bash -c` string
# runs only if that shell reaches it, and the scripts it named lived in
# $WORK/board-wt, which board.sh re-checkouts every tick. While that worktree
# sat on the orphan `board` branch for ~100 minutes, cloud-audit2-141 and
# cloud-remediate-148 both finished SUCCESSFULLY, both set their successor
# label, and both had their tail die on a path that no longer existed. Neither
# claim was ever released; pr_by_label excludes a claimed PR, so both were
# invisible to this outlet for six and a half hours, until a person noticed.
# Two things had to change and both did: the tail is an ExecStopPost, which
# systemd runs however the unit ends, and the scripts it names are snapshotted
# at claim time into $WORK/units/<unit>, which nothing else writes.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; JOBS="$T/jobs"
. "$JOBS/gh-label.sh"   # label_add/label_rm: `gh pr edit --add-label` exits 1 here
. "$JOBS/localtime.sh"  # say_time/local_ts: the display zone. Data timestamps below stay `date -u`.

# THE CAP IS ONE NUMBER AND lane.sh OWNS IT. An audit session costs exactly
# what a lane session costs -- a worktree, a model, the account's shared
# window -- so it is capped by LANE_MAX and by nothing else. The default is
# READ OUT OF lane.sh rather than repeated here: a repeated default is a
# second cap that drifts the first time one of them is edited. $WORK/limits.env
# overrides it, as it does for lane.sh, and it is sourced after, so it wins.
LANE_MAX=$(sed -n 's/^LANE_MAX=\([0-9][0-9]*\).*/\1/p' "$T/lane.sh" 2>/dev/null | head -1)
. "$JOBS/models.env"; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
: "${LANE_MAX:=2}"
# AND THE TURN CAP IS READ HERE, BELOW THE SOURCE, for the reason lane.sh's
# own TURNS line carries at length. It had the identical shape and the
# identical defect: `TURNS="${CLOUD_TURNS:-120}"` sat nine lines up, was
# evaluated before anything set CLOUD_TURNS, and the source below then set
# CLOUD_TURNS for nobody. LANE_MAX just above survives because limits.env
# assigns that exact name over it; CLOUD_TURNS is a different name, read once.
TURNS="${CLOUD_TURNS:-120}"
mkdir -p "$WORK/wt" "$WORK/briefs" "$WORK/logs/cloud" "$WORK/attempts"
LOG="$WORK/logs/cloud/tick.log"
# The tick log is read by hand when something jams, so it is display: local.
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
mode="${1:-run}"

# ------------------------------------------------------------ the territory row
#
# A UNIT THIS SCRIPT STARTS IS A LANE, SO IT GETS A LANE ROW -- WRITTEN HERE.
#
# Measured 2026-09-19, $WORK/logs/board/tick.log: seven occurrences of
# "FAIL: 1 lane(s) are RUNNING with no territory row", five of them naming a
# unit this script started (cloud-audit2-102, cloud-remediate-102,
# cloud-audit2-115, cloud-remediate-115, cloud-remediate-128). Each one wakes
# a board tick, and a board tick is a model session against the account's
# shared window -- so every audit and every remediation cost one, forever, for
# bookkeeping the claim already had in hand.
#
# The cost is not only the window. fleet.py's own message says what the gap
# is: check_territory.py cannot detect a collision with a lane that is not in
# the file, so between systemd-run and the next board tick the session is
# invisible to the one gate that exists to stop two sessions writing one file.
#
# SAME BRANCH, SAME SHAPE AS THE BOARD'S. The rows the board wrote by hand for
# exactly these units are `issues`/`files`/`standing`/`note` on the orphan
# `board` branch, and that is what this writes; the note says who wrote it and
# what removes it. Never master: the copy there is the fallback board_files.py
# uses when the branch cannot be read, and a lane branch that carried a row
# would revert the allocation on the next fold (this file's own §5 warning).
#
# NO WORKTREE AND NO CHECKOUT. The row is built with plumbing -- hash-object,
# a throwaway index, commit-tree, push -- because a worktree add here is
# seconds of IO inside the very window this is closing, and because a checkout
# is the one step that could leave a half-written file behind.
#
# THE LOST UPDATE IS HANDLED BY THE PUSH, NOT BY A LOCK. Two jobs write this
# file now. If a board tick pushes between the fetch and the push below, the
# push is REJECTED (not a fast-forward, which is the default for a branch
# ref), and the loop re-reads the branch and re-applies the row to the tip
# that actually exists. Overwriting the board's commit is the failure this
# must not have: a lost update here is a lane nothing can see, which is the
# defect being closed.
BOARD_BRANCH="${HAKUX_BOARD_BRANCH:-board}"
territory_row() {   # <add|rm> <lane> <issues-json> <files-json> <note>
    local action=$1 lane=$2 ij=$3 fj=$4 note=$5
    local tmp base blob tree commit out rc try msg perr
    command -v python3 >/dev/null 2>&1 || {
        say "  territory: no python3, so the row cannot be VALIDATED; not writing one for $lane"; return 1; }
    tmp=$(mktemp -d) || return 1
    rc=1
    for try in 1 2 3; do
        # INTO A PRIVATE REF, NOT FETCH_HEAD. $REPO is the host's shared
        # checkout: the board job, every lane worktree and this script all
        # fetch into it, and FETCH_HEAD is one file they would all write. A
        # concurrent fetch between these two lines would hand this loop some
        # other branch's tip as the base, and the tree built from it would be
        # pushed at `board`. The named ref also keeps the fetched objects
        # reachable, so a gc mid-claim cannot take them.
        if ! git -C "$REPO" fetch -q origin "+refs/heads/$BOARD_BRANCH:refs/hakux/board-claim" 2>/dev/null; then
            say "  territory: cannot fetch origin/$BOARD_BRANCH; no row for $lane"; break
        fi
        base=$(git -C "$REPO" rev-parse refs/hakux/board-claim 2>/dev/null)
        if [ -z "$base" ] || ! git -C "$REPO" show "$base:territory.toml" > "$tmp/old.toml" 2>/dev/null; then
            say "  territory: origin/$BOARD_BRANCH has no territory.toml; no row for $lane"; break
        fi
        # THE VALIDATION IS THE POINT OF THIS STEP, not a formality. Three
        # board-file breakages in one session came from editing these by text
        # slicing, so the edit is applied as text (the file is 90% comments
        # and a tomllib round-trip would delete all of them) and then PARSED,
        # with every other table and every other lane asserted unchanged. A
        # result that does not parse, or that moved anything else, is refused
        # and nothing is pushed.
        out=$(python3 - "$action" "$lane" "$tmp/old.toml" "$tmp/new.toml" "$ij" "$fj" "$note" <<'PY' 2>&1
import json
import sys
import tomllib

action, lane, src, dst = sys.argv[1:5]
issues, files, note = json.loads(sys.argv[5]), json.loads(sys.argv[6]), sys.argv[7]


def die(msg):
    print(msg)
    raise SystemExit(2)


def arr(xs):
    return "[" + ", ".join(json.dumps(x) for x in xs) + "]"


def strip(text, lane):
    """Drop `[lane.<name>]` and its body. Prefix collisions cannot happen:
    the `]` is part of the match, so cloud-audit1-1155 is not cloud-audit1-115."""
    out, drop = [], False
    for line in text.splitlines(keepends=True):
        s = line.lstrip()
        if s.startswith("["):
            drop = s.startswith("[lane.%s]" % lane)
        if not drop:
            out.append(line)
    return "".join(out)


raw = open(src, encoding="utf-8").read()
try:
    old = tomllib.loads(raw)
except Exception as e:                    # refuse to edit what we cannot read
    die("origin's territory.toml does not parse (%s); refusing to write over it" % e)

old_lanes = old.get("lane") or {}
if action == "rm" and lane not in old_lanes:
    print("no row to remove")
    raise SystemExit(3)                   # nothing to push; the caller skips

body = strip(raw, lane).rstrip("\n")
note_extra = ""
if action == "add":
    # NARROWED TO WHAT NOBODY ELSE NAMES, and the omission is written into the
    # note rather than dropped silently. check_territory.py FAILS on a path
    # claimed by two lanes, or claimed while [free] lists it -- and that FAIL
    # makes preflight red for EVERY lane on the repository. A bookkeeping
    # write must not be able to do that: the collision it would report is
    # already visible through the row that holds the path, whereas a fleet-wide
    # red gate is a new outage caused by writing a row. Exact string match,
    # which is the rule check_territory.py itself uses (so `target/**` is not
    # read as covering `target/foo.c` here either).
    owner = {}
    for ln, meta in old_lanes.items():
        if ln == lane:
            continue
        for f in meta.get("files") or []:
            owner.setdefault(f, "lane." + ln)
    for f in (old.get("free") or {}).get("files") or []:
        owner.setdefault(f, "[free]")
    kept = [f for f in files if f not in owner]
    dropped = [(f, owner[f]) for f in files if f in owner]
    if dropped:
        note_extra = (" NOT CLAIMED, because these paths are already named by "
                      "another row and claiming them twice would make "
                      "check_territory.py FAIL for every lane: "
                      + "; ".join("%s (%s)" % (f, who) for f, who in dropped) + ".")
    body += "\n\n\n[lane.%s]\nissues = %s\nfiles = %s\nstanding = false\nnote = %s\n" % (
        lane, arr(issues), arr(kept), json.dumps(note + note_extra))

try:
    new = tomllib.loads(body)
except Exception as e:
    die("the edited territory.toml does not parse (%s); refusing to write it" % e)

new_lanes = new.get("lane") or {}
want = set(old_lanes) | {lane} if action == "add" else set(old_lanes) - {lane}
if set(new_lanes) != want or len(new_lanes) != len(want):
    die("lane set would go from %d to %d, wanted %d -- refusing"
        % (len(old_lanes), len(new_lanes), len(want)))
for k in set(old) | set(new):             # wave, updated_utc, free, retired.*
    if k != "lane" and old.get(k) != new.get(k):
        die("editing lane.%s changed the `%s` table as well -- refusing" % (lane, k))
for ln in want - {lane}:                  # every OTHER lane, byte for byte
    if old_lanes.get(ln) != new_lanes.get(ln):
        die("editing lane.%s changed lane.%s as well -- refusing" % (lane, ln))

open(dst, "w", encoding="utf-8").write(body)
if action == "rm":
    print("row removed (%d lanes -> %d)" % (len(old_lanes), len(new_lanes)))
else:
    print("row written, %d file(s) claimed%s (%d lanes -> %d)"
          % (len(new_lanes[lane]["files"]),
             ", %d not claimed" % len(dropped) if dropped else "",
             len(old_lanes), len(new_lanes)))
PY
        ); rc=$?
        if [ "$rc" = 3 ]; then say "  territory: $lane -- $out"; rc=0; break; fi
        if [ "$rc" != 0 ]; then say "  territory: REFUSED -- $out"; rc=1; break; fi
        msg="cloud: $action territory row for lane.$lane (jobs/cloud.sh)"
        blob=$(git -C "$REPO" hash-object -w --stdin < "$tmp/new.toml" 2>/dev/null)
        GIT_INDEX_FILE="$tmp/index" git -C "$REPO" read-tree "$base" 2>/dev/null &&
        GIT_INDEX_FILE="$tmp/index" git -C "$REPO" update-index --add --cacheinfo "100644,$blob,territory.toml" 2>/dev/null &&
        tree=$(GIT_INDEX_FILE="$tmp/index" git -C "$REPO" write-tree 2>/dev/null) &&
        commit=$(git -C "$REPO" -c user.name=hakux-cloud -c user.email=cloud@hakux.invalid \
                     commit-tree "$tree" -p "$base" -m "$msg" 2>/dev/null) || {
            say "  territory: could not build the commit for $lane"; rc=1; break; }
        # KEEP WHAT GIT SAID. A rejected push is USUALLY the race -- but it is
        # also what an expired credential, a protected branch and a failed
        # unpack look like from here, and all four print "[remote rejected]".
        # Reporting every one of them as "the board moved under us" would send
        # the next reader to look for a board tick that never ran, so the
        # message goes into the log verbatim and the classification is left to
        # whoever reads it.
        if perr=$(git -C "$REPO" push origin "$commit:refs/heads/$BOARD_BRANCH" 2>&1 >/dev/null); then
            say "  territory: lane.$lane $out on origin/$BOARD_BRANCH (${base:0:9} -> ${commit:0:9})"
            rc=0; break
        fi
        perr=$(echo "$perr" | tr '\n' ' ' | cut -c1-200)
        rc=1
        say "  territory: push rejected (try $try of 3) -- usually origin/$BOARD_BRANCH moved while this row was being written, so it is re-read and re-applied; git said: $perr"
    done
    rm -rf "$tmp"
    [ "$rc" = 0 ] || say "  territory: lane.$lane is NOT on origin/$BOARD_BRANCH; the next board tick will report it as RUNNING with no row"
    return "$rc"
}

# ---------------------------------------------------------------- finish
#
# REMOVING THE STATE LABEL IS PART OF THE JOB. A label that is never cleared
# makes the same PR eligible forever, and the session that was supposed to
# clear it is the one thing here that can forget. So the script checks:
#
#   - the session set a successor state (the audit landed and said what is
#     next) -> the label it was claimed under is stale; remove it, and clear
#     the attempt counter so a later legitimate pass starts fresh.
#   - it set none -> the unit did NOT finish. LEAVE the label, so the next
#     tick claims it again, and say so on the PR. The attempt counter bounds
#     that retry; it is not a loop.
# IT RUNS TWICE, SO IT IS IDEMPOTENT -- and it was not. The tail below is an
# `ExecStopPost=`, which systemd runs however the unit ended; the owner also
# runs this by hand when a unit has stranded a claim (both #141 and #148 were
# repaired that way on 2026-09-19). Of the five things it does, four already
# no-op on a second run -- label_rm probes the labels first and skips what is
# not there, territory_row exits 3 on a row that is absent, `rm -f` is `rm -f`,
# and say() is a log line. The fifth did not: `gh pr comment` posted the
# "ended without setting a next state" notice again, every time, and that is
# the branch a repaired claim lands in once its label is already gone.
#
# THE CLAIM LABEL IS THE KEY, not a local marker file. It is the one piece of
# state that says "a claim is live right now", it lives on the server where
# every actor can see it, and it is re-applied by the next claim -- so a
# genuine second claim of the same PR gets a live finish again, which a
# kind+num marker under $WORK could not distinguish. Read it ONCE, here,
# BEFORE anything is removed: read after label_rm and the answer is always no.
if [ "$mode" = finish ]; then
    kind="${2:?usage: cloud.sh finish <kind> <num>}"; num="${3:?}"
    have=""; read_ok=0
    for try in 1 2 3; do
        have=$(gh api "repos/$GH_REPO/issues/$num/labels" --jq '.[].name' 2>/dev/null) && { read_ok=1; break; }
        sleep 2
    done
    claimed=0; grep -qFx 'claimed:cloud' <<< "$have" && claimed=1
    # AN UNREADABLE LABEL LIST IS NOT AN ABSENT CLAIM. A transient API failure
    # at exactly this moment would otherwise take the "already finished" exit
    # and strand the claim -- the defect this whole file is closing, rebuilt
    # out of its own guard. So it goes on: every step below undoes nothing
    # when there is nothing to undo, and the asymmetry is total. A claim that
    # outlives its session is invisible to the outlet forever; a finish that
    # runs on an already-finished claim costs three API calls.
    [ "$read_ok" = 1 ] || say "finish: could not read #$num's labels in 3 tries; going on anyway rather than reading that as a finished claim"
    label_rm "$num" claimed:cloud
    # THE ROW GOES WHERE THE CLAIM GOES. `unclaim` already runs on exit, and
    # it is the only place a row written at claim can be removed -- leave it
    # and territory.toml accumulates one dead lane per audit, each of them
    # coverage that does not exist (fleet.py's `ghost`, which errs safe and so
    # nothing would ever fail on it). Before the case below: the issue path
    # has no state label and exits there, but it has a row like every other.
    territory_row rm "cloud-$kind-$num" '[]' '[]' ''
    case "$kind" in
        audit1)    state=needs-audit-1;     succ='needs-audit-2|needs-remediation|fold-ready' ;;
        audit2)    state=needs-audit-2;     succ='needs-remediation|fold-ready' ;;
        remediate) state=needs-remediation; succ='needs-audit-2|fold-ready' ;;
        *)         exit 0 ;;   # the issue path has no PR state label to clear
    esac
    if grep -qE "^($succ)$" <<< "$have"; then
        label_rm "$num" "$state"
        rm -f "$WORK/attempts/cloud-$kind-$num"
        if [ "$claimed" = 1 ]; then
            say "finish: #$num moved past $state; cleared it"
        else
            say "finish: #$num moved past $state and carries no claimed:cloud, so an earlier finish already cleared it; this one changed nothing"
        fi
    elif [ "$claimed" = 1 ]; then
        # THE ONE STEP THAT IS NOT SELF-CANCELLING, so it is the one gated on
        # the claim having been live. The rule at the top of this block is
        # untouched: a session that set no successor still keeps its state
        # label and is still claimed again, bounded by the attempt counter.
        # What is gated is only saying so a second time about the same claim.
        gh pr comment "$num" --repo "$GH_REPO" --body "[job.cloud] the $kind session for this PR ended without setting a next state, so \`$state\` stays and the outlet will claim it again. If that keeps happening the attempt counter escalates it to the owner." >/dev/null 2>&1
        say "finish: #$num set no successor to $state; left it for the next tick"
    else
        say "finish: #$num set no successor to $state and carries no claimed:cloud, so this claim was already finished; left $state alone and posted nothing"
    fi
    exit 0
fi

# ---------------------------------------------------------------- the cap
# The same glob lane.sh counts, because the units share the hakux-lane- prefix.
active=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null | wc -l)
[ "$mode" = list ] && echo "cap: LANE_MAX=$LANE_MAX ($WORK/limits.env, default from lane.sh); $active lane/audit session(s) active"
if [ "$active" -ge "$LANE_MAX" ] && [ "$mode" != list ]; then
    say "cap: $active lane/audit session(s) running (LANE_MAX=$LANE_MAX); claiming nothing"
    exit 0
fi

# ------------------------------------------------------------- what to claim
pr_by_label() {   # <label> -> "num<TAB>head<TAB>title" of the oldest claimable match
    # NO HEAD-BRANCH FILTER. Every PR the harness opens is a lane's, and the
    # lane/cloud- prefix that used to be here made every one of them invisible.
    # Skipped: one a session already holds, and one the owner has been asked
    # to decide (blocked:needs-owner), which is what stops a failing unit from
    # being claimed forever.
    gh pr list --repo "$GH_REPO" --state open --label "$1" --json number,headRefName,title,labels \
        --jq 'sort_by(.number)[] | select((.labels | map(.name) | map(select(. == "claimed:cloud" or . == "blocked:needs-owner")) | length) == 0) | "\(.number)\t\(.headRefName)\t\(.title)"' 2>/dev/null | head -1
}
issue_cloud() {
    gh issue list --repo "$GH_REPO" --state open --label cloud --json number,title,labels \
        --jq 'sort_by(.number)[] | select((.labels | map(.name) | map(select(startswith("lane:") or . == "claimed:cloud" or . == "blocked:needs-owner")) | length) == 0) | "\(.number)\t\t\(.title)"' 2>/dev/null | head -1
}
kind=""; row=""
row=$(pr_by_label needs-remediation); [ -n "$row" ] && kind=remediate
[ -z "$row" ] && { row=$(pr_by_label needs-audit-2); [ -n "$row" ] && kind=audit2; }
[ -z "$row" ] && { row=$(pr_by_label needs-audit-1); [ -n "$row" ] && kind=audit1; }
[ -z "$row" ] && { row=$(issue_cloud); [ -n "$row" ] && kind=issue; }
[ -n "$row" ] || { [ "$mode" = list ] && echo "nothing to claim"; exit 0; }
IFS=$'\t' read -r num head title <<< "$row"
name="cloud-$kind-$num"; unit="hakux-lane-$name"; wt="$WORK/wt/$name"

# ATTEMPTS, THE SAME POLICY AS A LANE'S. Leaving the state label on a PR whose
# session did not finish is what makes a retry possible; this is what stops it
# being endless. The first LANE_ESCALATE_AFTER attempts run on MODEL_AUDIT, the
# next on the escalated model, and after LANE_MAX_ATTEMPTS the PR is handed to
# the owner -- labelled blocked:needs-owner, which pr_by_label skips, so the
# outlet moves on to the next unit instead of spending another window here.
# This runs BEFORE any git or worktree work: a refusal must be cheap.
att="$WORK/attempts/$name"
n=$(( $(cat "$att" 2>/dev/null || echo 0) + 1 ))
MODEL="${HAKUX_MODEL:-$MODEL_AUDIT}"
[ "$n" -gt "$LANE_ESCALATE_AFTER" ] && MODEL="${HAKUX_MODEL:-$MODEL_LANE_ESCALATED}"
if [ "$n" -gt "$LANE_MAX_ATTEMPTS" ]; then
    if [ "$mode" = list ]; then
        echo "would REFUSE $kind #$num: $(( n - 1 )) attempts (LANE_MAX_ATTEMPTS=$LANE_MAX_ATTEMPTS)"
        exit 0
    fi
    say "REFUSED: $kind #$num has had $(( n - 1 )) attempts (LANE_MAX_ATTEMPTS=$LANE_MAX_ATTEMPTS); escalating to the owner"
    label_add "$num" blocked:needs-owner
    # `gh pr comment` on an issue number fails; the issue path claims by
    # labelling `lane:cloud-N`, so it can only reach here if that label failed.
    [ "$kind" = issue ] && cmt=issue || cmt=pr
    gh "$cmt" comment "$num" --repo "$GH_REPO" --body "[job.cloud] $(( n - 1 )) $kind sessions on this PR ended without setting a next state (LANE_MAX_ATTEMPTS=$LANE_MAX_ATTEMPTS), the last on $MODEL_LANE_ESCALATED. Labelled \`blocked:needs-owner\`; the audit outlet will not claim it again. Clear the counter with \`rm $att\` once the brief or the PR is fixed." >/dev/null 2>&1
    exit 0
fi
[ "$mode" = list ] && { echo "would claim $kind #$num ${head:+($head) }$title -- attempt $n on $MODEL"; exit 0; }
echo "$n" > "$att"

# --------------------------------------------- the unit's scripts, snapshotted
#
# A UNIT MUST NOT DEPEND ON A DIRECTORY ANOTHER JOB REPARENTS UNDERNEATH IT.
#
# $JOBS is $WORK/board-wt/docs/testing/jobs -- the board's private worktree,
# which board.sh re-checkouts on EVERY tick (`git -C "$WT" checkout --detach
# FETCH_HEAD`, board.sh:185). Measured 2026-09-19: it spent roughly 100
# minutes detached on the orphan `board` branch, which has no docs/ at all.
# Two units that had already started -- cloud-audit2-141 and
# cloud-remediate-148 -- ran to completion, both sessions SUCCEEDED and both
# set their successor label, and then their tails hit
#
#     python3: can't open file '.../board-wt/docs/testing/jobs/summarise_run.py'
#
# and the `cloud.sh finish` after it in the same chain was missing too. So
# `claimed:cloud` stayed on both PRs, pr_by_label excludes a claimed PR, and
# both were invisible to this outlet for six and a half hours until a person
# looked. Those sessions ran 22 and 44 minutes; the tree only has to move once
# in that window, and every tick moves it.
#
# WHY A SNAPSHOT AND NOT THE OTHER TWO OPTIONS. $REPO is no better: it is
# whatever branch the owner last checked out, which board.sh:188-204 already
# has its own scar about. A copy installed once under $WORK cannot move, but
# it drifts from the trunk silently, which is the same class of bug with a
# longer fuse. A snapshot cannot move BY CONSTRUCTION, and it pins the tail to
# THE VERSION THAT MADE THE CLAIM -- which is the real invariant here. The
# shape of a claim (which labels, which territory row, which attempt file) is
# defined by the script that wrote it, so the script that reverses it must be
# that same one. A tail read from a $JOBS that merely moved FORWARD is not
# just a live path; it is a different program undoing this program's work.
#
# BEFORE THE CLAIM, so a copy that fails costs nothing: there is no claim yet
# to strand, and nothing is labelled until the block below.
SNAP="$WORK/units/$name"
# Sweep the snapshots whose unit is no longer running -- and only those. A
# unit's tail EXECUTES from its own snapshot, and bash reads a script lazily
# by byte offset, so deleting one under a live unit does not tidy a directory,
# it corrupts the program the tail is in the middle of.
for d in "$WORK"/units/*; do
    [ -d "$d" ] || continue
    systemctl --user is-active --quiet "hakux-lane-$(basename "$d")" 2>/dev/null || rm -rf "$d"
done
rm -rf "$SNAP"
# lane.sh as well as jobs/: the snapshot's own cloud.sh derives $T from its
# location and reads $T/lane.sh for LANE_MAX, so the layout has to survive the
# copy, not just the files.
mkdir -p "$SNAP" && cp -a "$JOBS" "$SNAP/jobs" && cp -a "$T/lane.sh" "$SNAP/lane.sh" || {
    say "cannot snapshot $JOBS into $SNAP; NOT claiming $kind #$num, because the unit's tail would then depend on a worktree another job moves out from under it"
    # No session ran, so no attempt was spent. Give the count back: a host
    # that is out of disk must not also walk the PR towards blocked:needs-owner.
    echo "$(( n - 1 ))" > "$att"
    exit 6
}
SJOBS="$SNAP/jobs"

# ------------------------------------------------------------- claim and start
if [ -e "$wt" ]; then git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || { say "worktree $wt busy"; exit 0; }; fi
brief="$WORK/briefs/$name.md"
case "$kind" in
    issue)
        branch="lane/cloud-$num"
        git -C "$REPO" fetch -q origin "$TIP" board 2>/dev/null
        if git -C "$REPO" rev-parse -q --verify "refs/remotes/origin/$branch" >/dev/null; then
            git -C "$REPO" fetch -q origin "$branch" && git -C "$REPO" worktree add --quiet "$wt" -B "$branch" "origin/$branch" \
                || { say "cannot create $wt for issue #$num on $branch; not claiming"; exit 5; }
        else
            git -C "$REPO" worktree add --quiet "$wt" -b "$branch" "origin/$TIP" \
                || { say "cannot create $wt for issue #$num on a new $branch; not claiming"; exit 5; }
        fi
        {
            echo "# cloud lane: issue #$num -- $title"; echo
            echo "You are the cloud-class lane for issue #$num, on branch \`$branch\` (already checked out here; it is yours). Read the issue with \`gh issue view $num --repo $GH_REPO --comments\`. The claim is already made (label claimed:cloud); do not re-claim. No device is available to you; if a device run is what settles it, register the prediction and push -- the arms job runs it."; echo
            b=$(git -C "$REPO" show "origin/board:briefs/$num.md" 2>/dev/null) && { echo "## The board's brief"; echo; echo "$b"; }
        } > "$brief"
        label_add "$num" claimed:cloud "lane:cloud-$num" || say "  WARNING: could not label issue #$num claimed; another tick may claim it too"
        gh issue comment "$num" --repo "$GH_REPO" --body "[job.cloud] claimed as a cloud-class lane on the host (unit $unit, branch \`$branch\`, model $MODEL). One session; it opens a draft PR and marks it ready when done." >/dev/null 2>&1
        ;;
    *)
        branch="$head"
        git -C "$REPO" fetch -q origin "$TIP" "$branch" || { say "fetch of $branch failed; not claiming #$num"; exit 4; }
        # DETACHED, and not -B "$branch". Every local lane holds its own branch
        # in a worktree under $WORK/wt, and git refuses to check one branch out
        # twice: "fatal: 'lane/blitsafe' is already used by worktree at ...".
        # So this path exited 5 for every PR a local lane had opened -- which is
        # all of them -- and it exited BEFORE the first say(): nothing in the
        # tick log, no comment on the PR, no label moved, no worktree left to
        # inspect. The only trace was a systemd exit code nobody reads.
        #
        # An audit writes one file and pushes it. It does not need the branch
        # NAME locally, and HEAD:<branch> pushes just as well from a detached
        # head. The issue path above keeps -B: its worktree path is derived
        # from the same name, so it removes its own predecessor first.
        git -C "$REPO" worktree add --quiet --detach "$wt" "origin/$branch" \
            || { say "cannot create $wt for #$num on $branch; not claiming"; exit 5; }
        case "$kind" in
            remediate) succ_human="needs-audit-2 or fold-ready" ;;
            *)         succ_human="needs-audit-2, needs-remediation or fold-ready" ;;
        esac
        case "$kind" in
            audit1) task="Audit PASS 1 of PR #$num: read the DIFF (\`gh pr diff $num --repo $GH_REPO\`), write docs/audits/$(local_day)-${head#lane/}-pass1.md on this branch, commit and push it, post it as a PR review (\`gh pr review $num --repo $GH_REPO --comment --body-file ...\`), then set the labels per your role file (HIGH/MEDIUM → needs-remediation; else needs-audit-2, or fold-ready if there is nothing to verify). Remove needs-audit-1.";;
            audit2) task="Audit PASS 2 of PR #$num: verify each pass-1 scenario in docs/audits/*-${head#lane/}-pass1.md can no longer occur. Write the pass2 file beside it, commit and push, post the review, then: clean → remove needs-audit-2, add fold-ready; not clean → needs-remediation.";;
            remediate) task="Remediate PR #$num: fix every HIGH and MEDIUM in the latest pass-1/pass-2 audit on this branch, push, comment what changed, move the label from needs-remediation to needs-audit-2.";;
        esac
        {
            echo "# cloud: $kind PR #$num -- $title"; echo
            echo "This worktree is DETACHED at \`origin/$branch\`, because that branch is checked out elsewhere on this host and git will not hold one branch in two worktrees. Commit here and push with \`git push origin HEAD:$branch\`; that is the only branch you may push to (and only the audit file, for an audit). The claim is already made (label claimed:cloud); do not re-claim."; echo
            echo "Setting the NEXT state label is how this unit ends: $succ_human. If you end without one of them on the PR, the outlet treats the unit as unfinished, leaves the label you were claimed under, and claims it again (this is attempt $n of $LANE_MAX_ATTEMPTS, after which the PR goes to the owner)."; echo
            echo "$task"
        } > "$brief"
        label_add "$num" claimed:cloud || say "  WARNING: could not label PR #$num claimed; another tick may claim it too"
        gh pr comment "$num" --repo "$GH_REPO" --body "[job.cloud] claimed for $kind (unit $unit, model $MODEL, attempt $n of $LANE_MAX_ATTEMPTS)." >/dev/null 2>&1
        ;;
esac

# ------------------------------------------------------- the row, before the session
#
# BEFORE systemd-run, NOT AFTER, and not on the next tick. fleet.py's comment
# lists the three variants of this defect it has seen, and the second is "a
# row written and validated but COMMITTED AFTER DISPATCH" -- the lane then
# spent its whole life against a table where its files sat in [free]. A row
# written after the unit starts has a window; a row written here has none.
#
# WHAT IT CLAIMS. An audit reads a diff and writes docs/audits/<pr>-pass{1,2}
# on the PR's own branch, so `files = []` -- the honest claim, and the one the
# board wrote by hand for these same units. A remediation edits the PR's own
# files, so it names them; territory_row narrows that to the paths no other
# row already names, because a path claimed twice fails check_territory.py for
# every lane and the collision is already visible through the row that holds
# it. `issues` comes from the PR's closing references and from the `Issue: #n`
# the lane contract puts in its body header -- the first two lines only, so a
# number mentioned in prose further down does not become a coverage claim.
row_issues='[]'; row_files='[]'; row_note=""
if [ "$kind" = issue ]; then
    row_issues="[\"$num\"]"
    row_note="WRITTEN AT CLAIM by jobs/cloud.sh (the audit outlet), not by a board tick: unit $unit, a cloud-class lane on issue #$num, branch $branch, attempt $n of $LANE_MAX_ATTEMPTS on $MODEL. Claims no files: the session's brief is the issue and the files it will touch are not known at claim time -- the row exists so check_territory.py and fleet.py can SEE the session, which they could not before. \`cloud.sh finish $kind $num\` removes this row when the unit ends."
else
    # THE JSON GOES IN ON ARGV, NOT ON STDIN. `python3 -` reads its PROGRAM
    # from stdin, so a heredoc script and a pipe are the same channel: the
    # pipe is silently replaced and the parse sees an empty document. That is
    # not a hypothetical -- it is how the first version of this read every PR
    # as having no issues and no files, quietly, with the row still written.
    row_meta=$(timeout 30 gh pr view "$num" --repo "$GH_REPO" --json body,closingIssuesReferences,files 2>/dev/null)
    { read -r row_issues; read -r row_files; } < <(
        python3 - "$kind" "$row_meta" <<'PY' 2>/dev/null
import json
import re
import sys

kind = sys.argv[1]
try:
    d = json.loads(sys.argv[2])
except Exception:
    d = {}
issues = [str(r.get("number")) for r in (d.get("closingIssuesReferences") or [])]
issues += re.findall(r"Issue:\s*#(\d+)", "\n".join((d.get("body") or "").splitlines()[:2]))
# Only a remediation edits the tree it was pointed at; an audit comments.
files = [f.get("path") for f in (d.get("files") or [])] if kind == "remediate" else []
print(json.dumps(sorted(set(i for i in issues if i))))
print(json.dumps(sorted(set(f for f in files if f))))
PY
    )
    case "$kind" in
        remediate) row_note="WRITTEN AT CLAIM by jobs/cloud.sh (the audit outlet), not by a board tick: unit $unit, remediation of PR #$num on branch $branch, attempt $n of $LANE_MAX_ATTEMPTS on $MODEL. A remediation EDITS the PR's own files, so it claims them (narrowed to the paths no other row already names; any omission is spelled out below)." ;;
        *)         row_note="WRITTEN AT CLAIM by jobs/cloud.sh (the audit outlet), not by a board tick: unit $unit, ${kind/audit/audit pass } of PR #$num on branch $branch, attempt $n of $LANE_MAX_ATTEMPTS on $MODEL. Claims no files: an audit reads the diff and writes docs/audits/ on the PR's own branch, it does not edit the tree it is auditing." ;;
    esac
    row_note="$row_note \`cloud.sh finish $kind $num\` removes this row when the unit ends."
fi
[ -n "$row_issues" ] || row_issues='[]'
[ -n "$row_files" ] || row_files='[]'
# A row that could not be written does NOT stop the dispatch: the unit is
# still worth running, and the board tick that reports it as RUNNING with no
# row is exactly the fallback that exists today. It is said out loud, on the
# PR as well as in the tick log, so the fallback is not the silent path.
territory_row add "$name" "$row_issues" "$row_files" "$row_note" || {
    [ "$kind" = issue ] && cmt=issue || cmt=pr
    gh "$cmt" comment "$num" --repo "$GH_REPO" --body "[job.cloud] could not write the \`territory.toml\` row for \`lane.$name\` on the \`$BOARD_BRANCH\` branch (see $LOG). The session is starting anyway; until a board tick writes the row, \`check_territory.py\` cannot see this unit." >/dev/null 2>&1; }

[ -f "$REPO/android/local.properties" ] && cp "$REPO/android/local.properties" "$wt/android/local.properties"
# UTC in the FILENAME: data. These sort, and `ls -t` aside, the name is how a
# run is located; a local-time name would jumble across the fall-back.
log="$WORK/logs/cloud/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
# THE TAIL IS A UNIT PROPERTY, NOT THE LAST COMMAND OF A STRING.
#
# `bash -c "...; cloud.sh finish ..."` runs the tail only if that shell
# REACHES it. It does not when the unit is killed, when the manager restarts,
# when the shell dies -- or, as on 2026-09-19, when an earlier command in the
# chain cannot be found, which is precisely how #141 and #148 were stranded:
# `python3 '$JOBS/summarise_run.py'` failed on a missing path and took the
# `finish` after it down with it, even though both sessions had SUCCEEDED and
# set their successor label. systemd runs `ExecStopPost=` however the main
# process ended -- success, failure, signal, timeout, manager shutdown -- and
# that is the only place a tail whose whole job is to undo a claim can live.
# Line 50's invariant ("a stale claim cannot outlive its session") was right;
# a trailing `;` was never able to hold it.
#
# ONE CALL SITE, NOT TWO. finish is idempotent now, but it is still not called
# both in-band and on stop: two calls would post the "ended without setting a
# next state" notice about one session twice in the ORDINARY case, and prove
# nothing extra in the failing one, where the in-band copy is exactly what did
# not run.
#
# AN ABSOLUTE PATH, because systemd requires one for the first word of an
# Exec* command. A bare `bash` here does not fall back to $PATH, it makes the
# unit fail to LOAD -- inert in the loudest possible way, and only on the host.
#
# $SJOBS, not $JOBS: the snapshot above, which nothing reparents. --setenv
# reaches ExecStopPost too (it is Environment= on the unit, not on one Exec
# line), so the tail gets the same $WORK, $GH_REPO and $REPO this tick used --
# which matters, because the row it removes was written against them.
systemd-run --user --unit "$unit" --collect \
    --property=ExecStopPost="/bin/bash $SJOBS/cloud.sh finish $kind $num" \
    --setenv=HAKUX_ROLE=cloud --setenv=HAKUX_BRIEF="$brief" --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
    --setenv=HAKUX_WORK="$WORK" --setenv=GH_REPO="$GH_REPO" \
    --setenv=HAKUX_REPO_DIR="$REPO" --setenv=HAKUX_BOARD_BRANCH="$BOARD_BRANCH" \
    --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
    --working-directory="$wt" \
    bash -c "claude -p \"\$(cat '$brief')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$SJOBS/roles/cloud.md' --allowedTools \"\$(cat '$SJOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$SJOBS/summarise_run.py' '$log' $name '$MODEL' >> '$WORK/logs/cloud/index.tsv'; exit \$rc" \
    && say "started $unit: $kind #$num on $branch ($MODEL, attempt $n); log $log; scripts snapshotted at $SNAP" || {
        # NO SESSION, NO CLAIM. The unit's tail is what undoes the claim, so a
        # unit that never started would leave the whole of it behind for good:
        # a row that is coverage which does not exist and which nothing fails
        # on (fleet.py prints `ghost` and sets no rc), AND a `claimed:cloud`
        # that pr_by_label excludes from every future tick -- the same
        # permanent invisibility as the stranded tail above, reached by the
        # one path ExecStopPost cannot cover, because there is no unit to stop.
        #
        # The STATE label stays: the session never ran, so the PR still needs
        # what it was claimed for, and the next tick should pick it up. The
        # attempt is given back for the same reason.
        say "systemd-run failed for $unit; dropping the claim so the next tick can pick #$num up again"
        territory_row rm "$name" '[]' '[]' ''
        # if/else, not `A && x || y`: label_rm returning 1 on the issue path
        # would otherwise fall through and run the PR-path removal as well.
        if [ "$kind" = issue ]; then
            label_rm "$num" claimed:cloud "lane:cloud-$num"
        else
            label_rm "$num" claimed:cloud
        fi
        echo "$(( n - 1 ))" > "$att"
        rm -rf "$SNAP"
    }
[ -x "$JOBS/status.sh" ] && bash "$JOBS/status.sh" >/dev/null 2>&1
exit 0
