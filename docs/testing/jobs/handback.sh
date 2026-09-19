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
# THE SECOND CAUSE IS NOT A LABEL: A DRAFT PR WHOSE LANE HAS EXITED. Every
# actor filters drafts out, deliberately -- `board.sh` skips `isDraft`,
# `fleet.py` counts only non-draft lane PRs, `fold.sh` refuses to fold one --
# because while the lane is running, draft means exactly what it says. The
# state is only wrong ONCE THE UNIT HAS EXITED, and until this job nothing
# joined those two facts: `isDraft` is read from GitHub, liveness from
# systemd. On 2026-09-19 five open lane PRs (#137, #141, #145, #146, #148)
# were finished, CI-green, in draft, with no lane running and no actor that
# could ever touch them.
#
# AND THEY MOSTLY DID NOT FAIL -- THEY WERE WAITING. CI on a pushed head is
# ~10 minutes, a device arm is ~90, an audit is a different session; a lane
# has no way to sleep and resume, so one that pushes and must wait can only
# burn turns polling until the turn cap cuts it, or end tidily and leave a
# draft. The tidier the lane, the more likely it strands. So this is not a
# lane misbehaving, and the resume must carry the RESOLVED STATE -- CI is
# GREEN on this sha, your arm was judged -- or the new session reads the same
# NOTES.md and the same diff and strands again.
#
# IT RESUMES THE LANE; IT DOES NOT MARK THE PR READY. `roles/lane.md`'s
# definition of done includes things no script can check: NOTES.md written,
# `Files:` matching the diff, the prediction committed with its refs. A job
# that flipped `isDraft` because CI went green would declare finished work
# nobody verified.
#
# AND WAITING IS NOT FAILING, so a strand resume does not spend one of the
# four attempts behind the escalation policy (`lane.sh` counts every resume;
# this job puts the counter back). What bounds it instead is DRAFT_STRAND_MAX
# per lane, plus the same once-per-head-sha key as every other cause.
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
H="$WORK/handback"
mkdir -p "$H/done" "$H/cause" "$H/strand" "$WORK/attempts" "$WORK/logs/handback"
LOG="$WORK/logs/handback/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }
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

# The strand causes are not labels, so they are not rows in that table: their
# pickup asks GitHub a different question. They share everything below it.
#
#   draft-strand-arm    the arm this lane was waiting for has been judged
#                       (`arms.sh` labels the PR `verified` or `regressed`)
#   draft-strand-quiet  nothing has happened on the PR for DRAFT_STRAND_SECS
#
# Two keys, not one, on purpose: the marker is `$label-$pr-$head`, so a
# verdict that lands AFTER a quiet resume is still a new cause at the same
# head, while a second quiet tick at that head is not.
#
# The stale set is wider than `needs-rebase`'s because every one of these
# labels already has an actor: the rows above, the audit outlet, or a person.
# A draft carrying one of them is not unowned, which is the only thing this
# cause is about.
STRAND_STALE="folded fold-ready needs-rebase needs-audit-1 needs-audit-2 needs-remediation blocked:needs-owner"
# Four fold ticks: long enough to outlast a ~90-minute device arm, so a lane
# that ended while its arm was in flight is not resumed to be told nothing.
DRAFT_STRAND_SECS="${DRAFT_STRAND_SECS:-7200}"
# The bound that replaces the attempt counter this cause does not spend. A
# lane that has been handed the resolved state three times and is still in
# draft is not waiting on anything this job can see.
DRAFT_STRAND_MAX="${DRAFT_STRAND_MAX:-3}"

