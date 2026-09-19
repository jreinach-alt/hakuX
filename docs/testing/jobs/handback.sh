#!/usr/bin/env bash
#
# The handback job: the actor for a PR a job handed back to its lane.
#
#   handback.sh          resume the lane of every handed-back PR
#   handback.sh list     what it would resume, and why it would skip the rest
#
# WHY THIS EXISTS. `fold.sh` refuses to resolve a merge conflict -- a merge
# resolved by a script that does not understand the code is how a working fix
# was reverted on 2026-09-12 -- so it labels the PR `needs-rebase`, comments
# naming the files, and stops. That label was set by one job, displayed by
# `status.sh`, and acted on by NONE: `roles/board.md` had no rule for it, the
# board only wakes on a `fleet.py` or coverage `FAIL`, and the lane that would
# fix it is a `systemd-run` transient unit that exited when its session ended.
# Complete, tested, green work was parked permanently. Seven of the ten lanes
# open on 2026-09-19 append to `jobs/selftest.sh` and every fold moves master,
# so it was going to fire seven times in an afternoon.
#
# ONE TABLE, NOT ONE SCRIPT PER LABEL. `needs-rebase` is the fourth terminal
# label; `needs-audit-1`, `needs-audit-2` and `needs-remediation` are the
# others (lane.auditoutlet, PR #130). They differ only in what the session is
# told to do, so the label is a ROW in HANDBACK_ROWS below and the work is a
# function that prints the brief. Everything else -- deriving the lane name,
# resuming only on a new cause, the cap, the attempt counter -- is written
# once, here. Adding a label is an edit to that list.
#
# WHAT IT DOES NOT DO. It resolves nothing and it starts nothing itself: the
# actor is `docs/testing/lane.sh resume`, which already counts the attempt,
# escalates the model on the fourth, and refuses past LANE_MAX_ATTEMPTS so the
# board's `decision-needed` path stays reachable.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"          # docs/testing
LANE_SH="${HAKUX_LANE_SH:-$T/lane.sh}"
. "$(dirname "${BASH_SOURCE[0]}")/gh-label.sh"   # label_add/label_rm: `gh pr edit --add-label` exits 1 here
. "$(dirname "${BASH_SOURCE[0]}")/localtime.sh"  # say_time/local_ts: the display zone
H="$WORK/handback"
mkdir -p "$H/done" "$H/cause" "$WORK/logs/handback"
LOG="$WORK/logs/handback/tick.log"
# The tick log is read by hand when something jams, so it is display: local.
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
mode="${1:-run}"
comment() { printf '%s\n' "$2" > "$H/comment.md"; gh pr comment "$1" --repo "$GH_REPO" --body-file "$H/comment.md" >/dev/null 2>&1; }

# ------------------------------------------------------------- the table
#
#   <label>  <action>  [<label that means this one is stale>...]
#
# A PR carrying any of the trailing labels is skipped: it has already moved on
# and re-resuming it is the loop this job must not become. A lane that resolves
# its conflict re-applies `fold-ready` and may leave `needs-rebase` behind, and
# its head has moved, so without this the next tick would read a new cause and
# resume a lane whose work is already back in the pipeline.
HANDBACK_ROWS=(
    "needs-rebase   resume_rebase   fold-ready folded"
)

