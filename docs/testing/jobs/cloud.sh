#!/usr/bin/env bash
#
# The "cloud" lane class, run on the host. Timer: hourly.
#
#   cloud.sh          claim one unit of no-device work and start a session on it
#   cloud.sh list     what it would claim
#
# WHY THIS RUNS ON THE HOST AND NOT IN THE CLOUD (measured 2026-09-19). A
# Routine created from a session fires a fresh cloud session that has NO
# repository checkout, NO GitHub tooling, and stalls forever on the first
# permission prompt nobody is there to answer; a session created directly
# with the repo attached wrote its file and was then refused the commit and
# the push by the auto-mode classifier. Four diagnostic sessions, zero
# branches pushed. Until a Routine can be created with the repo, a GitHub
# connector and a non-prompting permission mode (the claude.ai Routines UI
# can do that; this tool cannot), the cloud role runs here, as a headless
# session in its own worktree exactly like a lane, under its own cap. The
# role file (roles/cloud.md) is the same either way, so moving it later is
# a change of launcher, not of contract.
#
# WHAT IT CLAIMS, in order: a needs-remediation PR on a lane/cloud-* branch,
# a needs-audit-2 PR, a needs-audit-1 PR, an issue labelled `cloud` with no
# lane: label. The claim (label claimed:cloud, a [job.cloud] comment) is
# made HERE, by the script, before the session starts, and the label is
# removed by the unit when the session ends, so a stale claim cannot outlive
# its session.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
TURNS="${CLOUD_TURNS:-120}"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; JOBS="$T/jobs"
. "$JOBS/models.env"; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
CLOUD_MAX="${CLOUD_MAX:-1}"
MODEL="${HAKUX_MODEL:-$MODEL_AUDIT}"
mkdir -p "$WORK/wt" "$WORK/briefs" "$WORK/logs/cloud"
LOG="$WORK/logs/cloud/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }
mode="${1:-run}"

active=$(systemctl --user list-units 'hakux-cloud-*' --state=active,activating --no-legend 2>/dev/null | wc -l)
if [ "$active" -ge "$CLOUD_MAX" ] && [ "$mode" != list ]; then say "cap: $active cloud session(s) running (CLOUD_MAX=$CLOUD_MAX)"; exit 0; fi

pr_by_label() {   # <label> [head-prefix] -> "num<TAB>head<TAB>title" of the oldest unclaimed match
    gh pr list --repo "$GH_REPO" --state open --label "$1" --json number,headRefName,title,labels \
        --jq "sort_by(.number)[] | select((.labels | map(.name) | index(\"claimed:cloud\")) == null) | select(.headRefName | startswith(\"${2:-}\")) | \"\(.number)\t\(.headRefName)\t\(.title)\"" 2>/dev/null | head -1
}
issue_cloud() {
    gh issue list --repo "$GH_REPO" --state open --label cloud --json number,title,labels \
        --jq 'sort_by(.number)[] | select((.labels | map(.name) | map(select(startswith("lane:") or . == "claimed:cloud")) | length) == 0) | "\(.number)\t\t\(.title)"' 2>/dev/null | head -1
}
kind=""; row=""
row=$(pr_by_label needs-remediation lane/cloud-); [ -n "$row" ] && kind=remediate
[ -z "$row" ] && { row=$(pr_by_label needs-audit-2); [ -n "$row" ] && kind=audit2; }
[ -z "$row" ] && { row=$(pr_by_label needs-audit-1); [ -n "$row" ] && kind=audit1; }
[ -z "$row" ] && { row=$(issue_cloud); [ -n "$row" ] && kind=issue; }
[ -n "$row" ] || { [ "$mode" = list ] && echo "nothing to claim"; exit 0; }
IFS=$'\t' read -r num head title <<< "$row"
[ "$mode" = list ] && { echo "would claim $kind #$num ${head:+($head) }$title"; exit 0; }

