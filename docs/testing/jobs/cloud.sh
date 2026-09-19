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
# tail calls `cloud.sh finish`, so a stale claim cannot outlive its session.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
TURNS="${CLOUD_TURNS:-120}"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; JOBS="$T/jobs"
. "$JOBS/gh-label.sh"   # label_add/label_rm: `gh pr edit --add-label` exits 1 here

# THE CAP IS ONE NUMBER AND lane.sh OWNS IT. An audit session costs exactly
# what a lane session costs -- a worktree, a model, the account's shared
# window -- so it is capped by LANE_MAX and by nothing else. The default is
# READ OUT OF lane.sh rather than repeated here: a repeated default is a
# second cap that drifts the first time one of them is edited. $WORK/limits.env
# overrides it, as it does for lane.sh, and it is sourced after, so it wins.
LANE_MAX=$(sed -n 's/^LANE_MAX=\([0-9][0-9]*\).*/\1/p' "$T/lane.sh" 2>/dev/null | head -1)
. "$JOBS/models.env"; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
: "${LANE_MAX:=2}"
mkdir -p "$WORK/wt" "$WORK/briefs" "$WORK/logs/cloud" "$WORK/attempts"
LOG="$WORK/logs/cloud/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }
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
    local tmp base blob tree commit out rc try msg
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
        if git -C "$REPO" push -q origin "$commit:refs/heads/$BOARD_BRANCH" 2>/dev/null; then
            say "  territory: lane.$lane $out on origin/$BOARD_BRANCH ($(echo "$base" | cut -c1-9) -> $(echo "$commit" | cut -c1-9))"
            rc=0; break
        fi
        rc=1
        say "  territory: push rejected (try $try of 3) -- origin/$BOARD_BRANCH moved while this row was being written; re-reading it"
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
if [ "$mode" = finish ]; then
    kind="${2:?usage: cloud.sh finish <kind> <num>}"; num="${3:?}"
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
    have=$(gh api "repos/$GH_REPO/issues/$num/labels" --jq '.[].name' 2>/dev/null)
    if grep -qE "^($succ)$" <<< "$have"; then
        label_rm "$num" "$state"
        rm -f "$WORK/attempts/cloud-$kind-$num"
        say "finish: #$num moved past $state; cleared it"
    else
        gh pr comment "$num" --repo "$GH_REPO" --body "[job.cloud] the $kind session for this PR ended without setting a next state, so \`$state\` stays and the outlet will claim it again. If that keeps happening the attempt counter escalates it to the owner." >/dev/null 2>&1
        say "finish: #$num set no successor to $state; left it for the next tick"
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
            audit1) task="Audit PASS 1 of PR #$num: read the DIFF (\`gh pr diff $num --repo $GH_REPO\`), write docs/audits/$(date -u +%F)-${head#lane/}-pass1.md on this branch, commit and push it, post it as a PR review (\`gh pr review $num --repo $GH_REPO --comment --body-file ...\`), then set the labels per your role file (HIGH/MEDIUM → needs-remediation; else needs-audit-2, or fold-ready if there is nothing to verify). Remove needs-audit-1.";;
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
log="$WORK/logs/cloud/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
finish="bash '$JOBS/cloud.sh' finish $kind $num"
systemd-run --user --unit "$unit" --collect \
    --setenv=HAKUX_ROLE=cloud --setenv=HAKUX_BRIEF="$brief" --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
    --setenv=HAKUX_WORK="$WORK" --setenv=GH_REPO="$GH_REPO" \
    --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
    --working-directory="$wt" \
    bash -c "claude -p \"\$(cat '$brief')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/cloud.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' $name '$MODEL' >> '$WORK/logs/cloud/index.tsv'; $finish >/dev/null 2>&1; exit \$rc" \
    && say "started $unit: $kind #$num on $branch ($MODEL, attempt $n); log $log" || {
        # NO SESSION, NO ROW. The unit's tail is what removes the row, so a
        # unit that never started would leave one behind for good -- a claim
        # with no agent, which is coverage that does not exist and which
        # nothing fails on (fleet.py prints `ghost` and sets no rc).
        say "systemd-run failed for $unit"
        territory_row rm "$name" '[]' '[]' ''
    }
[ -x "$JOBS/status.sh" ] && bash "$JOBS/status.sh" >/dev/null 2>&1
exit 0