# ------------------------------------------------------------- the actions
# An action prints the section appended to the lane's brief. It gets:
#   $1 pr  $2 head branch  $3 head sha  $4 lane name  $5 cause detail (may be "")
resume_rebase() {
    cat <<EOF

---

## Handed back $(say_time_s): PR #$1 no longer merges into \`$TIP\`

The fold job could not merge \`$2\` into \`$TIP\` at \`${3:0:10}\`${5:+, conflicting in: $5}.
It resolves nothing itself, on purpose. Resolving it is now the whole task:

\`\`\`
git fetch origin $TIP
git merge origin/$TIP        # MERGE, never rebase: a rebase rewrites every
                             # sha and un-ancestors any registered
                             # prediction's a_ref/b_ref (ORCHESTRATION-DESIGN
                             # 8.1). Merging keeps them bound forever.
# resolve the conflict, keeping BOTH sides' intent, then:
git commit && git push
bash docs/testing/jobs/selftest.sh     # if the conflict was under jobs/
\`\`\`

Then, once CI is green on the new head:

\`\`\`
bash docs/testing/jobs/gh-label.sh rm  $1 needs-rebase
bash docs/testing/jobs/gh-label.sh add $1 fold-ready
\`\`\`

Do not re-open, re-measure or extend the work this PR already carries; it was
audited and green, and only the merge base moved. If the conflict cannot be
resolved without a decision that is not yours, say so in \`NOTES.md\` and in a
PR comment starting \`[lane.$4] blocked:\`, and stop -- that is a finished
outcome.
EOF
}

# ------------------------------------------------------------- lane naming
# THE LANE NAME IS NOT THE PR, AND NOT EVERY HEAD BRANCH HAS ONE. `lane/<name>`
# is a local lane with a worktree under $WORK/wt. `lane/cloud-*` is a cloud
# session's branch: no local worktree, and roles/board.md says cloud lanes
# remediate themselves. `claude/hakux-...` is an interactive session's branch
# with no lane at all. Both are live on this repository today, so a guess here
# is a wrong `lane.sh resume` that burns an attempt against the escalation
# budget of a lane that does not exist.
#
# It sets NAME and REASON rather than printing the name: `n=$(lane_name ...)`
# runs the function in a command-substitution subshell, so the REASON it sets
# on the refusing paths is discarded and the PR gets a comment that stops
# mid-sentence at the colon -- which is the whole content of the answer.
NAME=""; REASON=""
lane_name() {   # <head branch> -> 0 with $NAME set, or 1 with $REASON set
    NAME=""; REASON=""
    case "$1" in
        lane/cloud-*)
            REASON="\`$1\` is a cloud session's branch: it has no local worktree, and cloud lanes remediate themselves (\`jobs/roles/cloud.md\`). Nothing local can resume it."
            return 1 ;;
        lane/*/*)
            REASON="\`$1\` has a slash inside the lane name; \`lane.sh\` names a worktree \`\$WORK/wt/<name>\` and a unit \`hakux-lane-<name>\`, neither of which can hold one. Not guessing."
            return 1 ;;
        lane/?*)
            NAME="${1#lane/}"; return 0 ;;
        *)
            REASON="\`$1\` is not a \`lane/<name>\` branch, so there is no local lane to resume. Whoever owns this branch merges \`origin/$TIP\` into it by hand."
            return 1 ;;
    esac
}

# ------------------------------------------------------------- the pickup
prs_for() {   # <label> -> "num<TAB>headRefName<TAB>headRefOid<TAB>labels,comma,separated"
    gh pr list --repo "$GH_REPO" --state open --label "$1" --json number,headRefName,headRefOid,labels \
        --jq 'sort_by(.number)[] | "\(.number)\t\(.headRefName)\t\(.headRefOid)\t\(.labels | map(.name) | join(","))"' 2>/dev/null
}

resumed=0; seen=0
for row in "${HANDBACK_ROWS[@]}"; do
    read -r label action stale <<< "$row"
    while IFS=$'\t' read -r pr branch head labels; do
        [ -n "${pr:-}" ] || continue

        # THE ROW MUST CARRY THE LABEL IT WAS ASKED FOR. `gh pr list --label`
        # does the filtering server-side and this job never re-checks it, so a
        # row that comes back without the label means the filter did not
        # happen -- a `--jq` that stopped emitting the labels field, a gh that
        # ignored the flag, a shim. The failure mode is not "nothing found",
        # which would be visible; it is resuming the FIRST OPEN PR on the
        # repository, by name, against its lane's attempt budget. Found by the
        # fold-ci checks, whose gh shim answers every `pr list` with one row:
        # every fold tick ran a resume of lane.foldci and commented on #102.
        case ",$labels," in
            *",$label,"*) ;;
            *) say "#${pr:-?} came back for --label $label without it (labels=${labels:-none}); the filter did not happen, so acting on it would resume the wrong lane"
               continue ;;
        esac

        seen=$((seen+1))
        skip=""
        for s in $stale; do case ",$labels," in *",$s,"*) skip="$s" ;; esac; done
        if [ -n "$skip" ]; then
            [ "$mode" = list ] && echo "#$pr $branch: $label but also $skip; already moved on"
            continue
        fi

        if ! lane_name "$branch"; then
            # Say it once per PR, not once per tick: this state does not change
            # by itself, and a comment every 30 minutes is noise on a PR whose
            # owner is a person.
            [ "$mode" = list ] && { echo "#$pr $branch: $label, NO LANE -- $REASON"; continue; }
            if [ ! -f "$H/done/noname-$pr" ]; then
                printf '%s\n' "$REASON" > "$H/done/noname-$pr"
                say "#$pr $branch: $label but no local lane; $REASON"
                comment "$pr" "[job.handback] \`$label\` is set on this PR and no local lane can act on it: $REASON"
            fi
            continue
        fi
        name="$NAME"

        # RESUME ONLY ON A NEW CAUSE. Keyed on the head sha the handback was
        # found at, the way fold.sh already keys $F/failed/$pr-$head: a lane
        # resumed twice for the same head has been given no new information,
        # and the second session re-reads the same NOTES.md and the same diff.
        # When the lane pushes, the head moves and a fresh conflict is a fresh
        # cause.
        marker="$H/done/$label-$pr-$head"
        if [ -f "$marker" ]; then
            [ "$mode" = list ] && echo "#$pr $branch: $label already actioned at ${head:0:10} ($(head -1 "$marker"))"
            continue
        fi

        cause=""
        [ -f "$H/cause/$pr-$head" ] && cause=$(sed -n 's/^files=//p' "$H/cause/$pr-$head" | head -1)

        if [ ! -d "$WORK/wt/$name" ] || [ ! -f "$WORK/briefs/$name.md" ]; then
            [ "$mode" = list ] && { echo "#$pr $branch: $label, lane $name has no worktree or brief on this host"; continue; }
            echo "no worktree or brief for lane $name" > "$marker"
            say "#$pr: lane $name has no worktree ($WORK/wt/$name) or brief; cannot resume"
            comment "$pr" "[job.handback] \`$label\` is set and lane \`$name\`'s worktree or brief is gone from this host (\`$WORK/wt/$name\`), so \`lane.sh resume\` cannot run. It needs \`lane.sh start $name <brief>\`, which is the board's call, not this job's."
            continue
        fi

        # A lane whose unit is still running is not stalled, and
        # `systemd-run --unit` on a live unit fails AFTER lane.sh has already
        # counted the attempt -- a wasted attempt against the four the
        # escalation policy allows. No marker: next tick looks again.
        if systemctl --user is-active --quiet "hakux-lane-$name" 2>/dev/null; then
            [ "$mode" = list ] && echo "#$pr $branch: $label, but hakux-lane-$name is still running"
            say "#$pr: lane $name is still active; not resuming"
            continue
        fi

        if [ "$mode" = list ]; then echo "#$pr $branch @ ${head:0:10}: WOULD RESUME lane.$name ($label)"; continue; fi
        [ "$resumed" -eq 0 ] || { say "#$pr waits: one resume per tick"; continue; }

        # The handback goes in the brief BEFORE the resume, because that file is
        # what `lane.sh resume` hands the session -- and it is rolled back if the
        # resume does not happen. A capped tick that left the section behind
        # would append another on the next tick and another after that, so the
        # session that finally ran would open with the same paragraph five
        # times and no way to tell which head each one was about.
        size=$(wc -c < "$WORK/briefs/$name.md")
        "$action" "$pr" "$branch" "$head" "$name" "$cause" >> "$WORK/briefs/$name.md"
        out=$(bash "$LANE_SH" resume "$name" 2>&1); rc=$?
        [ "$rc" -eq 0 ] || truncate -s "$size" "$WORK/briefs/$name.md"
        if [ "$rc" -eq 0 ]; then
            echo "resumed: $out" > "$marker"
            say "#$pr: resumed lane.$name -- $out"
            comment "$pr" "[job.handback] Resumed \`lane.$name\` on \`$label\` at \`${head:0:10}\`${cause:+ (conflicting in \`$cause\`)}. The handback was appended to its brief: merge \`origin/$TIP\` (never rebase -- it would un-ancestor any registered prediction), resolve, push, then re-apply \`fold-ready\`. This job resumes a lane once per head sha, so pushing is what makes another handback possible."
            resumed=1
        elif grep -q 'LANE_MAX_ATTEMPTS' <<< "$out"; then
            # THE END OF THE LINE, AND IT MUST STAY REACHABLE. lane.sh refuses
            # after LANE_MAX_ATTEMPTS and the board opens a decision-needed
            # issue (roles/board.md). Marked, so this is said once.
            echo "attempts exhausted: $out" > "$marker"
            say "#$pr: lane $name REFUSED (attempts exhausted): $out"
            label_add "$pr" blocked:needs-owner || say "  WARNING: could not label #$pr blocked:needs-owner"
            comment "$pr" "[job.handback] Not resumed -- \`lane.$name\` has used every attempt:
\`\`\`
$out
\`\`\`
This is the owner's call now. Per \`jobs/roles/board.md\`, the board opens a \`decision-needed\` issue quoting this lane's \`NOTES.md\` and does not start it again; the attempt counter is reset only by the owner, when the brief was the problem."
        elif grep -q 'LANE_MAX=' <<< "$out"; then
            # The fleet cap, not a failure. NO MARKER: the cause is unchanged
            # and still unactioned, and the next tick must try it again. lane.sh
            # checks the cap before it counts the attempt, so nothing was spent.
            say "#$pr: lane $name not resumed, fleet at cap: $out"
        else
            echo "resume failed: $out" > "$marker"
            say "#$pr: lane $name resume FAILED rc=$rc: $out"
            comment "$pr" "[job.handback] \`lane.sh resume $name\` failed (rc=$rc) on \`$label\` at \`${head:0:10}\`:
\`\`\`
$out
\`\`\`
Not retried at this head. Push to the branch, or fix the host, and the next tick reads a new cause."
        fi
    done <<< "$(prs_for "$label")"
done

# Say so when there is nothing, the way `fold.sh list` does: an empty run and a
# broken `gh` look identical otherwise, and this job's whole output is one line
# in $WORK/logs/handback/tick.log that somebody reads at a distance.
[ "$seen" -eq 0 ] && { [ "$mode" = list ] && echo "nothing handed back (${HANDBACK_ROWS[*]%% *})" || say "nothing handed back"; }
exit 0