name="cloud-$kind-$num"; unit="hakux-$name"; wt="$WORK/wt/$name"
if [ -e "$wt" ]; then git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || { say "worktree $wt busy"; exit 0; }; fi
brief="$WORK/briefs/$name.md"
case "$kind" in
    issue)
        branch="lane/cloud-$num"
        git -C "$REPO" fetch -q origin "$TIP" board 2>/dev/null
        if git -C "$REPO" rev-parse -q --verify "refs/remotes/origin/$branch" >/dev/null; then
            git -C "$REPO" fetch -q origin "$branch" && git -C "$REPO" worktree add --quiet "$wt" -B "$branch" "origin/$branch" || exit 5
        else
            git -C "$REPO" worktree add --quiet "$wt" -b "$branch" "origin/$TIP" || exit 5
        fi
        {
            echo "# cloud lane: issue #$num -- $title"; echo
            echo "You are the cloud-class lane for issue #$num, on branch \`$branch\` (already checked out here; it is yours). Read the issue with \`gh issue view $num --repo $GH_REPO --comments\`. The claim is already made (label claimed:cloud); do not re-claim. No device is available to you; if a device run is what settles it, register the prediction and push -- the arms job runs it."; echo
            b=$(git -C "$REPO" show "origin/board:briefs/$num.md" 2>/dev/null) && { echo "## The board's brief"; echo; echo "$b"; }
        } > "$brief"
        gh issue edit "$num" --repo "$GH_REPO" --add-label claimed:cloud --add-label "lane:cloud-$num" >/dev/null 2>&1
        gh issue comment "$num" --repo "$GH_REPO" --body "[job.cloud] claimed as a cloud-class lane on the host (unit $unit, branch \`$branch\`, model $MODEL). One session; it opens a draft PR and marks it ready when done." >/dev/null 2>&1
        unclaim="gh issue edit $num --repo $GH_REPO --remove-label claimed:cloud"
        ;;
    *)
        branch="$head"
        git -C "$REPO" fetch -q origin "$TIP" "$branch" || exit 4
        git -C "$REPO" worktree add --quiet "$wt" -B "$branch" "origin/$branch" || exit 5
        case "$kind" in
            audit1) task="Audit PASS 1 of PR #$num: read the DIFF (\`gh pr diff $num --repo $GH_REPO\`), write docs/audits/$(date -u +%F)-${head#lane/}-pass1.md on this branch, commit and push it, post it as a PR review (\`gh pr review $num --repo $GH_REPO --comment --body-file ...\`), then set the labels per your role file (HIGH/MEDIUM → needs-remediation; else needs-audit-2, or fold-ready if there is nothing to verify). Remove needs-audit-1.";;
            audit2) task="Audit PASS 2 of PR #$num: verify each pass-1 scenario in docs/audits/*-${head#lane/}-pass1.md can no longer occur. Write the pass2 file beside it, commit and push, post the review, then: clean → remove needs-audit-2, add fold-ready; not clean → needs-remediation.";;
            remediate) task="Remediate PR #$num: fix every HIGH and MEDIUM in the latest pass-1/pass-2 audit on this branch, push, comment what changed, move the label from needs-remediation to needs-audit-2.";;
        esac
        {
            echo "# cloud: $kind PR #$num -- $title"; echo
            echo "Branch \`$branch\` is checked out here and is the only branch you may push to (and only the audit file, for an audit). The claim is already made (label claimed:cloud); do not re-claim."; echo
            echo "$task"
        } > "$brief"
        gh pr edit "$num" --repo "$GH_REPO" --add-label claimed:cloud >/dev/null 2>&1
        gh pr comment "$num" --repo "$GH_REPO" --body "[job.cloud] claimed for $kind (cloud-class session on the host, unit $unit, model $MODEL)." >/dev/null 2>&1
        unclaim="gh pr edit $num --repo $GH_REPO --remove-label claimed:cloud"
        ;;
esac
[ -f "$REPO/android/local.properties" ] && cp "$REPO/android/local.properties" "$wt/android/local.properties"
log="$WORK/logs/cloud/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
systemd-run --user --unit "$unit" --collect \
    --setenv=HAKUX_ROLE=cloud --setenv=HAKUX_BRIEF="$brief" --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
    --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
    --working-directory="$wt" \
    bash -c "claude -p \"\$(cat '$brief')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/cloud.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' $name '$MODEL' >> '$WORK/logs/cloud/index.tsv'; $unclaim >/dev/null 2>&1; exit \$rc" \
    && say "started $unit: $kind #$num on $branch ($MODEL); log $log" || say "systemd-run failed for $unit"
[ -x "$JOBS/status.sh" ] && bash "$JOBS/status.sh" >/dev/null 2>&1
exit 0