# ------------------------------------------------------------- the actions
# An action prints the section appended to the lane's brief. It gets:
#   $1 pr  $2 head branch  $3 head sha  $4 lane name  $5 cause detail (may be "")
resume_rebase() {
    cat <<EOF

---

## Handed back $(date -u '+%FT%TZ'): PR #$1 no longer merges into \`$TIP\`

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

# The strand brief. $5 is "ci=<STATE> quiet=<secs> arm=<label|none>" -- the
# RESOLVED STATE, and the reason this is worth a session at all. A lane
# resumed with no new information repeats what it did before, which is how a
# PR burns four attempts having never been wrong about anything.
resume_strand() {
    local ci quiet arm hrs
    ci=$(sed -n 's/.*\bci=\([A-Z]*\).*/\1/p' <<< "$5"); ci="${ci:-UNKNOWN}"
    quiet=$(sed -n 's/.*\bquiet=\([0-9]*\).*/\1/p' <<< "$5"); quiet="${quiet:-0}"
    arm=$(sed -n 's/.*\barm=\([A-Za-z:-]*\).*/\1/p' <<< "$5"); arm="${arm:-none}"
    hrs=$(( quiet / 3600 ))
    cat <<EOF

---

## Resumed $(date -u '+%FT%TZ'): PR #$1 is a draft and your lane was not running

Your session ended with #$1 still in draft, and \`hakux-lane-$4\` is not
active. **Nothing else can act on that PR**: \`board.sh\`, \`fleet.py\` and
\`fold.sh\` all skip drafts, correctly, because a draft means a lane is still
working -- and you are not. It would have sat there indefinitely.

**This is not counted as a failed attempt.** If you ended because you were
waiting, you were right to end; the harness had nowhere to put a waiting lane
and this job is that place. Here is what you were waiting for, resolved:

| | |
|---|---|
| head | \`${3:0:10}\` |
| CI on that head | **$ci** |
| arm verdict label | \`$arm\` |
| quiet for | ${hrs}h ($quiet s since the PR last changed) |

EOF
    case "$ci" in
    GREEN) cat <<EOF
CI is **GREEN** on \`${3:0:10}\`. That gate is done arguing with you.
EOF
        ;;
    RED) cat <<EOF
CI is **RED** on \`${3:0:10}\`. Read \`gh pr checks $1\` first: fixing that is
the task, and nothing downstream will look at this PR until it is green.
EOF
        ;;
    NONE) cat <<EOF
**No CI run exists** on \`${3:0:10}\` -- nothing has built this head, so no
gate can pass. The two causes are a merge conflict with \`$TIP\` (GitHub
builds the merge commit, so a PR that does not merge gets no runs at all:
check \`gh pr view $1 --json mergeable\` and \`git merge origin/$TIP\`), and
the retired skip-ci marker in the head commit's message. If it is the marker,
push \`git commit --allow-empty -m 'ci: build this head' && git push\` and do
**not** name the marker in that message -- GitHub matches it in the body too.
EOF
        ;;
    PENDING) cat <<EOF
CI is still **PENDING** on \`${3:0:10}\`, but the PR has been quiet for ${hrs}h,
which is longer than a run takes. Check \`gh pr checks $1\`: a job queued with
no runner never concludes by itself.
EOF
        ;;
    esac
    [ "$arm" = none ] || cat <<EOF

Your arm has been judged: the arms job labelled this PR \`$arm\` and posted the
verdict as a \`[job.arms]\` comment. **Read that comment before anything else.**
A \`regressed\` PR is not fold-ready; the verdict, not the diff, is the task.
EOF
    cat <<EOF

So: finish \`roles/lane.md\`'s definition of done -- \`docs/lanes/$4/NOTES.md\`
written, the PR body's \`Files:\` matching \`git diff --stat origin/$TIP...HEAD\`,
the prediction registered and committed with its refs or the body saying why
there is none -- and then **\`gh pr ready $1\`**. Do not re-open, re-measure or
extend work this PR already carries.

**If you are still waiting on something**, that is a finished session too, but
say it where a reader can see it: a PR comment starting \`[lane.$4] waiting:\`
naming what you are waiting for and what will resolve it. This job resumes a
lane once per head sha per cause, so if the thing you are waiting for lands and
nothing else on the PR changes, it will find you again on the quiet clock.
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

# THE JOIN NOTHING ELSE MAKES. One query, so the CI state and the quiet clock
# arrive with the row rather than costing a `pr view` per PR: `statusCheckRollup`
# is collapsed to the same four states `fold.sh` uses (its gate is the same
# question), and `quiet` is seconds since the PR last changed, taken from
# GitHub's own `updatedAt` rather than a timestamp on this host -- so the clock
# survives a restart of the timer and does not start over when a job is
# redeployed. The unit-liveness half of the join is below, per row: it is a
# systemd question and gh cannot answer it.
stranded_drafts() {   # -> "num<TAB>branch<TAB>head<TAB>labels<TAB>isDraft=<b> ci=<STATE> quiet=<secs>"
    gh pr list --repo "$GH_REPO" --state open --limit 100 \
        --json number,headRefName,headRefOid,isDraft,labels,updatedAt,statusCheckRollup \
        --jq 'sort_by(.number)[] | select(.isDraft) | select(.headRefName | startswith("lane/"))
              | [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
              | (if ($c | length) == 0 then "NONE"
                 elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
                 elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
                 else "PENDING" end) as $ci
              | "\(.number)\t\(.headRefName)\t\(.headRefOid)\t\(.labels | map(.name) | join(","))\tisDraft=\(.isDraft) ci=\($ci) quiet=\((now - (.updatedAt | fromdateiso8601)) | floor)"' 2>/dev/null
}

# ONE STREAM, ONE BODY. The two pickups ask GitHub different questions and
# produce the same eight fields, so everything that follows -- the lane name,
# the once-per-cause key, the worktree check, the liveness check, the cap, the
# attempt counter, the comment -- is written once. `$stale` holds spaces, which
# is why the stream is tab-separated and the rows are built before the loop:
# `while ... | read` would run the body in a subshell and lose `$resumed`.
rows=""
for row in "${HANDBACK_ROWS[@]}"; do
    read -r label action stale <<< "$row"
    while IFS=$'\t' read -r pr branch head labels; do
        [ -n "${pr:-}" ] || continue
        rows+="$label"$'\t'"$action"$'\t'"$stale"$'\t'"$pr"$'\t'"$branch"$'\t'"$head"$'\t'"$labels"$'\t'$'\n'
    done <<< "$(prs_for "$label")"
done
while IFS=$'\t' read -r pr branch head labels extra; do
    [ -n "${pr:-}" ] || continue
    # WHICH WAIT RESOLVED decides the cause, and the cause is the marker key.
    # `verified`/`regressed` is `arms.sh` saying a verdict landed, which is
    # information this lane has never seen; anything else falls to the clock.
    case ",$labels," in
        *,verified,*|*,regressed,*) strand_cause=draft-strand-arm ;;
        *)                          strand_cause=draft-strand-quiet ;;
    esac
    rows+="$strand_cause"$'\t'"resume_strand"$'\t'"$STRAND_STALE"$'\t'"$pr"$'\t'"$branch"$'\t'"$head"$'\t'"$labels"$'\t'"$extra"$'\n'
done <<< "$(stranded_drafts)"

resumed=0; seen=0
while IFS=$'\t' read -r label action stale pr branch head labels extra; do
        [ -n "${pr:-}" ] || continue

        # THE ROW MUST PROVE THE FILTER HAPPENED. Neither pickup is re-checked
        # by anything downstream, so a row that comes back not matching what it
        # was asked for means the filter did not happen -- a `--jq` that stopped
        # emitting a field, a gh that ignored a flag, a shim. The failure mode
        # is not "nothing found", which would be visible; it is resuming the
        # FIRST OPEN PR on the repository, by name, against its lane's attempt
        # budget. Found by the fold-ci checks, whose gh shim answers every
        # `pr list` with one row: every fold tick ran a resume of lane.foldci
        # and commented on #102.
        case "$label" in
        draft-strand-*)
            # `isDraft` and the branch shape are both filtered in the --jq, so
            # a row failing either is a row that bypassed the query. A draft
            # that is not a draft is the whole premise of this cause.
            case "$extra" in
                *"isDraft=true"*) ;;
                *) say "#${pr:-?} came back from the draft pickup without isDraft=true (extra=${extra:-none}); the filter did not happen, so acting on it would resume a lane that is not stranded"
                   continue ;;
            esac
            case "$branch" in
                lane/*) ;;
                *) say "#${pr:-?} came back from the draft pickup on branch ${branch:-none}, which is not lane/*; the filter did not happen"
                   continue ;;
            esac ;;
        *)
            case ",$labels," in
                *",$label,"*) ;;
                *) say "#${pr:-?} came back for --label $label without it (labels=${labels:-none}); the filter did not happen, so acting on it would resume the wrong lane"
                   continue ;;
            esac ;;
        esac

        seen=$((seen+1))
        skip=""
        for s in $stale; do case ",$labels," in *",$s,"*) skip="$s" ;; esac; done
        if [ -n "$skip" ]; then
            [ "$mode" = list ] && echo "#$pr $branch: $label but also $skip; already moved on"
            continue
        fi

        # How the cause reads to a person on the PR. A label says itself; the
        # strand causes are not labels and there is nothing on the PR to point
        # at, so they have to be said in words or the comment names a label
        # that does not exist.
        case "$label" in
            draft-strand-*) said="this PR is a draft and lane \`${branch#lane/}\`'s unit is not running" ;;
            *)              said="\`$label\` is set on this PR" ;;
        esac

        if ! lane_name "$branch"; then
            # Say it once per PR, not once per tick: this state does not change
            # by itself, and a comment every 30 minutes is noise on a PR whose
            # owner is a person.
            [ "$mode" = list ] && { echo "#$pr $branch: $label, NO LANE -- $REASON"; continue; }
            if [ ! -f "$H/done/noname-$pr" ]; then
                printf '%s\n' "$REASON" > "$H/done/noname-$pr"
                say "#$pr $branch: $label but no local lane; $REASON"
                comment "$pr" "[job.handback] $said and no local lane can act on it: $REASON"
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

        # The cause detail the action prints into the brief. For a label it is
        # whatever the job that set the label wrote down; for a strand it is
        # the resolved state -- which is the entire reason the resume is worth
        # a session rather than a repeat of the last one.
        cause=""; quiet=0; arm=none
        case "$label" in
        draft-strand-*)
            quiet=$(sed -n 's/.*\bquiet=\([0-9]*\).*/\1/p' <<< "$extra"); quiet="${quiet:-0}"
            case ",$labels," in
                *,regressed,*) arm=regressed ;;
                *,verified,*)  arm=verified ;;
            esac
            cause="${extra#isDraft=* } arm=$arm" ;;
        *)
            [ -f "$H/cause/$pr-$head" ] && cause=$(sed -n 's/^files=//p' "$H/cause/$pr-$head" | head -1) ;;
        esac

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

        # ------------------------------------------ the strand's own two gates
        uncounted=""
        if [ "${label#draft-strand}" != "$label" ]; then
            # WAITING IS NOT STRANDED. `draft-strand-quiet` fires on a clock and
            # nothing else, so before it does, the clock has to have run long
            # enough that the thing the lane was waiting for would have landed.
            # An arm is ~90 minutes; resuming at 30 would hand the session the
            # same "still queued" it ended on, and the marker would then keep
            # it from ever being resumed at that head again. No marker here:
            # the cause is unactioned and the clock is still running.
            # `draft-strand-arm` skips this -- a judged verdict IS the landing.
            if [ "$label" = draft-strand-quiet ] && [ "$quiet" -lt "$DRAFT_STRAND_SECS" ]; then
                [ "$mode" = list ] && { echo "#$pr $branch: draft, lane $name not running, but only quiet ${quiet}s of $DRAFT_STRAND_SECS; still waiting"; continue; }
                say "#$pr: lane $name is stranded in draft but only quiet ${quiet}s; waiting for $DRAFT_STRAND_SECS"
                continue
            fi
            # THE BOUND THAT REPLACES THE ATTEMPT THIS CAUSE DOES NOT SPEND.
            # Waiting is not failing, so a strand resume puts the attempt
            # counter back (below) -- which means the escalation policy cannot
            # end this, and something must. A lane handed the resolved state
            # DRAFT_STRAND_MAX times and still in draft is not waiting on
            # anything this job can see; that is a person's question.
            nstrand=$(cat "$H/strand/$name" 2>/dev/null || echo 0)
            if [ "$nstrand" -ge "$DRAFT_STRAND_MAX" ]; then
                [ "$mode" = list ] && { echo "#$pr $branch: draft, lane $name not running, but already strand-resumed $nstrand times (DRAFT_STRAND_MAX=$DRAFT_STRAND_MAX)"; continue; }
                if [ ! -f "$H/done/strandmax-$pr" ]; then
                    printf '%s\n' "$nstrand" > "$H/done/strandmax-$pr"
                    say "#$pr: lane $name strand-resumed $nstrand times already; handing to the owner"
                    label_add "$pr" blocked:needs-owner || say "  WARNING: could not label #$pr blocked:needs-owner"
                    comment "$pr" "[job.handback] Not resumed -- $said, and this job has already resumed \`lane.$name\` $nstrand times for that (\`DRAFT_STRAND_MAX=$DRAFT_STRAND_MAX\`). Those resumes did **not** spend the lane's attempts, because waiting is not failing, so nothing else was going to stop this.

It wants a person now. Either the lane is waiting on something this job cannot see, or its definition of done is not reachable from the brief it has. Per \`jobs/roles/board.md\`, that is the \`decision-needed\` path; \`rm $H/strand/$name\` on the host clears the count if the answer is just \"resume it again\"."
                fi
                continue
            fi
            uncounted=1
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
        # WAITING IS NOT FAILING, AND THE COUNTER CANNOT TELL THEM APART.
        # `lane.sh resume` counts every resume as an attempt: the fourth runs
        # on the escalated model and the fifth is refused outright. That is the
        # right policy for a lane that ended without finishing, and the wrong
        # one for a lane that ended because CI takes ten minutes -- re-merges
        # burned two lanes' attempts and escalated one to Fable for no reason
        # of its own on 2026-09-19. So the count is read before and put back
        # after, for the strand causes only. It is safe to do from here: by the
        # time `lane.sh resume` returns 0 the unit is up, and a second
        # `systemd-run --unit hakux-lane-$name` cannot start while it is, so
        # nothing else writes that file in between.
        attempts_before=$(cat "$WORK/attempts/$name" 2>/dev/null || echo 0)
        "$action" "$pr" "$branch" "$head" "$name" "$cause" >> "$WORK/briefs/$name.md"
        out=$(bash "$LANE_SH" resume "$name" 2>&1); rc=$?
        [ "$rc" -eq 0 ] || truncate -s "$size" "$WORK/briefs/$name.md"
        if [ "$rc" -eq 0 ] && [ -n "$uncounted" ]; then
            printf '%s\n' "$attempts_before" > "$WORK/attempts/$name"
            mkdir -p "$H/strand"
            printf '%s\n' "$(( $(cat "$H/strand/$name" 2>/dev/null || echo 0) + 1 ))" > "$H/strand/$name"
        fi
        if [ "$rc" -eq 0 ] && [ -n "$uncounted" ]; then
            echo "resumed (strand, attempt not counted): $out" > "$marker"
            say "#$pr: resumed lane.$name on $label -- $out"
            comment "$pr" "[job.handback] Resumed \`lane.$name\`: $said, so nothing else could act on it -- \`board.sh\`, \`fleet.py\` and \`fold.sh\` all skip drafts, and that is right while a lane is working.

The resolved state went into its brief (\`${head:0:10}\`: \`$cause\`), because a lane resumed with no new information repeats what it did before. **This did not spend one of the lane's attempts**: waiting on a ten-minute CI run or a ninety-minute arm is not a failed pass, and the escalation policy is for failed passes. It is bounded instead at \`DRAFT_STRAND_MAX=$DRAFT_STRAND_MAX\` per lane, and at once per head sha per cause.

This job does **not** mark a PR ready: the definition of done includes \`NOTES.md\`, the \`Files:\` line and the prediction refs, none of which a script can check. That call stays with the lane."
            resumed=1
        elif [ "$rc" -eq 0 ]; then
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
done <<< "$rows"

# Say so when there is nothing, the way `fold.sh list` does: an empty run and a
# broken `gh` look identical otherwise, and this job's whole output is one line
# in $WORK/logs/handback/tick.log that somebody reads at a distance. It names
# every cause it looked for, including the two that are not labels -- otherwise
# a draft pickup that silently stopped working reads exactly like a quiet day.
CAUSES="${HANDBACK_ROWS[*]%% *} draft-strand-arm draft-strand-quiet"
[ "$seen" -eq 0 ] && { [ "$mode" = list ] && echo "nothing handed back ($CAUSES)" || say "nothing handed back ($CAUSES)"; }
exit 0
