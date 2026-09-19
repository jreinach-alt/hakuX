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
[ -f "$REPO/android/local.properties" ] && cp "$REPO/android/local.properties" "$wt/android/local.properties"
log="$WORK/logs/cloud/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
finish="bash '$JOBS/cloud.sh' finish $kind $num"
systemd-run --user --unit "$unit" --collect \
    --setenv=HAKUX_ROLE=cloud --setenv=HAKUX_BRIEF="$brief" --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
    --setenv=HAKUX_WORK="$WORK" --setenv=GH_REPO="$GH_REPO" \
    --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
    --working-directory="$wt" \
    bash -c "claude -p \"\$(cat '$brief')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/cloud.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' $name '$MODEL' >> '$WORK/logs/cloud/index.tsv'; $finish >/dev/null 2>&1; exit \$rc" \
    && say "started $unit: $kind #$num on $branch ($MODEL, attempt $n); log $log" || say "systemd-run failed for $unit"
[ -x "$JOBS/status.sh" ] && bash "$JOBS/status.sh" >/dev/null 2>&1
exit 0
